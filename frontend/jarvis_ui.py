import sys
import requests
import os
import ctypes
import subprocess
import webbrowser
import json
import winsound
import uuid
import threading
import time
from datetime import datetime
from pathlib import Path

# QtWebEngine on this Windows host fails in the DirectComposition/GPU path
# (CrBrowserMain access violation). Keep the chat WebEngine on the stable
# software compositor unless the user explicitly overrides the environment.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "frontend")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
BACKEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from toggle_switch import ToggleSwitch
from jarvis_hud import JarvisHUD
from chat_composer import ChatComposer
from voice_mode_overlay import VoiceModeOverlay
from profile_dialog import UserProfileDialog
from account.application.account_coordinator import AccountCoordinator
from account.infrastructure.persistent_store import AccountStoreError
from services.storage_registry import StoragePaths
from account_ui import AccountCenterDialog
from autostart import is_enabled as windows_autostart_enabled, set_enabled as set_windows_autostart

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

print(os.path.join(BASE_DIR, "assets", "jarvis_off.png"))

API_ROOT = os.getenv("JARVIS_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_URL = f"{API_ROOT}/chat"
STARTUP_DIAGNOSTIC_WAV = os.path.abspath(os.path.join(
    BASE_DIR, "..", "backend", "voice_engine", "sound",
    "Начинаю диагностику системы (второй).wav"
))


def _ui_trace(stage, **fields):
    """Write opt-in UI diagnostics without changing normal runtime behavior."""
    if os.getenv("JARVIS_UI_TRACE", "").lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        trace_path = os.getenv(
            "JARVIS_UI_TRACE_PATH",
            os.path.join(os.environ.get("TEMP", os.getcwd()), "jarvis-ui-trace.log"),
        )
        payload = {
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
            "stage": stage,
            **fields,
        }
        with open(trace_path, "a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Diagnostics must never be allowed to interfere with the GUI thread.
        return

TECH_FONT_FILES = {
    "Good Times": "GOODTIME.ttf",
    "Imagine font": "imagine_font.ttf",
    "HandelGotD": "HandelGotD.ttf",
    "Nasalization": "nasaliza.ttf",
    "BitDust Two": "bitdust2.ttf",
}

TECH_ACTION_BUTTONS = {
    "COMP": (137, 227),
    "DOCS": (124, 281),
    "CTRL": (124, 340),
    "DESK": (127, 393),
    "XPLR": (536, 233),
    "CHRM": (556, 288),
    "GAME": (560, 348),
    "CFG": (545, 399),
}

HUD_TOP_PANEL_BUTTONS = {
    "CHAT": (266, 137),
    "AGENTS": (333, 137),
    "FUNCTION": (407, 137),
    "HISTORY": (493, 137),
}

HUD_BOTTOM_PANEL_BUTTONS = {
    "PROV": (232, 548),
    "MOD": (291, 548),
    "VID": (350, 548),
    "SET": (409, 548),
    "OUT": (468, 548),
}

HUD_TOP_PANEL_FONT_SIZES = {
    "CHAT": 8,
    "AGENTS": 8,
    "FUNCTION": 7,
    "HISTORY": 8,
}

WIDGET_ACTION_OPTIONS = [
    "CHAT", "AGENTS", "FUNCTION", "HISTORY", "PROV", "MOD", "VID", "SET", "OUT",
]
PANEL_ASSIGNMENT_KEYS = list(HUD_TOP_PANEL_BUTTONS) + list(HUD_BOTTOM_PANEL_BUTTONS) + list(TECH_ACTION_BUTTONS)
PANEL_ASSIGNMENT_OPTIONS = WIDGET_ACTION_OPTIONS + list(TECH_ACTION_BUTTONS) + ["CUSTOM"]
TIME_FORMAT_OPTIONS = (
    ("24 часа — 14:30", "%H:%M"),
    ("24 часа с секундами — 14:30:25", "%H:%M:%S"),
    ("12 часов — 02:30 PM", "%I:%M %p"),
)
DATE_FORMAT_OPTIONS = (
    ("TECH-A — 25TH OCT", "ORDINAL"),
    ("25 OCT 2026", "%d %b %Y"),
    ("25.10.2026", "%d.%m.%Y"),
    ("2026-10-25", "%Y-%m-%d"),
)


class VoiceDictationWorker(QObject):
    """Record one bounded push-to-record utterance and transcribe it locally."""

    recognized = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    state_changed = Signal(str)
    level_changed = Signal(float)
    finished = Signal()

    def __init__(self, device_index: int, model_path: str):
        super().__init__()
        self.device_index = int(device_index)
        self.model_path = str(model_path)
        self._stop_event = threading.Event()
        self._cancel_event = threading.Event()

    def request_stop(self):
        self._stop_event.set()

    def request_cancel(self):
        self._cancel_event.set()
        self._stop_event.set()

    @Slot()
    def run(self):
        try:
            import json as _json
            import queue as _queue
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model

            model_path = Path(self.model_path)
            if not model_path.is_dir():
                raise RuntimeError("Русская модель распознавания не найдена")

            audio_queue = _queue.Queue(maxsize=24)
            recognizer = KaldiRecognizer(Model(str(model_path)), 16000)
            import time as _time
            from array import array as _array
            last_level_emit = 0.0

            def callback(indata, frames, time_info, status):
                nonlocal last_level_emit
                if status:
                    # Device warnings are not fatal; the final recognizer
                    # result remains the source of truth.
                    return
                try:
                    now = _time.monotonic()
                    if now - last_level_emit >= 0.06:
                        samples = _array("h", bytes(indata))
                        peak = max((abs(sample) for sample in samples), default=0) / 32768.0
                        self.level_changed.emit(min(1.0, float(peak)))
                        last_level_emit = now
                    audio_queue.put_nowait(bytes(indata))
                except _queue.Full:
                    pass

            device = None if self.device_index < 0 else self.device_index
            self.state_changed.emit("Запись… нажмите микрофон ещё раз для остановки")
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=4000,
                device=device,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        data = audio_queue.get(timeout=0.2)
                    except _queue.Empty:
                        continue
                    recognizer.AcceptWaveform(data)

            # Process blocks already delivered by PortAudio before asking Vosk
            # for its final result; otherwise the last spoken syllables can
            # remain in the queue when Enter/stop is pressed.
            while True:
                try:
                    recognizer.AcceptWaveform(audio_queue.get_nowait())
                except _queue.Empty:
                    break

            if self._cancel_event.is_set():
                self.cancelled.emit()
                return

            self.state_changed.emit("Распознаю…")
            result = _json.loads(recognizer.FinalResult() or "{}")
            text = " ".join(str(result.get("text") or "").split()).strip()
            if text:
                self.recognized.emit(text)
            else:
                self.failed.emit("Речь не распознана")
        except Exception as error:
            self.failed.emit(self._safe_error(error))
        finally:
            self.finished.emit()

    @staticmethod
    def _safe_error(error: Exception) -> str:
        text = str(error).lower()
        if "input device" in text or "no default input" in text or "device" in text:
            return "Микрофон недоступен или не выбран"
        if "permission" in text or "access" in text:
            return "Нет доступа к микрофону"
        return "Не удалось распознать речь"


class RuntimeDeltaWorker(QObject):
    """Read bounded runtime deltas without putting polling on the GUI thread."""

    delta = Signal(str)
    stage = Signal(str)
    finished = Signal()

    def __init__(self, turn_id: str):
        super().__init__()
        self.turn_id = str(turn_id)
        self._stop_event = threading.Event()

    def request_stop(self):
        self._stop_event.set()

    @Slot()
    def run(self):
        import time as _time

        seen: set[str] = set()
        last_emit = 0.0
        accumulated = ""
        try:
            while not self._stop_event.is_set():
                try:
                    response = requests.get(
                        f"{API_ROOT}/runtime/events",
                        params={"turn_id": self.turn_id, "limit": 256},
                        timeout=0.7,
                    )
                    response.raise_for_status()
                    events = response.json().get("events", [])
                except (requests.RequestException, ValueError, TypeError):
                    events = []
                for event in events:
                    event_id = str(event.get("event_id") or "")
                    if event_id and event_id in seen:
                        continue
                    if event_id:
                        seen.add(event_id)
                    event_type = str(event.get("event_type") or "")
                    payload = event.get("payload") or {}
                    stage_text = {
                        "plan.created": f"План создан: {payload.get('step_count', 0)} шагов",
                        "item.started": "Анализирую запрос…",
                        "tool.selected": f"Инструмент: {payload.get('agent') or payload.get('route') or 'определяется'}",
                        "step_started": f"Выполняю шаг {payload.get('index', '')}/{payload.get('total', '')}".strip("/"),
                        "step.verified": "Шаг проверен",
                        "step.verification_failed": "Шаг завершён с предупреждением",
                        "task.completed": "Задача выполнена",
                    }.get(event_type)
                    if stage_text:
                        self.stage.emit(stage_text)
                    if event.get("event_type") == "message.delta":
                        accumulated = str(payload.get("accumulated") or accumulated)
                        now = _time.monotonic()
                        if now - last_emit >= 0.06:
                            self.delta.emit(accumulated)
                            last_emit = now
                    if event.get("event_type") in {"turn.completed", "turn.aborted", "turn.failed"}:
                        if accumulated:
                            self.delta.emit(accumulated)
                        return
                _time.sleep(0.08)
        finally:
            self.finished.emit()


class NetworkOperationWorker(QObject):
    """Run bounded settings and chat I/O outside the Qt GUI thread."""

    finished = Signal(object)
    failed = Signal(str)
    completed = Signal()

    def __init__(self, operation, payload=None, params=None):
        super().__init__()
        self.operation = str(operation)
        self.payload = payload or {}
        self.params = params or {}

    @Slot()
    def run(self):
        try:
            if self.operation == "load":
                response = requests.get(f"{API_ROOT}/settings/llm", timeout=6)
            elif self.operation == "save":
                response = requests.post(f"{API_ROOT}/settings/llm", json=self.payload, timeout=12)
            elif self.operation == "test":
                response = requests.post(f"{API_ROOT}/settings/llm/test", json=self.payload, timeout=20)
            elif self.operation == "models":
                response = requests.get(f"{API_ROOT}/settings/llm/models", params=self.params, timeout=12)
            elif self.operation == "sessions":
                response = requests.get(f"{API_ROOT}/chat/sessions", timeout=4)
            elif self.operation == "history-sessions":
                response = requests.get(
                    f"{API_ROOT}/chat/sessions",
                    params={"include_archived": "true"}, timeout=4,
                )
            elif self.operation == "chat-history":
                response = requests.get(
                    f"{API_ROOT}/chat/history",
                    params=self.params, timeout=5,
                )
            elif self.operation == "chat-send":
                response = requests.post(API_URL, json=self.payload, timeout=60)
            elif self.operation == "chat-cancel":
                turn_id = requests.utils.quote(str(self.params.get("turn_id") or ""), safe="")
                if not turn_id:
                    raise ValueError("chat turn id missing")
                response = requests.post(f"{API_ROOT}/chat/cancel/{turn_id}", timeout=4)
            elif self.operation == "backup-status":
                response = requests.get(f"{API_ROOT}/backups/status", timeout=3)
            elif self.operation == "backup-run":
                response = requests.post(f"{API_ROOT}/backups/run", timeout=30)
            elif self.operation == "capabilities":
                deep = bool(self.params.get("deep", False))
                response = requests.get(
                    f"{API_ROOT}/devices/capabilities",
                    params={"probe": "true" if deep else "false"},
                    timeout=45 if deep else 6,
                )
            elif self.operation == "camera-snapshot":
                response = requests.post(
                    f"{API_ROOT}/devices/camera/snapshot",
                    params={"index": int(self.params.get("index", 0))},
                    timeout=10,
                )
            elif self.operation == "voice-session-stop":
                response = requests.post(f"{API_ROOT}/voice/session/stop", timeout=4)
            elif self.operation in {"weather", "weather-validate"}:
                city = str(self.payload.get("city", "")).strip()
                key = str(self.payload.get("api_key", "")).strip()
                if not key:
                    raise ValueError("weather key missing")
                if not city:
                    geo_response = requests.get("http://ip-api.com/json", timeout=5)
                    geo_response.raise_for_status()
                    city = str(geo_response.json().get("city", "")).strip()
                    if not city:
                        raise ValueError("weather city unavailable")
                response = requests.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"q": city, "appid": key, "units": "metric", "lang": "ru"},
                    timeout=8,
                )
                response.raise_for_status()
                weather = response.json()
                entry = weather["weather"][0]
                self.finished.emit({
                    "ok": True,
                    "city": city.split(",", 1)[0].strip(),
                    "temp": round(weather["main"]["temp"]),
                    "description": entry["description"],
                    "condition_id": entry.get("id"),
                    "icon_code": entry.get("icon"),
                })
                return
            else:
                raise ValueError("Неизвестная операция провайдера")
            response.raise_for_status()
            _ui_trace("provider.worker.success", operation=self.operation, status=response.status_code)
            self.finished.emit(response.json())
        except Exception as error:
            _ui_trace("provider.worker.failed", operation=self.operation, error=type(error).__name__)
            self.failed.emit(type(error).__name__)
        finally:
            # Use the canonical worker -> deleteLater/quit sequence from the
            # worker thread. Removing Python references from thread.finished
            # while another HTTPS worker was still active caused a native
            # PySide/ucrtbase lifetime race during startup.
            self.completed.emit()


class NetworkOperationBridge(QObject):
    """Deliver worker results back to the GUI thread safely."""

    completed = Signal()

    def __init__(self, callback, error_callback, completion_callback=None, job_token=None, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.error_callback = error_callback
        self.completion_callback = completion_callback
        self.job_token = job_token

    def _complete(self):
        try:
            if self.completion_callback:
                self.completion_callback(self.job_token)
        finally:
            self.completed.emit()
            self.deleteLater()

    @Slot(object)
    def handle_result(self, data):
        try:
            if self.callback:
                self.callback(data)
        except Exception:
            if self.error_callback:
                self.error_callback("ошибка обработки ответа backend")
        finally:
            self._complete()

    @Slot(str)
    def handle_error(self, error):
        try:
            if self.error_callback:
                self.error_callback(error)
        finally:
            self._complete()


def start_network_operation(
    owner, operation, callback, error_callback, jobs, *, payload=None, params=None, completion_callback=None,
):
    """Run requests work in a Python thread and marshal only results into Qt.

    QThread-owned Python QObject teardown repeatedly crashed in shiboken6 on this
    Windows host. Requests does not require a Qt thread; keeping its worker as a
    normal Python thread leaves only the result delivery on the GUI event loop.
    """
    job_token = object()
    worker = NetworkOperationWorker(operation, payload=payload, params=params)

    def release(token):
        worker.deleteLater()
        jobs[:] = [job for job in jobs if len(job) < 4 or job[3] is not token]
        _ui_trace("network_job.finished", operation=operation, active_jobs=len(jobs))
        if completion_callback:
            completion_callback(token)

    bridge = NetworkOperationBridge(callback, error_callback, release, job_token, owner)
    # Explicit queued connections guarantee UI callbacks run in the GUI thread
    # even though requests.run() is invoked from a Python threading.Thread.
    worker.finished.connect(bridge.handle_result, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(bridge.handle_error, Qt.ConnectionType.QueuedConnection)
    thread = threading.Thread(
        target=worker.run,
        name=f"jarvis-network-{operation}",
        daemon=True,
    )
    jobs.append((thread, worker, bridge, job_token))
    _ui_trace("network_job.started", operation=operation, active_jobs=len(jobs))
    thread.start()
    return thread, worker, bridge


class VoiceStatusClient(QObject):
    """Poll the local voice API without waiting in the GUI event loop."""

    status_received = Signal(dict)
    failed = Signal(str)

    def __init__(self, api_root, parent=None):
        super().__init__(parent)
        self.api_root = api_root
        self.manager = QNetworkAccessManager(self)
        self._status_reply = None
        self._start_reply = None
        self._shutting_down = False

    def poll(self):
        if self._shutting_down or self._status_reply is not None:
            return
        request = QNetworkRequest(QUrl(f"{self.api_root}/voice/status"))
        request.setTransferTimeout(1000)
        reply = self.manager.get(request)
        self._status_reply = reply
        reply.finished.connect(lambda: self._finish_status(reply))

    def _finish_status(self, reply):
        if self._status_reply is reply:
            self._status_reply = None
        try:
            if self._shutting_down:
                return
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.failed.emit(reply.errorString())
                return
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status is None or not 200 <= int(status) < 300:
                self.failed.emit(f"HTTP {status}")
                return
            data = json.loads(bytes(reply.readAll()))
            if not isinstance(data, dict):
                raise ValueError("Voice status response is not an object")
            self.status_received.emit(data)
        except (ValueError, UnicodeDecodeError) as error:
            self.failed.emit(str(error))
        finally:
            reply.deleteLater()

    def ensure_worker(self, payload):
        if self._shutting_down or self._start_reply is not None:
            return
        request = QNetworkRequest(QUrl(f"{self.api_root}/voice/start"))
        request.setTransferTimeout(2000)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        reply = self.manager.post(request, json.dumps(payload).encode("utf-8"))
        self._start_reply = reply
        reply.finished.connect(lambda: self._finish_start(reply))

    def _finish_start(self, reply):
        if self._start_reply is reply:
            self._start_reply = None
        if not self._shutting_down and reply.error() != QNetworkReply.NetworkError.NoError:
            _ui_trace("voice.start.failed", error=reply.errorString())
        reply.deleteLater()

    def shutdown(self):
        self._shutting_down = True
        for reply in (self._status_reply, self._start_reply):
            if reply is not None:
                reply.abort()


class ProviderSwitch(QCheckBox):
    """Figma-style provider switch independent from the global QSS theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(78, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("OFF")
        self.toggled.connect(lambda checked: (self.setText("ON" if checked else "OFF"), self.update()))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(getattr(self, "accent_color", "#00aaff"))
        if self.isChecked():
            track = QColor("#e4edf1")
            knob_x = 53
        else:
            track = QColor(0, 0, 0, 25)
            knob_x = 3
        painter.setBrush(track)
        painter.setPen(QPen(accent, 1))
        painter.drawRoundedRect(QRectF(1, 1, 76, 26), 13, 13)
        painter.setBrush(accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(knob_x, 3, 22, 22))
        painter.setPen(QColor("#17303a") if self.isChecked() else QColor("#ffffff"))
        painter.setFont(QFont(self.font().family(), 10, QFont.Weight.Bold))
        # Keep the state label in the free half of the track. Drawing it on
        # top of the knob clipped the text and made ON/OFF look identical at
        # small DPI scales.
        text_rect = QRectF(7 if self.isChecked() else 43, 3, 33, 22)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "ON" if self.isChecked() else "OFF")


class NativeVideoDialog(QDialog):
    """Crazy Tad-compatible native fallback when WebEngine has no codec."""

    def __init__(self, source: QUrl, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ВИДЕО")
        self.resize(820, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        layout = QVBoxLayout(self)
        self.video = QVideoWidget(self)
        layout.addWidget(self.video)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.setSource(source)
        self.audio.setVolume(0.85)
        self.player.play()

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)


class FloatingVoiceStatusWidget(QWidget):
    """Small always-available, draggable voice status overlay."""

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self._drag_offset = None
        self.setObjectName("floatingVoiceStatus")
        self.setWindowTitle("Jarvis — состояние")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 140)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.label.setWordWrap(True)
        self.label.setMargin(12)
        self.label.setText("Состояние: выключен\nСлышит: —\nОтвет: —\nОшибка: —")
        self.shadow = QGraphicsDropShadowEffect(self.label)
        self.shadow.setBlurRadius(9)
        self.shadow.setColor(QColor(0, 190, 235, 48))
        self.shadow.setOffset(0, 0)
        self.label.setGraphicsEffect(self.shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def refresh_style(self):
        """Use the same glass/accent tokens as the main Jarvis window."""
        self.label.setStyleSheet(self.owner.status_widget_stylesheet())
        self.setWindowOpacity(self.owner.visual_settings["window_opacity"] / 100.0)

    def set_status_text(self, text):
        self.label.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.owner.save_status_widget_position(self)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(self.owner.dialog_stylesheet())
        size_menu = menu.addMenu("Размер")
        for label, size in (
            ("Маленький", "small"),
            ("Средний", "medium"),
            ("Большой", "large"),
        ):
            action = size_menu.addAction(label)
            action.triggered.connect(lambda checked=False, value=size: self.owner.set_status_widget_size(value))
        menu.addSeparator()
        close_action = menu.addAction("Закрыть виджет")
        close_action.triggered.connect(self.owner.close_status_widget)
        menu.exec(event.globalPos())
        event.accept()


class WeatherCardFrame(QFrame):
    """Sidebar weather card that opens a separate desktop copy on click."""

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.setObjectName("miniCard")
        self.setCursor(Qt.PointingHandCursor)
        self._press_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Consume the drag inside the card so the main Jarvis window cannot
        # interpret it as its own frameless-window move gesture.
        if self._press_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            start = self._press_position
            self._press_position = None
            if start is not None and (event.position().toPoint() - start).manhattanLength() <= 6:
                self.owner.open_detached_weather()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FloatingWeatherWidget(QWidget):
    """Independent weather card which stays available on the desktop."""

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self._drag_offset = None
        self._scale = 1.0
        self.setObjectName("floatingWeather")
        self.setWindowTitle("Jarvis — погода")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.card = QFrame(self)
        self.card.setObjectName("miniCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.card.setStyleSheet(self._card_stylesheet())
        self.city = QLabel("Мурино", self.card)
        self.temp = QLabel("--°C", self.card)
        self.desc = QLabel("Загрузка...", self.card)
        self.icon = QLabel(self.card)
        for label in (self.city, self.temp, self.desc):
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.apply_saved_size("medium")
        self.refresh_from_owner()

    def _card_stylesheet(self):
        opacity = max(0, min(100, int(
            self.owner.widget_settings.get("weather_detached_opacity", 96)
        )))
        frame_alpha = round(opacity * 2.55)
        glass_alpha = round(220 * opacity / 100)
        glass_alpha_soft = round(230 * opacity / 100)
        if self.owner.visual_settings.get("glass_enabled", True):
            background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 rgba(20,20,25,{glass_alpha}),"
                f"stop:0.35 rgba(15,15,20,{glass_alpha}),"
                f"stop:0.65 rgba(10,10,15,{glass_alpha_soft}),"
                f"stop:1 rgba(30,30,35,{glass_alpha}))"
            )
        else:
            background = f"rgba(15,15,20,{glass_alpha})"
        return (
            "QFrame#miniCard { background:" + background + "; border:none; "
            "border-radius:14px; }"
        )

    def refresh_from_owner(self):
        source = self.owner.widget_settings.get("weather", {})
        self.city.setText(self.owner.weather_city_label.text())
        self.temp.setText(self.owner.weather_temp_label.text())
        self.desc.setText(self.owner.weather_desc_label.text())
        pixmap = self.owner.weather_icon.pixmap()
        if pixmap and not pixmap.isNull():
            self.icon.setPixmap(pixmap)
        self._source_settings = dict(source)
        self.apply_saved_size(getattr(self, "_size_name", "medium"))

    def closeEvent(self, event):
        # Explicit close from the widget menu disables restoration on restart.
        self.owner.set_detached_weather_visible(False)
        super().closeEvent(event)

    def apply_saved_size(self, size_name):
        self._size_name = size_name
        self.owner.widget_settings["weather_detached_size"] = size_name
        self.owner.ui_settings.setValue(
            "widget_settings", json.dumps(self.owner.widget_settings, ensure_ascii=False)
        )
        # 256x112 maps to the user's 125% Windows scale as 320x140 on screen.
        dimensions = {"small": (165, 83), "medium": (220, 110), "large": (256, 112)}
        # Transparency belongs to the frame only; the window and glass fill
        # stay fully rendered so text and the weather PNG do not fade.
        self.setWindowOpacity(1.0)
        source = getattr(self, "_source_settings", None) or self.owner.widget_settings.get("weather", {})
        base_w = int(source.get("card_width", 220))
        base_h = int(source.get("card_height", 110))
        width, height = dimensions.get(size_name, dimensions["medium"])
        self._scale_x = width / max(1, base_w)
        self._scale_y = height / max(1, base_h)
        self._scale = min(self._scale_x, self._scale_y)
        self.setFixedSize(width, height)
        self.card.setGeometry(0, 0, width, height)

        def scaled(key, fallback):
            scale = self._scale_y if key.endswith("_y") or key.endswith("_h") else self._scale_x
            return round(int(source.get(key, fallback)) * scale)

        self.city.setStyleSheet(f"color:white; font-size:{scaled('city_font', 14)}px;")
        self.temp.setStyleSheet(f"color:white; font-size:{scaled('temp_font', 16)}px;")
        self.desc.setStyleSheet(f"color:white; font-size:{scaled('desc_font', 12)}px;")
        for name, label, defaults in (
            ("city", self.city, (12, 8, 92, 24)),
            ("temp", self.temp, (12, 42, 92, 28)),
            ("desc", self.desc, (12, max(8, base_h - 28), 108, 24)),
        ):
            x, y, item_w, item_h = [scaled(f"{name}_{key}", value) for key, value in zip(("x", "y", "w", "h"), defaults)]
            label.setGeometry(x, y, item_w, item_h)
        icon_size = scaled("icon_size", 64)
        icon_x = scaled("icon_x", base_w - 64 - 12)
        icon_y = scaled("icon_y", (base_h - 64) // 2)
        self.icon.setGeometry(icon_x, icon_y, icon_size, icon_size)
        icon_pixmap = self.owner.weather_icon.pixmap()
        if icon_pixmap and not icon_pixmap.isNull():
            self.icon.setPixmap(icon_pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.raise_()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.owner.save_detached_weather_position(self)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(self.owner.dialog_stylesheet())
        size_menu = menu.addMenu("Размер")
        for label, size in (("Маленький", "small"), ("Средний", "medium"), ("Большой", "large")):
            action = size_menu.addAction(label)
            action.triggered.connect(lambda checked=False, value=size: self.apply_saved_size(value))
        opacity_menu = menu.addMenu("Прозрачность")
        for label, opacity in (("50%", 50), ("70%", 70), ("85%", 85), ("96%", 96), ("100%", 100)):
            action = opacity_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, value=opacity: self.owner.set_detached_weather_opacity(value)
            )
        menu.addSeparator()
        close_action = menu.addAction("Закрыть виджет")
        close_action.triggered.connect(self.close)
        menu.exec(event.globalPos())
        event.accept()


class JarvisChatSettingsDialog(QDialog):
    """Firm-style chat preferences backed by the native settings store."""
    def __init__(self, parent):
        super().__init__(parent)
        self.owner = parent
        self.setWindowTitle("НАСТРОЙКИ ЧАТА")
        self.resize(520, 500)
        root = QVBoxLayout(self)
        title = QLabel("НАСТРОЙКИ ЧАТА")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        box = QGroupBox("ВНЕШНИЙ ВИД И ПОВЕДЕНИЕ")
        box.setObjectName("settingsTile")
        form = QFormLayout(box)
        self.incoming_glass = QCheckBox("Стеклянные входящие сообщения")
        self.outgoing_glass = QCheckBox("Стеклянные исходящие сообщения")
        self.avatars = QCheckBox("Показывать аватары")
        self.timestamps = QCheckBox("Показывать время сообщений")
        self.compact = QCheckBox("Компактный режим")
        self.autoplay = QCheckBox("Автовоспроизведение видео")
        defaults = {
            "incoming_glass": (self.incoming_glass, "chat_incoming_acrylic", True),
            "outgoing_glass": (self.outgoing_glass, "chat_outgoing_acrylic", False),
            "avatars": (self.avatars, "chat_show_avatars", True),
            "timestamps": (self.timestamps, "chat_show_timestamps", True),
            "compact": (self.compact, "chat_compact_mode", False),
            "autoplay": (self.autoplay, "chat_media_autoplay", False),
        }
        for check, key, fallback in defaults.values():
            check.setChecked(parent.ui_settings.value(key, fallback, type=bool))
            form.addRow(check)
        self.page_size = QSpinBox()
        self.page_size.setRange(10, 100)
        self.page_size.setValue(int(parent.ui_settings.value("chat_history_page_size", 25)))
        form.addRow("Сообщений за страницу", self.page_size)
        root.addWidget(box)
        root.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("СОХРАНИТЬ")
        buttons.button(QDialogButtonBox.Cancel).setText("ОТМЕНА")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self):
        return {
            "incoming_bubble_acrylic": self.incoming_glass.isChecked(),
            "outgoing_bubble_acrylic": self.outgoing_glass.isChecked(),
            "show_avatars": self.avatars.isChecked(),
            "show_timestamps": self.timestamps.isChecked(),
            "compact_mode": self.compact.isChecked(),
            "media_autoplay": self.autoplay.isChecked(),
            "chat_history_page_size": self.page_size.value(),
        }


class JarvisChatProfileDialog(QDialog):
    """Profile card opened from the Jarvis Chat header/avatar."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("ПРОФИЛЬ JARVIS CHAT")
        self.resize(420, 360)
        root = QVBoxLayout(self)
        avatar = QLabel("J")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(82, 82)
        avatar.setStyleSheet(f"background:{parent.accent_hex}; color:#071116; border-radius:41px; font-size:34px; font-weight:700;")
        root.addWidget(avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        name = QLabel("JARVIS CHAT")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size:20px; font-weight:700;")
        root.addWidget(name)
        info = QLabel("Локальный AI-ассистент\nПровайдер и модель выбираются в шапке чата")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(info)
        prompt = QLineEdit(parent.ui_settings.value("chat_system_prompt", "") or "")
        prompt.setPlaceholderText("Системная инструкция для Jarvis (необязательно)")
        root.addWidget(prompt)
        save = QPushButton("СОХРАНИТЬ ПРОФИЛЬ")
        save.clicked.connect(lambda: (parent.ui_settings.setValue("chat_system_prompt", prompt.text().strip()), self.accept()))
        root.addWidget(save)


class JarvisChatBridge(QObject):
    """Small WebChannel adapter for the imported Crazy Tad chat renderer."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @Slot(str)
    def replyToMessage(self, message_id):
        self.window.composer.set_reply(str(message_id), f"Сообщение {message_id}")

    @Slot()
    def clearReply(self):
        self.window.composer.clear_reply()

    @Slot(str)
    def insertEmoji(self, emoji):
        self.window.composer.insert_emoji_at_picker_cursor(str(emoji))

    @Slot(str)
    def queueAttachment(self, payload):
        """Queue the same semantic attachment payload as Crazy Tad's picker.

        The donor picker sends either a relative preview/media descriptor or a
        Crazy Tad sticker filename. Keep its kind/pack/item metadata so the
        composer and backend do not mistake a mult for a pinned message.
        """
        try:
            value = json.loads(payload) if isinstance(payload, str) else payload
        except (TypeError, ValueError):
            value = payload
        if isinstance(value, dict):
            relative = value.get("preview_path") or value.get("path") or value.get("media_path")
            path = (Path(BASE_DIR) / "assets" / "CHAT" / str(relative)).resolve() if relative else None
            kind = str(value.get("kind") or value.get("type") or "mult")
            pack_id = str(value.get("pack_id") or value.get("pack") or "")
            item_id = str(value.get("item_id") or value.get("id") or value.get("file") or "")
            send_mode = str(value.get("send_mode") or "")
            fallback = str(value.get("fallback") or "")
            if (pack_id, kind) not in {("mailru_agent", "mult"), ("telegram_retro", "sticker")}:
                return
            if send_mode != "draft_attachment":
                return
        else:
            path = (Path(BASE_DIR) / "assets" / "CHAT" / "stickers" / "crazy_tad" / str(value)).resolve() if value else None
            kind, pack_id, item_id, send_mode = "sticker", "crazy_tad", str(value or ""), "draft_attachment"
        if path:
            assets_root = (Path(BASE_DIR) / "assets" / "CHAT").resolve()
            try:
                path.relative_to(assets_root)
            except ValueError:
                return
            self.window.composer.add_attachment(
                path, kind=kind, pack_id=pack_id, item_id=item_id,
                send_mode=send_mode, fallback=fallback,
            )

    @Slot(str)
    def insertSticker(self, sticker_name):
        self.queueAttachment(sticker_name)

    @Slot(result=str)
    def loadMessageReactions(self):
        return self.window.ui_settings.value("chat_reactions", "{}")

    @Slot(str)
    def saveMessageReactions(self, value):
        self.window.ui_settings.setValue("chat_reactions", str(value or "{}"))

    @Slot(str)
    def setMessageReaction(self, payload):
        """Persist one donor-style reaction toggle in Jarvis chat storage."""
        try:
            data = json.loads(payload or "{}")
            message_id = str(data.get("message_id") or "")
            reaction = str(data.get("reaction") or "")
            if not message_id or not reaction:
                return
            requests.post(
                f"{API_ROOT}/chat/messages/{requests.utils.quote(message_id, safe='')}/reaction",
                json={"reaction": reaction, "actor": "user"},
                timeout=3,
            )
        except (TypeError, ValueError, requests.RequestException):
            return

    @Slot(result=str)
    def loadPickerUsage(self):
        return str(self.window.ui_settings.value("chat_picker_usage", "{}") or "{}")

    @Slot(str)
    def savePickerUsage(self, value):
        self.window.ui_settings.setValue("chat_picker_usage", str(value or "{}"))

    @Slot(str)
    def recordChatPerformance(self, _payload):
        return None

    @Slot(str)
    def pinMessage(self, message_id):
        try:
            requests.post(f"{API_ROOT}/chat/messages/{message_id}/pin", timeout=3)
        except requests.RequestException:
            pass

    @Slot(str)
    def unpinMessage(self, message_id):
        # Jarvis exposes one idempotent toggle endpoint at this stage.
        self.pinMessage(message_id)

    @Slot(str)
    def openAttachment(self, path):
        value = str(path or "").strip()
        if value.startswith("att_"):
            QDesktopServices.openUrl(QUrl(f"{API_ROOT}/api/media/{requests.utils.quote(value, safe='')}"))
            return
        candidate = Path(value).expanduser().resolve()
        if candidate.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))

    @Slot(str)
    def downloadAttachment(self, path):
        value = str(path or "").strip()
        if not value:
            return
        source_name = Path(value).name or "attachment"
        source_path = None
        response = None
        try:
            if value.startswith("att_"):
                response = requests.get(
                    f"{API_ROOT}/api/media/{requests.utils.quote(value, safe='')}",
                    stream=True,
                    timeout=20,
                )
                response.raise_for_status()
                disposition = response.headers.get("Content-Disposition", "")
                if "filename*=" in disposition:
                    source_name = disposition.split("filename*=UTF-8''", 1)[-1].strip('"; ') or source_name
            else:
                candidate = Path(value).expanduser().resolve()
                if not candidate.is_file():
                    return
                source_path = candidate
            target, _ = QFileDialog.getSaveFileName(
                self.window, "Сохранить вложение", source_name, "Все файлы (*.*)"
            )
            if not target:
                return
            if source_path is not None:
                with source_path.open("rb") as source, open(target, "wb") as destination:
                    destination.write(source.read())
            else:
                with open(target, "wb") as destination:
                    for chunk in response.iter_content(chunk_size=1024 * 128):
                        if chunk:
                            destination.write(chunk)
        except (OSError, requests.RequestException) as error:
            QMessageBox.warning(self.window, "Вложение", f"Не удалось сохранить файл:\n{error}")
        finally:
            if response is not None:
                response.close()

    @Slot(str)
    def openVideoAttachment(self, path):
        value = str(path or "").strip()
        if value.startswith("att_"):
            source = QUrl(f"{API_ROOT}/api/media/{requests.utils.quote(value, safe='')}")
        else:
            candidate = Path(value).expanduser().resolve()
            if not candidate.is_file():
                return
            source = QUrl.fromLocalFile(str(candidate))
        dialog = NativeVideoDialog(source, self.window)
        dialog.setObjectName("jarvisNativeVideo")
        dialog.show()
        # Keep the dialog alive while Qt is playing the remote source. Closed
        # dialogs are removed by the destroyed signal.
        dialogs = getattr(self.window, "_video_dialogs", None)
        if dialogs is None:
            dialogs = set()
            self.window._video_dialogs = dialogs
        dialogs.add(dialog)
        dialog.destroyed.connect(lambda *_: dialogs.discard(dialog))


class _WeatherEditorItem(QLabel):
    """One draggable element in the visual weather-card editor."""

    moved = Signal()

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        self._drag_offset = None
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            position = self.pos() + event.position().toPoint() - self._drag_offset
            parent = self.parentWidget()
            if parent:
                x = max(0, min(position.x(), parent.width() - self.width()))
                y = max(0, min(position.y(), parent.height() - self.height()))
                self.move(x, y)
                self.moved.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)


class WeatherLayoutEditorDialog(QDialog):
    """Visual editor for the four independent weather-card elements."""

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("ВИЗУАЛЬНАЯ НАСТРОЙКА ПОГОДЫ")
        self.resize(760, 520)
        self.weather = json.loads(json.dumps(settings or {}))
        self.items = {}
        self.spins = {}

        root = QVBoxLayout(self)
        title = QLabel("РАССТАНОВКА ПОГОДЫ")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        root.addWidget(QLabel("Перетаскивай элементы мышью прямо на карточке. Положение и размеры сохранятся в Jarvis."))

        body = QHBoxLayout()
        self.preview = QFrame()
        self.preview.setObjectName("weatherEditorPreview")
        self.preview.setFixedSize(440, 240)
        body.addWidget(self.preview, 0, Qt.AlignTop)

        controls = QGroupBox("ПАРАМЕТРЫ")
        form = QFormLayout(controls)
        fields = (
            ("Размер карточки — ширина", "card_width", 220, 160, 420),
            ("Размер карточки — высота", "card_height", 110, 80, 240),
            ("Город — размер", "city_font", 14, 8, 32),
            ("Градусы — размер", "temp_font", 16, 8, 36),
            ("Описание — размер", "desc_font", 12, 8, 28),
            ("Картинка — размер", "icon_size", 64, 24, 180),
        )
        for label, key, fallback, minimum, maximum in fields:
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(int(self.weather.get(key, fallback)))
            spin.setSuffix(" px")
            self.spins[key] = spin
            form.addRow(label, spin)
            spin.valueChanged.connect(self._apply_sizes)
        body.addWidget(controls, 1)
        root.addLayout(body)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("СОХРАНИТЬ РАСКЛАДКУ")
        buttons.button(QDialogButtonBox.Cancel).setText("ОТМЕНА")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._build_preview()

    def _build_preview(self):
        card_w = int(self.weather.get("card_width", 220))
        card_h = int(self.weather.get("card_height", 110))
        self.preview.setFixedSize(max(440, card_w + 24), max(240, card_h + 24))
        card = QFrame(self.preview)
        card.setObjectName("weatherEditorCard")
        card.setGeometry(12, 12, card_w, card_h)
        self.editor_card = card
        values = (
            ("city", "Мурино", "city_font", 12, 8, 92, 24),
            ("temp", "10°C", "temp_font", 12, 42, 92, 28),
            ("desc", "пасмурно", "desc_font", 12, max(8, card_h - 28), 108, 24),
        )
        for name, text, font_key, default_x, default_y, default_w, default_h in values:
            item = _WeatherEditorItem(name, card)
            item.setText(text)
            item.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setStyleSheet(f"color:white; font-size:{int(self.weather.get(font_key, 12))}px;")
            item.setGeometry(
                int(self.weather.get(f"{name}_x", default_x)),
                int(self.weather.get(f"{name}_y", default_y)),
                int(self.weather.get(f"{name}_w", default_w)),
                int(self.weather.get(f"{name}_h", default_h)),
            )
            item.moved.connect(self._remember_positions)
            item.show()
            self.items[name] = item

        icon = _WeatherEditorItem("icon", card)
        weather_dir = Path(BASE_DIR) / "assets" / "WEATHER"
        pixmap = QPixmap(str(weather_dir / "11.png"))
        if not pixmap.isNull():
            icon.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        icon_size = int(self.weather.get("icon_size", 64))
        icon.setGeometry(
            int(self.weather.get("icon_x", card_w - icon_size - 12)),
            int(self.weather.get("icon_y", (card_h - icon_size) // 2)),
            icon_size,
            icon_size,
        )
        icon.moved.connect(self._remember_positions)
        icon.show()
        self.items["icon"] = icon
        self._apply_sizes()

    def _apply_sizes(self):
        for name, key in (("city", "city_font"), ("temp", "temp_font"), ("desc", "desc_font")):
            item = self.items.get(name)
            if item:
                item.setStyleSheet(f"color:white; font-size:{self.spins[key].value()}px;")
        icon = self.items.get("icon")
        if icon:
            size = self.spins["icon_size"].value()
            icon.resize(size, size)
            pixmap = icon.pixmap()
            if pixmap and not pixmap.isNull():
                icon.setPixmap(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _remember_positions(self):
        for name, item in self.items.items():
            self.weather[f"{name}_x"] = item.x()
            self.weather[f"{name}_y"] = item.y()

    def values(self):
        self._remember_positions()
        for key, spin in self.spins.items():
            self.weather[key] = spin.value()
        for name, item in self.items.items():
            self.weather[f"{name}_w"] = item.width()
            self.weather[f"{name}_h"] = item.height()
        self.weather["card_width"] = self.spins["card_width"].value()
        self.weather["card_height"] = self.spins["card_height"].value()
        return self.weather


class GlassPreferencesDialog(QDialog):
    """Small persistent preference editor used by the unified settings center."""

    def __init__(self, owner, title, fields, checks=()):
        super().__init__(owner)
        self.owner = owner
        self.fields = fields
        self.edits = {}
        self.checks = {}
        self.setWindowTitle(title)
        self.setModal(False)
        self.resize(560, 420)
        self.setAttribute(Qt.WA_TranslucentBackground, owner.visual_settings["transparent_background"])
        self.setWindowOpacity(owner.visual_settings["window_opacity"] / 100.0)
        self.setStyleSheet(owner.dialog_stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        heading = QLabel(title.upper())
        heading.setObjectName("settingsTitle")
        root.addWidget(heading)
        form = QFormLayout()
        for key, label, default in fields:
            edit = QLineEdit(str(owner.ui_settings.value(key, default)))
            edit.setClearButtonEnabled(True)
            self.edits[key] = edit
            form.addRow(label, edit)
        root.addLayout(form)
        for key, label, default in checks:
            check = QCheckBox(label)
            check.setChecked(owner.ui_settings.value(key, default, type=bool))
            self.checks[key] = check
            root.addWidget(check)
        root.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("СОХРАНИТЬ")
        buttons.button(QDialogButtonBox.Cancel).setText("ОТМЕНА")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

    def save(self):
        for key, edit in self.edits.items():
            self.owner.ui_settings.setValue(key, edit.text().strip())
        for key, check in self.checks.items():
            self.owner.ui_settings.setValue(key, check.isChecked())
        self.owner.ui_settings.sync()
        self.accept()


class WeatherSettingsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("ПОГОДА")
        self.resize(560, 310)
        self.setModal(False)
        self.setAttribute(Qt.WA_TranslucentBackground, owner.visual_settings["transparent_background"])
        self.setWindowOpacity(owner.visual_settings["window_opacity"] / 100.0)
        self.setStyleSheet(owner.dialog_stylesheet())
        root = QVBoxLayout(self)
        title = QLabel("НАСТРОЙКИ ПОГОДЫ")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        form = QFormLayout()
        self.city = QLineEdit(str(owner.ui_settings.value("weather_city", "Мурино")))
        self.key = QLineEdit(str(owner.ui_settings.value("weather_api_key", "")))
        self.key.setEchoMode(QLineEdit.Password)
        self.status = QLabel("Ключ не показывается и не выводится в журнал.")
        self.status.setObjectName("settingsHint")
        form.addRow("Город", self.city)
        form.addRow("OpenWeather API key", self.key)
        root.addLayout(form)
        root.addWidget(self.status)
        self.save_button = QPushButton("ПРОВЕРИТЬ API И СОХРАНИТЬ")
        self.save_button.clicked.connect(self.validate_and_save)
        root.addWidget(self.save_button)
        layout = QPushButton("ОТКРЫТЬ ВИЗУАЛЬНЫЙ РЕДАКТОР")
        layout.clicked.connect(owner.open_weather_layout_editor)
        root.addWidget(layout)

    def validate_and_save(self):
        city, key = self.city.text().strip(), self.key.text().strip()
        self.owner._validate_and_save_weather(city, key, self.status, self.save_button)


class AIProviderDialog(QDialog):
    def __init__(self, owner, provider_id=None):
        super().__init__(owner)
        self.owner = owner
        self.initial_provider = str(provider_id or "").strip().lower()
        self._provider_jobs = []
        self.setWindowTitle("AI-ПРОВАЙДЕРЫ И МОДЕЛИ")
        self.resize(650, 470)
        self.setModal(False)
        self.setAttribute(Qt.WA_TranslucentBackground, owner.visual_settings["transparent_background"])
        self.setWindowOpacity(owner.visual_settings["window_opacity"] / 100.0)
        self.setStyleSheet(owner.dialog_stylesheet())
        root = QVBoxLayout(self)
        title = QLabel("ПРОВАЙДЕРЫ И МОДЕЛИ AI")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["ollama", "openai", "openai_compatible", "codex", "claude", "freellmapi"])
        self.provider.setCurrentText("ollama")
        self.base = QLineEdit("http://127.0.0.1:11434")
        self.model = QComboBox()
        self.model.setEditable(False)
        self.model.setEnabled(False)
        self.model.setPlaceholderText("Сначала получите список моделей")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        form.addRow("Провайдер", self.provider)
        form.addRow("Base URL", self.base)
        form.addRow("Модель", self.model)
        form.addRow("API key", self.key)
        root.addLayout(form)
        self.status = QLabel("Получение текущей конфигурации…")
        self.status.setObjectName("settingsHint")
        root.addWidget(self.status)
        actions = QHBoxLayout()
        models = QPushButton("ПОЛУЧИТЬ МОДЕЛИ")
        models.clicked.connect(self.fetch_models)
        test = QPushButton("ПРОВЕРИТЬ")
        test.clicked.connect(self.test_provider)
        save = QPushButton("СОХРАНИТЬ")
        save.clicked.connect(self.save_provider)
        for button in (models, test, save):
            actions.addWidget(button)
        root.addLayout(actions)
        self.provider.currentTextChanged.connect(self.update_defaults)
        QTimer.singleShot(0, self.load_current)

    def _run_provider_operation(self, operation, *, payload=None, params=None, callback=None):
        """Keep provider I/O off the Qt GUI thread."""
        start_network_operation(
            self,
            operation,
            callback,
            lambda error: self.status.setText(f"Операция не выполнена: {error}"),
            self._provider_jobs,
            payload=payload,
            params=params,
        )

    def load_current(self):
        self.status.setText("Загрузка конфигурации…")
        self._run_provider_operation("load", callback=self._apply_current_config)

    def _apply_current_config(self, data):
        provider = self.initial_provider or data.get("provider", "ollama")
        self.provider.setCurrentText(provider)
        config = data.get("config", {})
        fields = {
            "ollama": ("HEL_OLLAMA_BASE_URL", "HEL_OLLAMA_MODEL", ""),
            "openai": ("HEL_OPENAI_BASE_URL", "HEL_OPENAI_MODEL", "HEL_OPENAI_API_KEY"),
            "openai_compatible": ("HEL_OPENAI_BASE_URL", "HEL_OPENAI_MODEL", "HEL_OPENAI_API_KEY"),
            "codex": ("HEL_CODEX_BASE_URL", "HEL_CODEX_MODEL", "HEL_CODEX_API_KEY"),
            "claude": ("HEL_ANTHROPIC_BASE_URL", "HEL_ANTHROPIC_MODEL", "HEL_ANTHROPIC_API_KEY"),
            "freellmapi": ("HEL_FREELLMAPI_BASE_URL", "HEL_FREELLMAPI_MODEL", "HEL_FREELLMAPI_API_KEY"),
        }
        base_key, model_key, secret_key = fields.get(provider, fields["ollama"])
        self.base.setText(str(config.get(base_key) or ""))
        selected_model = str(config.get(model_key) or "").strip()
        self._set_model_choices([selected_model] if selected_model else [], selected_model)
        self._config_loaded = True
        self.key.clear()
        self.key.setEnabled(bool(secret_key))
        if secret_key and config.get(secret_key):
            self.key.setPlaceholderText("Сохранённый ключ скрыт; пустое поле его сохранит")
        self.status.setText("Конфигурация загружена. Секреты скрыты.")
        QTimer.singleShot(0, self.fetch_models)

    def _set_model_choices(self, models, selected_model=""):
        """Populate a read-only selector while preserving the saved choice."""
        selected_model = str(selected_model or "").strip()
        options = []
        for model in models:
            model = str(model or "").strip()
            if model and model not in options:
                options.append(model)
        if selected_model and selected_model not in options:
            options.insert(0, selected_model)
        self.model.blockSignals(True)
        try:
            self.model.clear()
            self.model.addItems(options)
            if selected_model:
                index = self.model.findText(selected_model)
                if index >= 0:
                    self.model.setCurrentIndex(index)
            self.model.setEnabled(bool(options))
        finally:
            self.model.blockSignals(False)

    def update_defaults(self, provider):
        defaults = {
            "ollama": ("http://127.0.0.1:11434", "qwen3:8b"),
            "claude": ("https://api.anthropic.com/v1", ""),
            "deepseek": ("https://api.deepseek.com", ""),
            "openai": ("https://api.openai.com/v1", ""),
            "openai_compatible": ("", ""),
            "freellmapi": ("", "AUTO"),
        }
        base_url, default_model = defaults.get(provider, ("", ""))
        self.base.setText(base_url)
        self._set_model_choices([default_model] if default_model else [], default_model)
        if getattr(self, "_config_loaded", False):
            QTimer.singleShot(0, self.fetch_models)

    def payload(self):
        key = self.key.text().strip()
        provider = self.provider.currentText().strip().lower()
        value = self.model.currentText().strip()
        base_url = self.base.text().strip()
        payload = {"provider": provider}
        fields = {
            "ollama": ("ollama_base_url", "ollama_model", None),
            "openai": ("openai_base_url", "openai_model", "openai_api_key"),
            "openai_compatible": ("openai_base_url", "openai_model", "openai_api_key"),
            "codex": ("codex_base_url", "codex_model", "codex_api_key"),
            "claude": ("claude_base_url", "claude_model", "claude_api_key"),
            "freellmapi": ("freellmapi_base_url", "freellmapi_model", "freellmapi_api_key"),
        }
        base_key, model_key, secret_key = fields.get(provider, fields["ollama"])
        payload[base_key] = base_url
        payload[model_key] = value
        if secret_key and key:
            payload[secret_key] = key
        return payload

    def fetch_models(self):
        self.status.setText("Получение списка моделей…")
        self._run_provider_operation(
            "models",
            params={"provider": self.provider.currentText(), "base_url": self.base.text().strip(), "api_key": self.key.text().strip()},
            callback=self._apply_models,
        )

    def _apply_models(self, data):
        models = data.get("models", [])
        if models:
            selected_model = self.model.currentText().strip()
            self._set_model_choices(models, selected_model)
            self.status.setText("Модели получены: " + ", ".join(models[:5]))
        else:
            self.status.setText(data.get("message", "Модели не найдены."))

    def test_provider(self):
        self.status.setText("Проверка подключения…")
        self._run_provider_operation(
            "test",
            payload=self.payload(),
            callback=lambda data: self.status.setText(data.get("message", "Проверка завершена.")),
        )

    def _apply_saved_provider(self, data):
        self._apply_current_config(data)
        selected_model = self.model.currentText().strip() or "не выбрана"
        self.status.setText(f"Конфигурация сохранена. Активная модель: {selected_model}.")

    def save_provider(self):
        self.status.setText("Сохранение конфигурации…")
        self._run_provider_operation(
            "save",
            payload=self.payload(),
            callback=self._apply_saved_provider,
        )


class WidgetSettingsDialog(QDialog):
    """Standalone HUD settings: layers, metrics and panel assignments."""

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("НАСТРОЙКИ IRON")
        self.setModal(False)
        self.resize(820, 760)
        self.settings = settings
        self.layer_checks = {}
        self.metric_checks = {}
        self.action_combos = {}
        self.target_edits = {}
        self.motion_spins = {}
        self.weather_settings = json.loads(json.dumps(settings.get("weather", {})))

        root = QVBoxLayout(self)
        title = QLabel("НАСТРОЙКИ ВИДЖЕТА IRON")
        title.setObjectName("settingsTitle")
        root.addWidget(title)
        hint = QLabel("Слои, метрики и назначения кнопок сохраняются отдельно от общих настроек приложения.")
        hint.setObjectName("settingsHint")
        root.addWidget(hint)

        self.status_widget_enabled = QCheckBox("Плавающее окно состояния Jarvis")
        self.status_widget_enabled.setChecked(settings.get("status_widget_enabled", True))
        root.addWidget(self.status_widget_enabled)

        content = QHBoxLayout()
        layers_box = QGroupBox("СЛОИ")
        layers_box.setObjectName("settingsTile")
        layers_layout = QVBoxLayout(layers_box)
        layer_values = settings.get("layers", {})
        for name in ("BG1", "BG2/BG000", "BG3", "BG4", "BG5", "BG6", "ROTATOR 1", "ROTATOR 2"):
            check = QCheckBox(name)
            check.setChecked(layer_values.get(name, True))
            self.layer_checks[name] = check
            layers_layout.addWidget(check)
        content.addWidget(layers_box)

        metrics_box = QGroupBox("МЕТРИКИ")
        metrics_box.setObjectName("settingsTile")
        metrics_layout = QVBoxLayout(metrics_box)
        metric_values = settings.get("metrics", {})
        for name in ("CPU", "RAM", "GPU", "DISK"):
            check = QCheckBox(name)
            check.setChecked(metric_values.get(name, True))
            self.metric_checks[name] = check
            metrics_layout.addWidget(check)
        metrics_layout.addStretch()
        content.addWidget(metrics_box)
        root.addLayout(content)

        motion_box = QGroupBox("АНИМАЦИЯ И РАЗМЕРЫ")
        motion_box.setObjectName("settingsTile")
        motion_layout = QFormLayout(motion_box)
        motion_values = settings.get("motion", {})
        motion_fields = (
            ("ROTATOR 1 — размер (%)", "rotator_1_size", 100, 25, 200),
            ("ROTATOR 1 — оборот (сек.)", "rotator_1_seconds", 75, 1, 600),
            ("ROTATOR 2 — размер (%)", "rotator_2_size", 100, 25, 200),
            ("ROTATOR 2 — оборот (сек.)", "rotator_2_seconds", 125, 1, 600),
            ("BG000 — размер (%)", "bg000_size", 100, 25, 200),
            ("BG000 — оборот (сек.)", "bg000_seconds", 40, 1, 600),
        )
        for label, key, fallback, minimum, maximum in motion_fields:
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(int(motion_values.get(key, fallback)))
            spin.setSuffix(" %" if "size" in key else " сек")
            self.motion_spins[key] = spin
            motion_layout.addRow(QLabel(label), spin)
        root.addWidget(motion_box)

        datetime_box = QGroupBox("ВРЕМЯ И ДАТА HUD")
        datetime_box.setObjectName("settingsTile")
        datetime_layout = QFormLayout(datetime_box)
        datetime_values = settings.get("datetime", {})
        self.time_format_combo = QComboBox()
        for label, value in TIME_FORMAT_OPTIONS:
            self.time_format_combo.addItem(label, value)
        self.time_format_combo.setCurrentIndex(max(
            0, self.time_format_combo.findData(datetime_values.get("time_format", "%H:%M"))
        ))
        datetime_layout.addRow(QLabel("Формат времени"), self.time_format_combo)
        self.time_size_spin = QSpinBox()
        self.time_size_spin.setRange(6, 48)
        self.time_size_spin.setSuffix(" px")
        self.time_size_spin.setValue(int(datetime_values.get("time_size", 14)))
        datetime_layout.addRow(QLabel("Размер времени"), self.time_size_spin)
        self.date_format_combo = QComboBox()
        for label, value in DATE_FORMAT_OPTIONS:
            self.date_format_combo.addItem(label, value)
        self.date_format_combo.setCurrentIndex(max(
            0, self.date_format_combo.findData(datetime_values.get("date_format", "ORDINAL"))
        ))
        datetime_layout.addRow(QLabel("Формат даты"), self.date_format_combo)
        self.date_size_spin = QSpinBox()
        self.date_size_spin.setRange(6, 36)
        self.date_size_spin.setSuffix(" px")
        self.date_size_spin.setValue(int(datetime_values.get("date_size", 8)))
        datetime_layout.addRow(QLabel("Размер даты"), self.date_size_spin)
        root.addWidget(datetime_box)

        weather_box = QGroupBox("ВИЗУАЛЬНАЯ НАСТРОЙКА ПОГОДЫ")
        weather_box.setObjectName("settingsTile")
        weather_layout = QVBoxLayout(weather_box)
        weather_layout.addWidget(QLabel("Отдельно настрой город, температуру, описание и размер картинки."))
        weather_editor_button = QPushButton("ОТКРЫТЬ ВИЗУАЛЬНЫЙ РЕДАКТОР")
        weather_editor_button.clicked.connect(self.open_weather_editor)
        weather_layout.addWidget(weather_editor_button)
        root.addWidget(weather_box)

        assignments = QGroupBox("НАЗНАЧЕНИЕ ПАНЕЛЕЙ")
        assignments.setObjectName("settingsTile")
        assignments_layout = QFormLayout(assignments)
        action_values = settings.get("actions", {})
        target_values = settings.get("targets", {})
        for key in PANEL_ASSIGNMENT_KEYS:
            combo = QComboBox()
            combo.addItems(PANEL_ASSIGNMENT_OPTIONS)
            combo.setCurrentText(action_values.get(key, key))
            self.action_combos[key] = combo
            target = QLineEdit(target_values.get(key, ""))
            target.setPlaceholderText("EXE, папка или URL — для CUSTOM")
            self.target_edits[key] = target
            row = QHBoxLayout()
            row.addWidget(combo, 1)
            row.addWidget(target, 2)
            assignments_layout.addRow(QLabel(key), row)
        assignment_scroll = QScrollArea()
        assignment_scroll.setWidgetResizable(True)
        assignment_scroll.setFrameShape(QFrame.NoFrame)
        assignment_scroll.setWidget(assignments)
        root.addWidget(assignment_scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("СОХРАНИТЬ")
        buttons.button(QDialogButtonBox.Cancel).setText("ОТМЕНА")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def open_weather_editor(self):
        dialog = WeatherLayoutEditorDialog(self, self.weather_settings)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.weather_settings = dialog.values()

    def values(self):
        return {
            "status_widget_enabled": self.status_widget_enabled.isChecked(),
            "status_widget_size": self.settings.get("status_widget_size", "medium"),
            "status_widget_position": self.settings.get("status_widget_position", {}),
            "layers": {name: check.isChecked() for name, check in self.layer_checks.items()},
            "metrics": {name: check.isChecked() for name, check in self.metric_checks.items()},
            "actions": {name: combo.currentText() for name, combo in self.action_combos.items()},
            "targets": {name: edit.text().strip() for name, edit in self.target_edits.items()},
            "motion": {name: spin.value() for name, spin in self.motion_spins.items()},
            "datetime": {
                "time_format": self.time_format_combo.currentData(),
                "time_size": self.time_size_spin.value(),
                "date_format": self.date_format_combo.currentData(),
                "date_size": self.date_size_spin.value(),
            },
            "weather": self.weather_settings,
            "panel_positions": self.settings.get("panel_positions", {}),
        }


class RotatablePanelButton(QPushButton):
    """Text panel button whose label can be tilted without rotating its hitbox."""

    angleChanged = Signal(float)
    fontSizeChanged = Signal(int)

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.panel_angle = 0.0
        self.panel_font_size = 10
        self._panel_hover = 0.0
        self._panel_press = 0.0
        self._panel_effect = QGraphicsColorizeEffect(self)
        self._panel_effect.setColor(QColor("#00EBF5"))
        self._panel_effect.setStrength(0.0)
        self.setGraphicsEffect(self._panel_effect)
        self._panel_animations = {}

    def _animate_panel_state(self, state, target, duration=150):
        current = float(getattr(self, f"_panel_{state}"))
        animation = QVariantAnimation(self)
        animation.setStartValue(current)
        animation.setEndValue(float(target))
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(
            lambda value, name=state: self._set_panel_state(name, float(value))
        )
        self._panel_animations[state] = animation
        animation.start()

    def _set_panel_state(self, state, value):
        setattr(self, f"_panel_{state}", value)
        strength = min(1.0, max(self._panel_hover * 0.78, self._panel_press))
        self._panel_effect.setStrength(strength)
        self.update()

    def enterEvent(self, event):
        self._animate_panel_state("hover", 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_panel_state("hover", 0.0)
        self._animate_panel_state("press", 0.0, 90)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._animate_panel_state("press", 1.0, 90)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._animate_panel_state("press", 0.0, 130)

    def set_panel_angle(self, angle):
        self.panel_angle = max(-45.0, min(45.0, float(angle)))
        self.update()

    def set_panel_font_size(self, size):
        self.panel_font_size = max(6, min(14, int(size)))
        font = QFont(self.font())
        font.setPointSize(self.panel_font_size)
        self.setFont(font)
        self.update()

    def wheelEvent(self, event):
        if self.property("calibrationEnabled"):
            step = 2 if event.angleDelta().y() > 0 else -2
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.set_panel_font_size(self.panel_font_size + (1 if step > 0 else -1))
                self.fontSizeChanged.emit(self.panel_font_size)
            else:
                self.set_panel_angle(self.panel_angle + step)
                self.angleChanged.emit(self.panel_angle)
            event.accept()
            return
        super().wheelEvent(event)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)

        painter.translate(self.rect().center())
        painter.rotate(self.panel_angle)
        press_scale = 1.0 - (self._panel_press * 0.06)
        painter.scale(press_scale, press_scale)
        painter.setPen(QColor(self.property("panelTextColor") or "#ffffff"))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(-self.width() / 2, -self.height() / 2, self.width(), self.height()),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )
        painter.end()


# ---------------- MESSAGE BUBBLE ----------------

class MessageBubble(QWidget):

    def __init__(self, text, user):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.label = QLabel(text)
        self.label.setMaximumWidth(120)
        self.label.setWordWrap(False)
        self.label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label.setStyleSheet("""
        color:white;
        font-size:13px;
        """)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(800)
        self.label.adjustSize()

        self.label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        

        if user:

            self.label.setStyleSheet("""
            QLabel{
                background:#EAEAEA;
                color:black;
                padding:8px 14px;
                border-radius:14px 14px 4px 14px;
            }
            """)

            layout.addStretch()
            layout.addWidget(self.label)

        else:

            self.label.setStyleSheet("""
            QLabel{
                background:#2E89FF;
                color:white;
                padding:8px 14px;
                border-radius:14px 14px 14px 4px;
            }
            """)

            layout.addWidget(self.label)
            layout.addStretch()

        # анимация появления
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

# ---------------- CHAT ITEM WIDGET ----------------

class CapabilityCard(QPushButton):
    """Clickable capability tile with a visual cue and independently styled state."""

    _IMAGE_BASE_GEOMETRY = QRect(13, 11, 96, 96)
    _IMAGE_HOVER_GEOMETRY = QRect(4, 2, 114, 114)

    def __init__(self, title: str, image_path: Path | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("capabilityCard")
        self.setProperty("available", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(138)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 15)
        layout.setSpacing(10)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(7)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("capabilityCardTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.status_label = QLabel("Проверка состояния…")
        self.status_label.setObjectName("capabilityCardStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.status_label)
        # Reserve the remaining card height for the future capability icon;
        # do not separate the status from the title with that empty space.
        text_layout.addStretch(1)
        layout.addLayout(text_layout, 1)

        self.image_slot = QWidget(self)
        self.image_slot.setObjectName("capabilityCardImageSlot")
        self.image_slot.setFixedSize(122, 118)
        self.image_label = QLabel(self.image_slot)
        self.image_label.setObjectName("capabilityCardImage")
        self.image_label.setGeometry(self._IMAGE_BASE_GEOMETRY)
        self.image_label.setScaledContents(True)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if image_path and image_path.is_file():
            self.image_label.setPixmap(QPixmap(str(image_path)))
        self._image_animation = QPropertyAnimation(self.image_label, b"geometry", self)
        self._image_animation.setDuration(170)
        self._image_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        layout.addWidget(self.image_slot, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _animate_image(self, expanded: bool) -> None:
        if self.image_label.pixmap().isNull():
            return
        self._image_animation.stop()
        self._image_animation.setStartValue(self.image_label.geometry())
        self._image_animation.setEndValue(
            self._IMAGE_HOVER_GEOMETRY if expanded else self._IMAGE_BASE_GEOMETRY
        )
        self._image_animation.start()

    def enterEvent(self, event):
        self._animate_image(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_image(False)
        super().leaveEvent(event)

    def set_capability_state(self, name: str, available: bool, status: str) -> None:
        self.title_label.setText(name)
        prefix = "Доступно" if available else "Недоступно"
        detail = str(status or "нет данных").strip()
        self.status_label.setText(f"{prefix} · {detail}")
        self.setProperty("available", bool(available))
        self.style().unpolish(self)
        self.style().polish(self)


class ChatItemWidget(QWidget):

    def __init__(self, text, pinned=False, mode=None):
        super().__init__()
        self.setObjectName("chatItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("""
            QWidget#chatItem {
                background: rgba(255,255,255,0.07);
                border: none;
                border-radius: 10px;
            }
            QWidget#chatItem:hover {
                background: rgba(255,255,255,0.12);
                border-radius: 10px;
            }
        """)
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 7, 0)
        layout.setSpacing(4)

        self.label = QLabel(text)
        self.label.setStyleSheet("color:white;font-size:10px;")
        self.label.setMinimumWidth(0)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.pin = QLabel()
        self.pin.setFixedSize(12,12)

        self.mode_label = QLabel("SELF-LEARNING" if str(mode or "").upper() == "SELF_LEARNING" else "")
        self.mode_label.setStyleSheet("color:#00AAFF;font-size:7px;font-weight:600;")
        self.mode_label.setVisible(bool(self.mode_label.text()))

        self.unread_dot = QLabel()
        self.unread_dot.setObjectName("chatUnreadDot")
        self.unread_dot.setFixedSize(8, 8)
        self.unread_dot.setStyleSheet(
            "background:#00AAFF; border:none; border-radius:4px;"
        )
        self.unread_dot.setToolTip("Есть новый ответ")
        self.unread_dot.hide()

        if pinned:
            pin_path = os.path.join(BASE_DIR,"assets","pin.svg")
            self.pin.setPixmap(QIcon(pin_path).pixmap(12,12))

        self.menu_btn = QPushButton("⋯")
        self.menu_btn.setFixedSize(20,20)
        self.menu_btn.hide()

        self.menu_btn.setStyleSheet("""
        QPushButton{
            background:transparent;
            border:none;
            color:#aaa;
        }
        QPushButton:hover{
            color:white;
        }
        """)

        layout.addWidget(self.label)
        layout.addWidget(self.mode_label)
        layout.addStretch()
        layout.addWidget(self.unread_dot)
        layout.addWidget(self.pin)
        layout.addWidget(self.menu_btn)

        self._active = False
        self._accent = "#00AAFF"
        self._unread = False

    def set_active(self, active: bool, accent: str) -> None:
        """Visually mark the chat bound to the current voice/text context."""
        self._active = bool(active)
        self._accent = str(accent or "#00AAFF")
        self.label.setStyleSheet(
            f"color:{self._accent if self._active else '#FFFFFF'};"
            f"font-size:10px; font-weight:{'700' if self._active else '400'};"
        )
        if self.mode_label.isVisible():
            self.mode_label.setStyleSheet(
                f"color:{self._accent}; font-size:7px; font-weight:600;"
            )
        self.update()

    def set_unread(self, unread: bool, accent: str = "#00AAFF") -> None:
        """Show a compact unread marker for a response received off-screen."""
        color = str(accent or "#00AAFF")
        self._unread = bool(unread)
        self.unread_dot.setStyleSheet(
            f"background:{color}; border:none; border-radius:4px;"
        )
        self.unread_dot.setVisible(self._unread and not self._active)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Keep the antialiased active outline fully inside the list viewport.
        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._active:
            painter.setBrush(QColor(self._accent))
            painter.setOpacity(0.22)
            painter.drawRoundedRect(rect, 10, 10)
            painter.setOpacity(1.0)
            painter.setPen(QPen(QColor(self._accent), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 10, 10)
        else:
            painter.setBrush(QColor(255, 255, 255, 30 if self.underMouse() else 18))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 10, 10)
        super().paintEvent(event)


# ---------------- TECH-A BUTTON ----------------

class TechActionButton(QToolButton):
    """Rainmeter-like three-state sprite button without a Qt hover overlay."""

    def __init__(self, static_frame, hover_frame, pressed_frame, parent=None):
        super().__init__(parent)
        self.static_frame = static_frame
        self.hover_frame = hover_frame
        self.pressed_frame = pressed_frame
        self.setIcon(QIcon(self.static_frame))
        self.setIconSize(self.static_frame.size())
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.setIcon(QIcon(self.hover_frame))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(QIcon(self.static_frame))
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.setIcon(QIcon(self.pressed_frame))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setIcon(QIcon(self.hover_frame if self.underMouse() else self.static_frame))


class AnimatedPanelIconButton(QToolButton):
    """Lower HUD icon with a borderless cyan hover/press animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panel_hover = 0.0
        self._panel_press = 0.0
        self._panel_base_icon_size = QSize(18, 18)
        self._panel_effect = QGraphicsColorizeEffect(self)
        self._panel_effect.setColor(QColor("#00EBF5"))
        self._panel_effect.setStrength(0.0)
        self.setGraphicsEffect(self._panel_effect)
        self._panel_animations = {}

    def setIconSize(self, size):
        self._panel_base_icon_size = QSize(size)
        super().setIconSize(size)

    def _animate_panel_state(self, state, target, duration=150):
        current = float(getattr(self, f"_panel_{state}"))
        animation = QVariantAnimation(self)
        animation.setStartValue(current)
        animation.setEndValue(float(target))
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(
            lambda value, name=state: self._set_panel_state(name, float(value))
        )
        self._panel_animations[state] = animation
        animation.start()

    def _set_panel_state(self, state, value):
        setattr(self, f"_panel_{state}", value)
        strength = max(self._panel_hover * 0.82, self._panel_press)
        self._panel_effect.setStrength(min(1.0, strength))
        scale = 1.0 + self._panel_hover * 0.12 - self._panel_press * 0.10
        base = self._panel_base_icon_size
        super().setIconSize(QSize(round(base.width() * scale), round(base.height() * scale)))

    def enterEvent(self, event):
        self._animate_panel_state("hover", 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_panel_state("hover", 0.0)
        self._animate_panel_state("press", 0.0, 90)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._animate_panel_state("press", 1.0, 90)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._animate_panel_state("press", 0.0, 130)


class OpaqueWebSurface(QFrame):
    """Opaque host that clips QtWebEngine's fractional-DPI edge pixels."""

    _EDGE_OVERSCAN = 2

    def __init__(self, view, parent=None):
        super().__init__(parent)
        self._view = view
        self._view.setParent(self)
        self.setObjectName("chatWebSurface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "QFrame#chatWebSurface{background:#121212; border:none;}"
        )
        surface_palette = self.palette()
        surface_palette.setColor(QPalette.ColorRole.Window, QColor("#121212"))
        self.setPalette(surface_palette)

    def resizeEvent(self, event):
        """Push the native WebEngine right/bottom compositor edge outside the clip."""
        bleed = self._EDGE_OVERSCAN
        self._view.setGeometry(0, 0, self.width() + bleed, self.height() + bleed)
        super().resizeEvent(event)


class StartButton(QPushButton):
    """START button with a restrained readable shadow and accent contour."""

    def __init__(self, text, text_color, accent_color, parent=None):
        super().__init__(text, parent)
        self.start_text_color = QColor(text_color)
        self.start_accent_color = QColor(accent_color)
        self.start_hovered = False
        # START is mouse-driven. Keeping keyboard focus here makes the native
        # style draw a square focus rectangle around the circular button.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoDefault(False)
        self.setDefault(False)

    def set_text_color(self, color):
        parsed = QColor(color)
        if parsed.isValid():
            self.start_text_color = parsed
            self.update()

    def set_accent_color(self, color):
        parsed = QColor(color)
        if parsed.isValid():
            self.start_accent_color = parsed
            self.update()

    def enterEvent(self, event):
        self.start_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.start_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.state &= ~QStyle.StateFlag.State_HasFocus
        text = option.text
        option.text = ""
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)

        painter.setFont(self.font())
        text_rect = self.rect()

        # Dark offset shadow keeps START readable over the bright glass core.
        shadow = QColor(0, 0, 0, 225 if self.start_hovered else 210)
        painter.setPen(shadow)
        painter.drawText(
            text_rect.translated(0, 3 if self.start_hovered else 2),
            Qt.AlignCenter,
            text,
        )

        # A restrained accent contour adds separation without a heavy glow.
        contour = QColor(self.start_accent_color)
        contour.setAlpha(180 if self.start_hovered else 115)
        painter.setPen(contour)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            painter.drawText(text_rect.translated(dx, dy), Qt.AlignCenter, text)

        painter.setPen(self.start_text_color)
        painter.drawText(text_rect, Qt.AlignCenter, text)


# ---------------- MAIN UI ----------------

class CurrentPageStack(QStackedWidget):
    """Let the Settings scroll host size itself for the visible page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(self.updateGeometry)

    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page is not None else super().sizeHint()

    def minimumSizeHint(self):
        page = self.currentWidget()
        return page.minimumSizeHint() if page is not None else super().minimumSizeHint()

    def hasHeightForWidth(self):
        page = self.currentWidget()
        return page.hasHeightForWidth() if page is not None else super().hasHeightForWidth()

    def heightForWidth(self, width):
        page = self.currentWidget()
        return page.heightForWidth(width) if page is not None and page.hasHeightForWidth() else -1


class JarvisUI(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Jarvis Assist")
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, "assets", "jarvis.ico")))
        self._normal_window_size = QSize(1280, 850)
        self.resize(self._normal_window_size)
        self.setMinimumSize(1000, 800)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.ui_settings = QSettings("Jarvis", "Jarvis Assist")
        self._account_coordinator = None
        try:
            account_root = StoragePaths.from_backend_root(BACKEND_DIR).account_state.parent
            self._account_coordinator = AccountCoordinator.local_default(account_root)
        except (AccountStoreError, OSError, ValueError, TypeError):
            # Account integration is optional; Local Mode must still start.
            self._account_coordinator = None
        self._sync_authenticated_email_to_profile()
        # Keep the launch/normal geometry as the authoritative restore target.
        # Native maximize/fullscreen notifications must never replace it with
        # the expanded screen rectangle.
        self._launch_geometry = QRect(self.geometry())
        self._normal_geometry = QRect(self._launch_geometry)
        self._fullscreen_mode = False
        self._fullscreen_geometry_mode = False
        self.visual_settings = {
            "window_opacity": int(self.ui_settings.value("window_opacity", 96)),
            "transparent_background": self.ui_settings.value(
                "transparent_background", True, type=bool
            ),
            "glass_enabled": self.ui_settings.value("glass_enabled", True, type=bool),
            "glass_tint": str(self.ui_settings.value("glass_tint", "#00AAFF")),
        }
        if not QColor(self.visual_settings["glass_tint"]).isValid():
            self.visual_settings["glass_tint"] = "#00AAFF"
        self.hardware_settings = {
            "audio_input_device": int(self.ui_settings.value("audio_input_device", -1)),
            "video_input_device": int(self.ui_settings.value("video_input_device", 0)),
        }
        self.startup_widget_mode = self.ui_settings.value("startup_widget_mode", True, type=bool)
        # Calibration profiles are kept separately so fullscreen calibration
        # cannot overwrite the accepted widget-mode layout.
        self.panel_calibration_profile = (
            "fullscreen" if "--fullscreen" in sys.argv else "widget"
        )
        self.setAttribute(
            Qt.WA_TranslucentBackground,
            self.visual_settings["transparent_background"],
        )
        self.widget_settings = self.load_widget_settings()
        self.status_widget = FloatingVoiceStatusWidget(self)
        self.panel_calibration_mode = "--calibrate-panels" in sys.argv
        self._panel_drag = None
        self.tech_font_families = self.register_tech_fonts()
        self.active_font_family = self.ui_settings.value(
            "font_family",
            self.tech_font_families.get("Good Times", "Arial"),
        )
        stored_accent = self.ui_settings.value("accent_color", "#00ebf5")
        self.accent_color = QColor(stored_accent)
        if not self.accent_color.isValid():
            self.accent_color = QColor("#00ebf5")
        self.accent_hex = self.accent_color.name()
        stored_text_color = self.ui_settings.value("font_color", "#ffffff")
        self.text_color = QColor(stored_text_color)
        if not self.text_color.isValid():
            self.text_color = QColor("#ffffff")
        self.text_color_hex = self.text_color.name()
        QApplication.instance().setFont(QFont(self.active_font_family, 10))

        self.oldPos = None
        self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)

        self._network_jobs = []
        self._sessions_read_pending = False
        self._sessions_reload_requested = False
        self._unread_chat_ids = set()
        self._recent_chat_activity = {}
        self._recent_chat_sequence = 0
        self._chat_model_generation = 0
        self._history_sessions_generation = 0
        self._chat_history_generation = 0
        self._displayed_chat_id = None
        self._weather_generation = 0
        self._chat_request_in_flight = False
        self._runtime_delta_generation = 0
        self._closing_after_jobs = False

        self.build_ui()
        self.voice_orb_calibration_mode = "--calibrate-voice-orb" in sys.argv
        if self.voice_orb_calibration_mode:
            # Calibration is a visual-only mode: show the existing Voice Mode
            # overlay without starting microphone/backend voice capture.
            self.startup_widget_mode = False
        self.voice_mode_overlay = VoiceModeOverlay(
            Path(BASE_DIR) / "assets" / "CHAT",
            self.chat_frame,
        )
        self.voice_mode_overlay.set_orb_host(self, self.chat_frame)
        self.voice_mode_overlay.set_calibration_mode(self.voice_orb_calibration_mode)
        self.voice_mode_overlay.stop_requested.connect(self.stop_voice_chat_from_composer)
        # Keep a final HUD-only mouse fallback above decorative child layers.
        # It is removed on close and is restricted to the fixed HUD canvas.
        QApplication.instance().installEventFilter(self)
        self.current_chat_id = "default"
        self.status_widget.refresh_style()
        self.restore_status_widget_position()
        self.apply_status_widget_settings()
        self.apply_application_font()
        QTimer.singleShot(900, self.play_startup_diagnostic)

        self.menu.currentRowChanged.connect(self.on_menu_row_changed)
        self.menu.setCurrentRow(0)
        if self.startup_widget_mode:
            QTimer.singleShot(0, self.toggle_widget_mode)

        self.load_weather()
        if self.widget_settings.get("weather_detached_visible", False):
            QTimer.singleShot(350, self.open_detached_weather)

        if self.panel_calibration_mode:
            self.assistant_label.setText("КАЛИБРОВКА ПАНЕЛЕЙ: перетащите иконки мышью")

        self.weather_timer = QTimer()
        self.weather_timer.timeout.connect(self.load_weather)
        self.weather_timer.start(600000)

        self.voice_status_client = VoiceStatusClient(API_ROOT, self)
        self.voice_status_client.status_received.connect(self._apply_voice_status)
        self.voice_status_client.failed.connect(self._voice_status_failed)
        self.voice_status_timer = QTimer(self)
        self.voice_status_timer.timeout.connect(self.refresh_voice_status)
        # Voice phases are short-lived (especially WAV/TTS playback); polling
        # faster prevents the overlay from missing the real speaking window.
        self.voice_status_timer.start(350)
        if self.voice_orb_calibration_mode:
            QTimer.singleShot(900, self._open_voice_orb_calibration)
        self._voice_autostart_enabled = False
        self._voice_autostart_attempts = 0
        self._microphone_enabled = True
        QTimer.singleShot(250, self.sync_voice_model)
        QTimer.singleShot(0, self._initialize_voice_idle)

        # hover отслеживание
        self.chats_list.setMouseTracking(True)
        self.chats_list.viewport().setMouseTracking(True)
        self.chats_list.viewport().installEventFilter(self)

    def play_startup_diagnostic(self):
        """Play the optional local startup phrase without blocking the UI."""
        enabled = self.ui_settings.value("startup_diagnostic_enabled", True, type=bool)
        if enabled and os.path.isfile(STARTUP_DIAGNOSTIC_WAV):
            winsound.PlaySound(
                STARTUP_DIAGNOSTIC_WAV,
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )

    def load_widget_settings(self):
        default = {
            "status_widget_enabled": True,
            "weather_detached_visible": False,
            "weather_detached_size": "medium",
            "status_widget_position": {},
            "status_widget_size": "medium",
            "layers": {
                "BG1": True, "BG2/BG000": True, "BG3": True, "BG4": True,
                "BG5": True, "BG6": True, "ROTATOR 1": True, "ROTATOR 2": True,
            },
            "metrics": {"CPU": True, "RAM": True, "GPU": True, "DISK": True},
            "actions": {key: key for key in PANEL_ASSIGNMENT_KEYS},
            "targets": {},
            "motion": {
                "rotator_1_size": 100, "rotator_2_size": 100, "bg000_size": 100,
                "rotator_1_seconds": 75, "rotator_2_seconds": 125, "bg000_seconds": 40,
            },
            "datetime": {
                "time_format": "%H:%M", "time_size": 14,
                "date_format": "ORDINAL", "date_size": 8,
            },
            "weather": {
                "card_width": 220, "card_height": 110,
                "city_font": 14, "temp_font": 16, "desc_font": 12,
                "icon_size": 64,
                "city_x": 12, "city_y": 8, "city_w": 92, "city_h": 24,
                "temp_x": 12, "temp_y": 42, "temp_w": 92, "temp_h": 28,
                "desc_x": 12, "desc_y": 82, "desc_w": 108, "desc_h": 24,
                "icon_x": 144, "icon_y": 23, "icon_w": 64, "icon_h": 64,
            },
            "panel_positions": {
                key: {"x": position[0], "y": position[1], "angle": 0}
                for key, position in {**HUD_TOP_PANEL_BUTTONS, **HUD_BOTTOM_PANEL_BUTTONS}.items()
            },
            "panel_positions_by_mode": {},
        }
        raw = self.ui_settings.value("widget_settings", "")
        if not raw:
            return default
        try:
            saved = json.loads(raw)
            for group in (
                "layers", "metrics", "actions", "targets", "motion", "datetime", "weather",
            ):
                default[group].update(saved.get(group, {}))
            if "status_widget_enabled" in saved:
                default["status_widget_enabled"] = bool(saved["status_widget_enabled"])
            default["weather_detached_visible"] = bool(saved.get("weather_detached_visible", False))
            default["weather_detached_size"] = saved.get("weather_detached_size", "medium")
            default["status_widget_position"] = saved.get("status_widget_position", {})
            default["status_widget_size"] = saved.get("status_widget_size", "medium")
            default["panel_positions"].update(saved.get("panel_positions", {}))
            saved_profiles = saved.get("panel_positions_by_mode", {})
            if isinstance(saved_profiles, dict):
                for profile, positions in saved_profiles.items():
                    if isinstance(positions, dict):
                        default["panel_positions_by_mode"][profile] = positions
            # Preserve the previously accepted widget profile when opening
            # older settings that only had the legacy top-level map.
            default["panel_positions_by_mode"].setdefault(
                "widget", json.loads(json.dumps(default["panel_positions"]))
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return default

    def restore_status_widget_position(self):
        """Restore the floating status overlay position or place it top-right."""
        position = self.widget_settings.get("status_widget_position", {})
        if isinstance(position, dict) and {"x", "y"}.issubset(position):
            x, y = int(position["x"]), int(position["y"])
            screen = QApplication.primaryScreen()
            available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 850)
            x = max(available.left(), min(x, available.right() - self.status_widget.width()))
            y = max(available.top(), min(y, available.bottom() - self.status_widget.height()))
            self.status_widget.move(x, y)
            return
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 850)
        self.status_widget.move(available.right() - self.status_widget.width() - 24, available.top() + 80)

    def save_status_widget_position(self, widget):
        self.widget_settings["status_widget_position"] = {"x": widget.x(), "y": widget.y()}
        self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))

    def apply_status_widget_settings(self):
        """Apply the settings checkbox without affecting the main HUD mode."""
        self.set_status_widget_size(self.widget_settings.get("status_widget_size", "medium"), persist=False)
        enabled = bool(self.widget_settings.get("status_widget_enabled", True))
        if enabled:
            self.status_widget.show()
            self.status_widget.raise_()
        else:
            self.status_widget.hide()

    def set_status_widget_size(self, size_name, persist=True):
        sizes = {
            "small": (260, 112),
            "medium": (320, 140),
            "large": (430, 190),
        }
        normalized = size_name if size_name in sizes else "medium"
        self.status_widget.setFixedSize(*sizes[normalized])
        self.widget_settings["status_widget_size"] = normalized
        if persist:
            self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))

    def close_status_widget(self):
        self.widget_settings["status_widget_enabled"] = False
        self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))
        self.status_widget.hide()

    def toggle_status_widget(self):
        """Toggle the floating status overlay from the HUD OUT button."""
        enabled = not self.status_widget.isVisible()
        self.widget_settings["status_widget_enabled"] = enabled
        self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))
        self.apply_status_widget_settings()
        self.assistant_label.setText(
            "Окно состояния включено" if enabled else "Окно состояния выключено"
        )

    def open_widget_settings(self):
        dialog = WidgetSettingsDialog(self, self.widget_settings)
        dialog.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet(self.dialog_stylesheet())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.widget_settings = dialog.values()
            self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))
            self.hud.apply_widget_settings(self.widget_settings)
            self.hud.set_datetime_settings(self.widget_settings.get("datetime", {}))
            self.apply_weather_card_settings()
            self.apply_status_widget_settings()
            for key, button in getattr(self, "hud_panel_button_map", {}).items():
                button.setProperty("actionKey", self.widget_settings["actions"].get(key, key))
                button.style().unpolish(button)
                button.style().polish(button)
            self.assistant_label.setText("Настройки виджета сохранены")

    def on_menu_row_changed(self, row):
        _ui_trace(
            "menu.row_changed.begin",
            row=row,
            widget_mode=getattr(self, "widget_mode", None),
            pages_index=self.pages.currentIndex() if hasattr(self, "pages") else None,
        )
        self._stop_voice_mode_for_navigation("смене раздела")
        if row == 1 and hasattr(self, "create_new_chat"):
            self.create_new_chat()
            self.set_settings_header_visible(False)
            _ui_trace("menu.row_changed.end", row=row, result="chat")
            return
        if row == 2:
            _ui_trace("menu.row_changed.before_devices")
            self.ensure_full_ui()
            self.pages.setCurrentIndex(3)
            self.set_settings_header_visible(False)
            _ui_trace("menu.row_changed.end", row=row, result="devices")
            return
        if row == 3:
            _ui_trace("menu.row_changed.before_settings_ensure")
            self.ensure_full_ui()
        _ui_trace("menu.row_changed.before_page", target=2 if row == 3 else row)
        self.pages.setCurrentIndex(2 if row == 3 else row)
        self.set_settings_header_visible(row == 3)
        _ui_trace(
            "menu.row_changed.end",
            row=row,
            result="settings" if row == 3 else "page",
            pages_index=self.pages.currentIndex(),
        )

    def set_settings_header_visible(self, visible):
        """Keep the absolute settings labels in sync with the active page."""
        if not hasattr(self, "settings_title_widget"):
            return
        for widget in (
            self.settings_title_widget,
            self.settings_subtitle_widget,
            self.settings_hub_hint_widget,
        ):
            widget.setVisible(bool(visible))
        if visible:
            self.position_settings_header()

    def open_settings_section(self, index):
        # Settings are a full application page.  Opening them from the HUD
        # must leave transparent widget mode first; otherwise the page is
        # rendered on top of the compact overlay with no normal chrome.
        _ui_trace("settings.open.begin", section=index, widget_mode=getattr(self, "widget_mode", None))
        self.ensure_full_ui()
        _ui_trace("settings.open.after_ensure", widget_mode=getattr(self, "widget_mode", None))
        self.menu.setCurrentRow(3)
        _ui_trace("settings.open.after_menu", pages_index=self.pages.currentIndex())
        if hasattr(self, "settings_nav"):
            self.settings_nav.setCurrentRow(index)
        _ui_trace(
            "settings.open.end",
            section=index,
            settings_index=self.settings_nav.currentRow() if hasattr(self, "settings_nav") else None,
        )

    def _jump_to_settings_section(self, title):
        """Navigate quick links by section text, not fragile numeric indexes."""
        if not hasattr(self, "settings_nav"):
            return
        wanted = str(title).casefold()
        for row in range(self.settings_nav.count()):
            if self.settings_nav.item(row).text().strip().casefold() == wanted:
                self.open_settings_section(row)
                return

    def position_settings_header(self):
        """Place the three settings labels above the cards, aligned with the logo row."""
        if not hasattr(self, "settings_page_widget") or not hasattr(self, "settings_title_widget"):
            return
        host = getattr(self, "settings_header_host", None)
        if host is None:
            return
        origin = self.settings_page_widget.mapTo(host, QPoint(0, 0))
        x = origin.x() + 9
        self.settings_title_widget.setGeometry(x, 19, 600, 42)
        self.settings_subtitle_widget.setGeometry(x, 61, 600, 24)
        self.settings_hub_hint_widget.setGeometry(x, 85, 850, 24)
        for widget in (
            self.settings_title_widget,
            self.settings_subtitle_widget,
            self.settings_hub_hint_widget,
        ):
            widget.raise_()

    def open_preference_dialog(self, title, fields=(), checks=()):
        dialog = GlassPreferencesDialog(self, title, fields, checks)
        dialog.show()
        self._preference_dialog = dialog

    def open_ai_settings(self):
        existing = getattr(self, "_ai_settings_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        dialog = AIProviderDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_ai_settings_dialog", None))
        dialog.show()
        self._ai_settings_dialog = dialog

    def open_weather_settings(self):
        dialog = WeatherSettingsDialog(self)
        dialog.show()
        self._weather_settings_dialog = dialog

    def open_weather_layout_editor(self):
        dialog = WeatherLayoutEditorDialog(self, self.widget_settings.get("weather", {}))
        dialog.setStyleSheet(self.dialog_stylesheet())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.widget_settings["weather"] = dialog.values()
            self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))
            self.apply_weather_card_settings()

    def open_custom_target(self, target, source_name=None):
        """Open a user-defined URL, application or folder from a panel binding."""
        if not target:
            self.assistant_label.setText(f"Для {source_name or 'кнопки'} не задан адрес")
            return
        try:
            if target.lower().startswith(("http://", "https://", "mailto:")):
                webbrowser.open(target)
            elif os.path.exists(target):
                os.startfile(target)
            else:
                subprocess.Popen(target, shell=True)
            self.assistant_label.setText(f"Открыто: {target}")
        except (OSError, ValueError) as error:
            self.assistant_label.setText(f"Не удалось открыть {target}: {error}")


    def activate_assistant(self):

     self.jarvis_state = not self.jarvis_state

     if self.jarvis_state:
        self.jarvis_button.setText("STOP")
        self.jarvis_button.setProperty("active", True)
        self.jarvis_button.style().unpolish(self.jarvis_button)
        self.jarvis_button.style().polish(self.jarvis_button)

        self.assistant_label.setText("JARVIS слушает...")

        # запускаем пульс
        self.pulse_anim.start()

        print("Jarvis ON")

     else:
        self.jarvis_button.setText("START")
        self.jarvis_button.setProperty("active", False)
        self.jarvis_button.style().unpolish(self.jarvis_button)
        self.jarvis_button.style().polish(self.jarvis_button)

        self.assistant_label.setText("Нажмите кнопку чтобы активировать JARVIS")

        # выключаем пульс
        self.pulse_anim.stop()
        self.glow.setBlurRadius(40)

        print("Jarvis OFF")

    def _set_assistant_ui(self, enabled, message=None):
        self.jarvis_state = bool(enabled)
        if hasattr(self, "assistant_toggle"):
            self.assistant_toggle.blockSignals(True)
            self.assistant_toggle.setChecked(self.jarvis_state)
            self.assistant_toggle.blockSignals(False)
        if hasattr(self, "microphone_toggle"):
            self.microphone_toggle.blockSignals(True)
            self.microphone_toggle.setChecked(self._microphone_enabled)
            self.microphone_toggle.blockSignals(False)
        self.jarvis_button.setText("STOP" if self.jarvis_state else "START")
        self.jarvis_button.setProperty("active", self.jarvis_state)
        self.jarvis_button.style().unpolish(self.jarvis_button)
        self.jarvis_button.style().polish(self.jarvis_button)
        if self.jarvis_state:
            self.pulse_anim.start()
            self.assistant_label.setText(message or "JARVIS слушает...")
        else:
            self.pulse_anim.stop()
            self.glow.setBlurRadius(40)
            self.assistant_label.setText(message or "Нажмите кнопку чтобы активировать JARVIS")

    def _assistant_toggle(self, checked):
        """Make the sidebar assistant switch control the real voice runtime."""
        desired = bool(checked)
        if desired == bool(self.jarvis_state):
            return
        self._toggle_voice_runtime()

    def _toggle_microphone_from_sidebar(self, checked):
        """Mute/unmute audio capture without stopping Jarvis itself."""
        self._microphone_enabled = bool(checked)
        if not self.jarvis_state:
            return
        try:
            response = requests.post(
                f"{API_ROOT}/voice/microphone",
                json={"enabled": self._microphone_enabled},
                timeout=3,
            )
            response.raise_for_status()
            data = response.json()
            if "microphone_enabled" in data:
                self._microphone_enabled = bool(data["microphone_enabled"])
            self._update_voice_debug(data)
        except (requests.RequestException, ValueError) as error:
            self.assistant_label.setText(f"Микрофон: ошибка переключения — {error}")

    def _voice_microphone_index(self):
        if hasattr(self, "audio_source_combo"):
            return int(self.audio_source_combo.currentData())
        return int(self.hardware_settings.get("audio_input_device", -1))

    def _auto_start_voice(self):
        """Enable the real microphone runtime shortly after the UI opens.

        The backend may start a little later than the Qt window, so retry a
        few times. A deliberate user click disables this automatic retry loop.
        """
        if not self._voice_autostart_enabled or self.jarvis_state:
            return
        self._voice_autostart_attempts += 1
        self._toggle_voice_runtime(automatic=True)
        if not self.jarvis_state and self._voice_autostart_attempts < 10:
            QTimer.singleShot(2000, self._auto_start_voice)

    def _initialize_voice_idle(self):
        """Open with START idle even if an old backend process was left on."""
        self._microphone_enabled = True
        try:
            requests.post(f"{API_ROOT}/voice/stop", timeout=3)
        except requests.RequestException:
            pass
        self._set_assistant_ui(False, "Нажмите START, чтобы Jarvis начал слушать")

    def _toggle_voice_runtime(self, automatic=False):
        """Start/stop the real backend microphone runtime."""
        if not automatic:
            self._voice_autostart_enabled = False
        target_enabled = not self.jarvis_state
        try:
            if target_enabled:
                response = requests.post(
                    f"{API_ROOT}/voice/start",
                    json={
                        "microphone_index": self._voice_microphone_index(),
                        "microphone_enabled": self._microphone_enabled,
                        "source": "widget",
                    },
                    timeout=4,
                )
            else:
                response = requests.post(f"{API_ROOT}/voice/stop", timeout=4)
            response.raise_for_status()
            data = response.json()
            self._set_assistant_ui(bool(data.get("enabled")), data.get("last_error") or None)
            print(f"Jarvis {'ON' if self.jarvis_state else 'OFF'}: {data}")
        except (requests.RequestException, ValueError) as error:
            # Do not put the raw HTTP/urllib exception into a geometry-driven
            # QLabel: its unbroken URL used to become the window's minimum
            # width and stretch the whole application. Keep the diagnostic in
            # the terminal and show a bounded user-facing message instead.
            print(f"Voice runtime unavailable: {error}")
            self._set_assistant_ui(False, "Голосовой runtime недоступен — backend не отвечает")

    def _ensure_voice_chat_session(self):
        chat_id = str(getattr(self, "current_chat_id", "default"))
        if chat_id.startswith("draft_"):
            response = requests.post(
                f"{API_ROOT}/chat/sessions",
                json={"title": "Голосовой разговор"},
                timeout=4,
            )
            response.raise_for_status()
            chat_id = str(response.json().get("id") or "default")
            self.current_chat_id = chat_id
            self.chat_view.page().runJavaScript(
                "window.setCurrentChatId && window.setCurrentChatId(" + json.dumps(chat_id) + ");"
            )
            self.load_history_sessions()
            self.load_chat_history()
        return chat_id

    def toggle_voice_chat_from_composer(self):
        """Start the shared runtime bound to the currently open ChatStore chat."""
        try:
            status = requests.get(f"{API_ROOT}/voice/status", timeout=3).json()
            active = status.get("voice_session") or {}
            if active.get("active") and active.get("source") == "chat":
                self.stop_voice_chat_from_composer()
                return
            chat_id = self._ensure_voice_chat_session()
            response = requests.post(
                f"{API_ROOT}/voice/session/start",
                json={
                    "chat_id": chat_id,
                    "microphone_index": self._voice_microphone_index(),
                    "microphone_enabled": True,
                    "replace": True,
                },
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            self.composer.set_voice_chat_active(True, "Голосовой чат активен в этом диалоге")
            self._set_assistant_ui(True, None)
            self.assistant_label.setText("Голосовой чат слушает этот диалог")
            self.voice_mode_overlay.show_mode()
            self.voice_mode_overlay.set_state("waiting")
        except (requests.RequestException, ValueError, KeyError) as error:
            self.composer.set_voice_chat_active(False, "Не удалось запустить голосовой чат")
            self.assistant_label.setText(f"Голосовой чат: {str(error)[:120]}")

    def _open_voice_orb_calibration(self):
        """Open the visual Orb calibration surface without starting voice capture."""
        overlay = getattr(self, "voice_mode_overlay", None)
        if overlay is None or not self.voice_orb_calibration_mode:
            return
        overlay.show_mode()
        overlay.set_state("waiting")
        self.assistant_label.setText("Калибровка Orb: перетащите, измените размер и зафиксируйте")

    def stop_voice_chat_from_composer(self):
        self._stop_voice_mode_for_navigation("завершению диалога", force=True)

    def _stop_voice_mode_for_navigation(self, reason: str, force: bool = False) -> None:
        """Hide Voice Mode immediately and stop its backend session off the GUI thread."""
        overlay = getattr(self, "voice_mode_overlay", None)
        composer = getattr(self, "composer", None)
        active = bool(getattr(composer, "_voice_chat_active", False))
        visible = bool(overlay is not None and overlay.isVisible())
        if not force and not active and not visible:
            return
        if overlay is not None:
            overlay.hide_mode()
        if composer is not None:
            composer.set_voice_chat_active(False, f"Голосовой чат остановлен при {reason}")
        if hasattr(self, "assistant_label"):
            self.assistant_label.setText("Голосовой чат завершён и сохранён")
        self._run_network_operation(
            "voice-session-stop",
            lambda _data: None,
            lambda _error: self.assistant_label.setText(
                "Voice Mode закрыт; backend не подтвердил остановку"
            ),
        )

    def _sync_voice_mode_overlay(self, data: dict) -> None:
        overlay = getattr(self, "voice_mode_overlay", None)
        if overlay is None or not overlay.isVisible():
            return
        phase = str(data.get("phase") or "").lower()
        try:
            last_speaking_finished_at = float(data.get("last_speaking_finished_at") or 0.0)
        except (TypeError, ValueError):
            last_speaking_finished_at = 0.0
        try:
            last_speaking_started_at = float(data.get("last_speaking_started_at") or 0.0)
        except (TypeError, ValueError):
            last_speaking_started_at = 0.0
        recently_finished = (
            last_speaking_finished_at > 0
            and 0 <= time.time() - last_speaking_finished_at <= 3.5
        )
        recently_started = (
            last_speaking_started_at > 0
            and 0 <= time.time() - last_speaking_started_at <= 12.0
            and last_speaking_started_at >= last_speaking_finished_at
        )
        if bool(data.get("speaking")) or recently_finished or recently_started or any(token in phase for token in ("говор", "отвечаю wav", "tts")):
            state = "speaking"
        elif any(token in phase for token in ("распозна", "уточня", "проверя", "выполня", "слышу", "запуска")):
            state = "processing"
        else:
            state = "waiting"
        overlay.set_state(state)
        try:
            audio_level = float(data.get("audio_level") or 0.04)
        except (TypeError, ValueError):
            audio_level = 0.04
        overlay.set_voice_activity(
            audio_level,
            "слышу" in phase or state == "speaking",
        )
        overlay.set_dialogue(
            str(data.get("last_transcript") or ""),
            str(data.get("last_response") or ""),
        )

    def _stop_voice_chat_before_switch(self, next_chat_id: str):
        """Never let a live chat session leak turns into another chat."""
        current_chat_id = str(getattr(self, "current_chat_id", "default"))
        if str(next_chat_id) == current_chat_id:
            return
        # Dictation is a separate local QThread from the backend voice-chat
        # session. Stop it here as well, otherwise its microphone callback can
        # continue after the composer has switched to another chat.
        dictation_worker = getattr(self, "_dictation_worker", None)
        dictation_thread = getattr(self, "_dictation_thread", None)
        if dictation_worker and dictation_thread and dictation_thread.isRunning():
            dictation_worker.request_cancel()
            if hasattr(self, "composer"):
                self.composer.set_voice_recording(False, "Запись остановлена при смене диалога")
            dictation_thread.quit()
            dictation_thread.wait(1500)
            self._dictation_worker = None
            self._dictation_thread = None
            self._dictation_auto_send = False
        # Voice Mode owns visual children reparented to the shell. Hide those
        # immediately and stop the backend session asynchronously.
        self._stop_voice_mode_for_navigation("смене диалога")

    def handle_composer_tool(self, tool: str):
        messages = {
            "control_windows": "Контроль ПК подключается через безопасные обработчики Jarvis.",
            "browser": "Контроль браузера пока доступен как точка подключения; действующие команды не имитируются.",
            "figma": "Подключение Figma требует OAuth/API-настройки и пока не авторизовано.",
            "plugins": "Система плагинов находится в разработке",
        }
        self.show_panel_dialog("ИНСТРУМЕНТЫ", [messages.get(tool, "Инструмент недоступен")])

    def toggle_fullscreen_window(self):
        # Fullscreen/window mode belongs to the application shell, not the
        # compact HUD presentation.  A transition from widget mode must first
        # restore the shell so the user never gets a fullscreen transparent
        # widget with a hidden settings/navigation layer underneath.
        if getattr(self, "widget_mode", False):
            self.toggle_widget_mode()

        currently_fullscreen = self._fullscreen_mode or self.isMaximized() or self.isFullScreen()
        if currently_fullscreen:
            normal = QRect(getattr(self, "_normal_geometry", self._launch_geometry))
            self._fullscreen_geometry_mode = False
            self._fullscreen_mode = False
            self.showNormal()
            available = self._available_screen_geometry()
            width = min(normal.width(), available.width())
            height = min(normal.height(), available.height())
            x = max(available.left(), min(normal.left(), available.right() - width + 1))
            y = max(available.top(), min(normal.top(), available.bottom() - height + 1))
            self.setGeometry(QRect(x, y, width, height))
            self.voice_mode_overlay.set_fullscreen_centered(False)
            self.fullscreen_button.setToolTip("Развернуть на весь экран")
        else:
            # Preserve the user's current normal rectangle as the restore
            # target.  The expanded fullscreen rectangle must never replace
            # it.
            self._normal_geometry = QRect(self.geometry())
            self._fullscreen_geometry_mode = True
            self._fullscreen_mode = True
            # Use available monitor geometry so the taskbar and Start menu
            # remain outside the frameless Jarvis surface.
            self.showNormal()
            self.setGeometry(self._available_screen_geometry())
            self.voice_mode_overlay.set_fullscreen_centered(True)
            self.fullscreen_button.setToolTip("Вернуть размер окна")
        self._refresh_sidebar_layout()
        self.raise_hud_controls()

    def changeEvent(self, event):
        """Keep the fullscreen flag and control tooltip in sync with Qt."""
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        actual_native_fullscreen = self.isFullScreen() or self.isMaximized()
        if actual_native_fullscreen:
            self._fullscreen_mode = True
        elif not self._fullscreen_geometry_mode:
            self._fullscreen_mode = False
        button = getattr(self, "fullscreen_button", None)
        if button is not None:
            button.setToolTip(
                "Вернуть размер окна" if self._fullscreen_mode else "Развернуть на весь экран"
            )

    def _available_screen_geometry(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            full = screen.geometry()
            available = screen.availableGeometry()
            if available.bottom() >= full.bottom():
                reserve = max(24, round(48 * screen.logicalDotsPerInch() / 96.0))
                available.setBottom(max(available.top(), full.bottom() - reserve))
            return available
        return QRect(0, 0, 1280, 850)

    def capture_initial_window_geometry(self) -> None:
        """Capture the normal launch rectangle after the native show event."""
        if self._fullscreen_mode or self.isMaximized() or self.isFullScreen():
            return
        geometry = QRect(self.geometry())
        if geometry.width() > 0 and geometry.height() > 0:
            self._launch_geometry = geometry
            self._normal_geometry = QRect(geometry)

    def toggle_voice_from_composer(self):
        """Start/stop one local dictation session in the active composer."""
        thread = getattr(self, "_dictation_thread", None)
        worker = getattr(self, "_dictation_worker", None)
        if thread and thread.isRunning() and worker:
            self.composer.set_voice_recording(True, "Останавливаю запись…")
            self._dictation_auto_send = True
            worker.request_stop()
            return

        model_path = Path(BASE_DIR).parent / "backend" / "voice_engine" / "model_small"
        self._dictation_thread = QThread(self)
        self._dictation_worker = VoiceDictationWorker(
            self._voice_microphone_index(),
            str(model_path),
        )
        self._dictation_auto_send = False
        self._dictation_worker.moveToThread(self._dictation_thread)
        self._dictation_thread.started.connect(self._dictation_worker.run)
        self._dictation_worker.state_changed.connect(self._dictation_state_changed)
        self._dictation_worker.level_changed.connect(self._dictation_level_changed)
        self._dictation_worker.recognized.connect(self._dictation_recognized)
        self._dictation_worker.failed.connect(self._dictation_failed)
        self._dictation_worker.cancelled.connect(self._dictation_cancelled)
        self._dictation_worker.finished.connect(self._dictation_thread.quit)
        self._dictation_worker.finished.connect(self._dictation_worker.deleteLater)
        self._dictation_thread.finished.connect(self._dictation_thread.deleteLater)
        self._dictation_thread.finished.connect(self._dictation_finished)
        self.composer.set_voice_recording(True, "Запрашиваю доступ к микрофону…")
        self.assistant_label.setText("Голосовой ввод готовится…")
        self._dictation_thread.start()

    @Slot()
    def cancel_voice_dictation(self):
        worker = getattr(self, "_dictation_worker", None)
        thread = getattr(self, "_dictation_thread", None)
        if worker and thread and thread.isRunning():
            worker.request_cancel()
            self.composer.set_voice_recording(True, "Отменяю запись…")

    @Slot(str)
    def _dictation_state_changed(self, state):
        if hasattr(self, "composer"):
            self.composer.set_voice_recording(True, state)
        if hasattr(self, "assistant_label"):
            self.assistant_label.setText(state)

    @Slot(float)
    def _dictation_level_changed(self, level):
        if hasattr(self, "composer"):
            self.composer.set_voice_level(level)

    @Slot(str)
    def _dictation_recognized(self, text):
        if hasattr(self, "composer"):
            self.composer.insert_transcript(text)
            self.composer.set_voice_recording(False, "Готово — текст добавлен в поле")
            # Voice dictation follows the voice-chat interaction model: once
            # the user confirms the recording, the recognized turn is sent to
            # the active chat instead of being left as an unsubmitted draft.
            if getattr(self, "_dictation_auto_send", False):
                self.composer.submit()
                self._dictation_auto_send = False
        if hasattr(self, "assistant_label"):
            self.assistant_label.setText("Голосовой текст отправлен в чат")

    @Slot(str)
    def _dictation_failed(self, message):
        self._dictation_auto_send = False
        if hasattr(self, "composer"):
            self.composer.set_voice_recording(False, message)
        if hasattr(self, "assistant_label"):
            self.assistant_label.setText(f"Голосовой ввод: {message}")

    @Slot()
    def _dictation_cancelled(self):
        self._dictation_auto_send = False
        if hasattr(self, "composer"):
            self.composer.set_voice_recording(False, "Запись отменена")

    @Slot()
    def _dictation_finished(self):
        self._dictation_thread = None
        self._dictation_worker = None

    def refresh_voice_status(self):
        self.voice_status_client.poll()

    def _voice_status_failed(self, _error):
        self._set_chat_status_dot("#ffffff", "Jarvis не онлайн")

    def _apply_voice_status(self, data):
        self._update_chat_status_dot(data)
        self._update_voice_debug(data)
        self._sync_voice_mode_overlay(data)
        if data.get("voice_model"):
            self._render_voice_model_status(data["voice_model"])
        if data.get("enabled") and data.get("conversation_worker") is False:
            # Recover an interrupted conversation worker without blocking Qt.
            self.voice_status_client.ensure_worker({
                "microphone_index": self._voice_microphone_index(),
                "microphone_enabled": self._microphone_enabled,
            })
        if bool(data.get("enabled")) != bool(self.jarvis_state):
            self._set_assistant_ui(bool(data.get("enabled")), data.get("last_error") or None)
        elif data.get("last_error") and self.jarvis_state:
            print(f"Voice runtime error: {data['last_error']}")
            error = str(data["last_error"])
            if error.startswith("command_action_missing:"):
                intent = error.split(":", 1)[1]
                self.assistant_label.setText(f"Команда не подключена: {intent}")
            elif error.startswith("conversation TTS:"):
                self.assistant_label.setText("Голосовой синтез недоступен")
            elif error.startswith("conversation request:"):
                self.assistant_label.setText("Не удалось получить ответ от модели")
            else:
                self.assistant_label.setText("Голосовой runtime: ошибка")
        elif self.jarvis_state and self.assistant_label.text() in {
            "Голосовой runtime: ошибка",
            "Голосовой синтез недоступен",
            "Не удалось получить ответ от модели",
        }:
            # Clear a transient provider/runtime error when the backend
            # reports that listening has recovered.
            self.assistant_label.setText(
                "JARVIS слушает..." if data.get("listening") else "Нажмите кнопку чтобы активировать JARVIS"
            )

    def _set_chat_status_dot(self, color: str, tooltip: str) -> None:
        dot = getattr(self, "chat_status_dot", None)
        if dot is None:
            return
        dot.setStyleSheet(
            "QLabel#chatStatusDot { background: %s; border-radius: 4px; min-width: 9px; max-width: 9px; "
            "min-height: 9px; max-height: 9px; }" % color
        )
        dot.setToolTip(tooltip)

    def _update_chat_status_dot(self, data: dict) -> None:
        override = getattr(self, "_chat_status_override", None)
        if override and time.monotonic() < override[2]:
            self._set_chat_status_dot(override[0], override[1])
            return
        if override:
            self._chat_status_override = None
        error = str(data.get("last_error") or "").strip()
        if error:
            self._set_chat_status_dot("#ff3b4d", f"Ошибка Jarvis: {error[:160]}")
        elif str(getattr(self, "_chat_model_confirmed", "")).strip():
            self._set_chat_status_dot("#00aaff", "Модель готова к работе")
        else:
            self._set_chat_status_dot("rgba(255,255,255,110)", "Модель ещё не готова")

    def _update_voice_debug(self, data):
        """Show the live voice handler state in the assistant page."""
        phase = data.get("phase") or ("слушаю" if data.get("listening") else "выключен")
        transcript = str(data.get("last_transcript") or "—")
        response = str(data.get("last_response") or "—")
        error = str(data.get("last_error") or "—")
        if len(response) > 420:
            response = response[:420] + "…"
        if len(error) > 240:
            error = error.splitlines()[0][:240] + "…"
        self.status_widget.set_status_text(
            f"Состояние:  {phase}\n"
            f"Слышит:     {transcript}\n"
            f"Ответ:      {response}\n"
            f"Ошибка:     {error}"
        )

    def raise_hud_controls(self):
        """Keep HUD controls above the decorative stacked layers."""
        for button in getattr(self, "tech_action_buttons", []):
            button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            button.raise_()
        self.apply_hud_hitbox_offset()

    def apply_hud_hitbox_offset(self):
        """Keep hitboxes at the same coordinates as the rendered HUD artwork."""
        # Do not move the button widgets: their artwork is painted by the same
        # widget that receives the click, so a geometry correction would move
        # the visible button as well. The transparent-mode offset experiment is
        # intentionally disabled until a separate overlay hitbox is introduced.
        offset_y = 0
        for button in getattr(self, "tech_action_buttons", []):
            base_x = button.property("hitboxBaseX")
            base_y = button.property("hitboxBaseY")
            if base_x is not None and base_y is not None:
                button.move(int(base_x), int(base_y) + offset_y)
        for button in getattr(self, "hud_panel_button_map", {}).values():
            base_x = button.property("hitboxBaseX")
            base_y = button.property("hitboxBaseY")
            if base_x is not None and base_y is not None:
                button.move(int(base_x), int(base_y) + offset_y)
        for button in getattr(self, "hud_panel_button_map", {}).values():
            button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            button.raise_()

    def create_tech_action_buttons(self, parent):
        """Restore the eight clickable TECH-A image buttons from the Rainmeter skin."""
        assets_dir = os.path.join(BASE_DIR, "assets", "TECH-A")
        buttons = []

        for name, (x, y) in TECH_ACTION_BUTTONS.items():
            path = os.path.join(assets_dir, f"{name}.png")
            sprite = QPixmap(path)
            if sprite.isNull() or sprite.width() % 3:
                continue

            # TECH-A stores three horizontal states in one PNG:
            # static | hover | pressed. Do not render the complete sprite.
            frame_width = sprite.width() // 3
            static_frame = sprite.copy(0, 0, frame_width, sprite.height())
            # Rainmeter order is UP | DOWN | OVER, not UP | OVER | DOWN.
            pressed_frame = sprite.copy(frame_width, 0, frame_width, sprite.height())
            hover_frame = sprite.copy(frame_width * 2, 0, frame_width, sprite.height())

            button = TechActionButton(static_frame, hover_frame, pressed_frame, parent)
            button.setObjectName("techTool")
            hit_padding = 8
            button.setGeometry(
                x - hit_padding,
                y - hit_padding,
                frame_width + hit_padding * 2,
                sprite.height() + hit_padding * 2,
            )
            button.setProperty("hitboxBaseX", x - hit_padding)
            button.setProperty("hitboxBaseY", y - hit_padding)
            button.setToolTip(name)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, key=name: self.handle_tech_action(key))
            button.show()
            button.raise_()
            buttons.append(button)

        return buttons

    def create_hud_panel_buttons(self, parent):
        """Create the upper command labels and lower SVG command icons."""
        buttons = []
        self.hud_panel_button_map = {}
        action_map = self.widget_settings.get("actions", {})
        position_map = self.widget_settings.get("panel_positions_by_mode", {}).get(
            self.panel_calibration_profile,
            self.widget_settings.get("panel_positions", {}),
        )
        if not position_map:
            position_map = self.widget_settings.get("panel_positions", {})

        def safe_position(name, default):
            saved = position_map.get(name, {})
            try:
                x = float(saved.get("x", default[0]))
                y = float(saved.get("y", default[1]))
                # Calibration stores coordinates in the fixed 710x710 HUD.
                # Older builds could leave screen coordinates here; discard
                # those values instead of placing a button outside the ring.
                if not (0 <= x <= JarvisHUD.HUD_SIZE and 0 <= y <= JarvisHUD.HUD_SIZE):
                    raise ValueError
                angle = float(saved.get("angle", 0))
                return {"x": x, "y": y, "angle": angle}
            except (AttributeError, TypeError, ValueError):
                return {"x": default[0], "y": default[1], "angle": 0}

        for name, (x, y) in HUD_TOP_PANEL_BUTTONS.items():
            saved_position = safe_position(name, (x, y))
            x, y = saved_position.get("x", x), saved_position.get("y", y)
            button = RotatablePanelButton(name, parent)
            button.setObjectName("hudPanelTop")
            button.setProperty("actionKey", action_map.get(name, name))
            button.setProperty("panelName", name)
            button.setProperty("panelTextColor", self.text_color_hex)
            button.set_panel_angle(saved_position.get("angle", 0))
            button.set_panel_font_size(
                saved_position.get("font_size", HUD_TOP_PANEL_FONT_SIZES.get(name, 8))
            )
            visual_width = 72 if name != "FUNCTION" else 86
            hit_width, hit_height = visual_width + 18, 44
            button.setProperty("panelAnchorX", x)
            button.setProperty("panelAnchorY", y)
            button.setProperty("panelAnchorOffsetX", (hit_width - visual_width) // 2)
            button.setProperty("panelAnchorOffsetY", (hit_height - 24) // 2)
            button.setGeometry(
                x - (hit_width - visual_width) // 2,
                y - (hit_height - 24) // 2,
                hit_width,
                hit_height,
            )
            button.setProperty("hitboxBaseX", button.x())
            button.setProperty("hitboxBaseY", button.y())
            button.setCursor(Qt.PointingHandCursor)
            # These HUD controls are mouse-driven; keep Qt's keyboard focus
            # frame from adding a visible selection outline around the panel.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if self.panel_calibration_mode:
                button.setProperty("calibrationEnabled", True)
                button.setToolTip(
                    f"{name}: перетащите мышью, колесо — наклон, Ctrl+колесо — размер текста"
                )
                button.installEventFilter(self)
                button.angleChanged.connect(lambda angle, item=button: self.save_panel_position(item))
                button.fontSizeChanged.connect(lambda size, item=button: self.save_panel_position(item))
            button.clicked.connect(lambda checked=False, item=button: self.handle_hud_panel_action(
                item.property("actionKey"), item.property("panelName")
            ))
            button.show()
            button.raise_()
            buttons.append(button)
            self.hud_panel_button_map[name] = button

        icons_dir = os.path.join(BASE_DIR, "assets", "TECH-A", "panel")
        for name, (x, y) in HUD_BOTTOM_PANEL_BUTTONS.items():
            saved_position = safe_position(name, (x, y))
            x, y = saved_position.get("x", x), saved_position.get("y", y)
            button = AnimatedPanelIconButton(parent)
            button.setObjectName("hudPanelIcon")
            button.setProperty("actionKey", action_map.get(name, name))
            button.setProperty("panelName", name)
            # Keep the artwork at the same visual center while giving the
            # lower-row controls a forgiving invisible hitbox.  The cells
            # deliberately overlap slightly; the application-level router
            # resolves an overlap by nearest center before Qt can select a
            # later decorative sibling. Calibration coordinates remain stable
            # because the anchor offsets move with the larger geometry.
            hit_width, hit_height = 84, 68
            anchor_offset_x, anchor_offset_y = 22, 18
            button.setProperty("panelAnchorX", x)
            button.setProperty("panelAnchorY", y)
            button.setProperty("panelAnchorOffsetX", anchor_offset_x)
            button.setProperty("panelAnchorOffsetY", anchor_offset_y)
            button.setGeometry(x - anchor_offset_x, y - anchor_offset_y, hit_width, hit_height)
            button.setProperty("hitboxBaseX", button.x())
            button.setProperty("hitboxBaseY", button.y())
            button.setIcon(QIcon(os.path.join(icons_dir, f"{name}.svg")))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(name)
            button.setCursor(Qt.PointingHandCursor)
            # Keep the lower HUD icons free of the native focus rectangle too.
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if self.panel_calibration_mode:
                button.setToolTip(f"{name}: перетащите мышью")
                button.installEventFilter(self)
            button.clicked.connect(lambda checked=False, item=button: self.handle_hud_panel_action(
                item.property("actionKey"), item.property("panelName")
            ))
            button.show()
            button.raise_()
            buttons.append(button)
            self.hud_panel_button_map[name] = button
        return buttons

    def handle_hud_background_release(self, event):
        """Route near-miss clicks on the HUD background to the nearest icon."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        point = event.position().toPoint()
        button = self._hud_panel_button_at(point)
        if button is not None:
            self.handle_hud_panel_action(
                button.property("actionKey"), button.property("panelName")
            )
            return True
        return False

    def _hud_panel_button_at(self, point, include_top=True):
        """Return the HUD button whose cell contains point.

        The artwork is drawn by transparent/decorative siblings, so a click
        can arrive on a sibling instead of the QToolButton itself.  Use a
        forgiving rectangular cell around each icon, then resolve overlaps by
        nearest center.  This keeps the hit area aligned with the visible HUD
        cells instead of relying on a small radial approximation.
        """
        candidates = []
        names = []
        if include_top:
            names.extend(HUD_TOP_PANEL_BUTTONS)
        names.extend(HUD_BOTTOM_PANEL_BUTTONS)
        for name in names:
            button = getattr(self, "hud_panel_button_map", {}).get(name)
            if button is None:
                continue
            center = button.geometry().center()
            dx = abs(center.x() - point.x())
            dy = abs(center.y() - point.y())
            if name in HUD_TOP_PANEL_BUTTONS:
                # Use the complete existing top-panel hitbox.  User-calibrated
                # labels can overlap slightly; nearest center resolves that
                # overlap without changing the visible text or coordinates.
                half_width = button.width() / 2
                half_height = button.height() / 2
            else:
                # 84x68 is the native invisible lower cell; the extra margin
                # covers the transparent outline without moving artwork.
                half_width, half_height = 48, 38
            if dx <= half_width and dy <= half_height:
                candidates.append((dx * dx + dy * dy, name, button))
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[2]

    def handle_hud_global_release(self, event):
        """Route a click from any decorative HUD child to its nearest panel."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if not self._hud_fallback_enabled():
            return False
        container = getattr(self, "hud_container", None)
        if container is None:
            return False
        global_pos = event.globalPosition().toPoint()
        local = container.mapFromGlobal(global_pos)
        if not container.rect().contains(local):
            return False
        target = QApplication.widgetAt(global_pos)
        buttons = getattr(self, "hud_panel_button_map", {})
        if target is not None and any(
            target is button or button.isAncestorOf(target) for button in buttons.values()
        ):
            return False
        button = self._hud_panel_button_at(local)
        if button is not None:
            self.handle_hud_panel_action(
                button.property("actionKey"), button.property("panelName")
            )
            return True
        return False

    def _hud_fallback_enabled(self) -> bool:
        """Limit the application-wide HUD hit-test to the actual HUD page."""
        pages = getattr(self, "pages", None)
        return pages is not None and pages.currentIndex() == 0

    def handle_hud_global_press(self, event):
        """Activate a HUD cell even when a decorative child owns the press."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if not self._hud_fallback_enabled():
            return False
        container = getattr(self, "hud_container", None)
        if container is None:
            return False
        global_pos = event.globalPosition().toPoint()
        local = container.mapFromGlobal(global_pos)
        if not container.rect().contains(local):
            return False
        target = QApplication.widgetAt(global_pos)
        button = self._hud_panel_button_at(local)
        protected_children = list(getattr(self, "tech_action_buttons", []))
        protected_children.append(getattr(self, "jarvis_button", None))
        if target is not None and any(
            target is child or (child is not None and child.isAncestorOf(target))
            for child in protected_children
        ):
            return False
        # In the normal widget presentation route the whole cell before Qt's
        # child hit-test. This is important where neighboring enlarged cells
        # or calibrated top labels overlap: the nearest visual cell, rather
        # than child z-order, wins.
        if button is not None and not self.panel_calibration_mode:
            self.handle_hud_panel_action(
                button.property("actionKey"), button.property("panelName")
            )
            self._hud_fallback_pressed_button = button
            return True

        clickable_children = list(getattr(self, "hud_panel_button_map", {}).values())
        clickable_children.extend(getattr(self, "tech_action_buttons", []))
        clickable_children.append(getattr(self, "jarvis_button", None))
        if target is not None and any(
            target is child or (child is not None and child.isAncestorOf(target))
            for child in clickable_children
        ):
            return False
        if button is None:
            return False
        self.handle_hud_panel_action(
            button.property("actionKey"), button.property("panelName")
        )
        self._hud_fallback_pressed_button = button
        return True

    def ensure_full_ui(self):
        """Restore the normal Jarvis chrome before opening an application page."""
        # Settings and application pages live in the same main window as the
        # HUD.  Leaving widget_mode enabled only hides the chrome and leaves
        # the settings page looking like a transparent, non-navigable overlay.
        # Use the normal mode transition so opacity, styles and hitboxes are
        # restored together instead of duplicating only part of the change.
        _ui_trace("ensure_full_ui.begin", widget_mode=getattr(self, "widget_mode", None))
        if getattr(self, "widget_mode", False):
            self.toggle_widget_mode()
        else:
            self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
            self.apply_styles()
        _ui_trace("ensure_full_ui.end", widget_mode=getattr(self, "widget_mode", None))

    def handle_hud_panel_action(self, name, source_key=None):
        """Route the new top/bottom HUD panel commands."""
        if name in {"CHAT", "HISTORY"}:
            self.ensure_full_ui()
        if name == "CUSTOM":
            self.open_custom_target(self.widget_settings.get("targets", {}).get(source_key, ""), source_key)
        elif name in TECH_ACTION_BUTTONS:
            self.handle_tech_action(name)
        elif name == "CHAT":
            self.menu.setCurrentRow(1)
            self.pages.setCurrentIndex(1)
        elif name == "HISTORY":
            self.menu.setCurrentRow(3)
            self.pages.setCurrentIndex(2)
            self._jump_to_settings_section("ИСТОРИЯ ЧАТОВ")
        elif name == "SET":
            self.ensure_full_ui()
            self.open_settings_section(3)
        elif name == "AGENTS":
            self.show_panel_dialog("ДОСТУПНЫЕ АГЕНТЫ", [
                "Main Agent", "Planner", "Executor", "Critic", "File",
                "Network", "Web", "Vision", "Memory", "Performance",
                "Game Coach", "Social", "Policy", "Selfcheck",
            ])
        elif name == "FUNCTION":
            self.ensure_full_ui()
            self.open_settings_section(7)
        elif name == "PROV":
            self.ensure_full_ui()
            self.open_settings_section(5)
        elif name == "MOD":
            self.ensure_full_ui()
            self.open_settings_section(5)
        elif name == "VID":
            self.toggle_widget_mode()
        elif name == "OUT":
            self.toggle_status_widget()

        self.assistant_label.setText(name)

    def show_panel_dialog(self, title, items):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(False)
        dialog.resize(360, 280)
        dialog.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet(self.dialog_stylesheet())
        layout = QVBoxLayout(dialog)
        heading = QLabel(title)
        heading.setObjectName("settingsTitle")
        layout.addWidget(heading)
        for item in items:
            label = QLabel(f"• {item}")
            label.setObjectName("settingsHint")
            layout.addWidget(label)
        close_button = QPushButton("ЗАКРЫТЬ")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        dialog.show()
        self._panel_dialog = dialog

    def dialog_stylesheet(self):
        accent_hover = self.accent_color.lighter(120).name()
        if self.visual_settings["glass_enabled"]:
            popup_background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 rgba(20,20,25,220),stop:0.35 rgba(15,15,20,220),"
                "stop:0.65 rgba(10,10,15,230),stop:1 rgba(30,30,35,220))"
            )
        else:
            popup_background = "rgba(15,15,20,220)"
        return f"""
            QDialog {{ background: {popup_background}; color: {self.text_color_hex};
                border: 1px solid rgba(255,255,255,55); border-radius: 15px; }}
            QMenu {{ background: {popup_background}; color: {self.text_color_hex};
                border: 1px solid rgba(255,255,255,55); border-radius: 15px; padding: 6px; }}
            QLabel, QGroupBox, QCheckBox, QRadioButton {{ color: {self.text_color_hex}; }}
            QGroupBox, QGroupBox#settingsTile {{ border: 1px solid rgba(255,255,255,55); border-radius: 12px;
                margin-top: 10px; padding: 14px 8px 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px;
                color: {self.accent_hex}; }}
            QFrame#settingsTile {{ background: rgba(255,255,255,18); border: 1px solid rgba(255,255,255,45);
                border-radius: 12px; }}
            QPushButton#settingsTileButton {{ background: {self.accent_hex}; color: #071116;
                border: none; border-radius: 9px; padding: 8px 12px; min-height: 20px; }}
            QPushButton, QDialogButtonBox QPushButton {{ background: {self.accent_hex};
                color: #071116; border: none; border-radius: 9px; padding: 8px 18px;
                min-height: 18px; }}
            QPushButton:hover, QDialogButtonBox QPushButton:hover {{ background: {accent_hover}; }}
            QComboBox, QLineEdit, QSpinBox {{ background: rgba(255,255,255,225); color: #111820;
                border: 1px solid rgba(255,255,255,100); border-radius: 7px; padding: 5px; }}
            QComboBox QAbstractItemView {{ background: #171b24; color: #ffffff;
                selection-background-color: {self.accent_hex}; selection-color: #071116; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
                border: 1px solid rgba(255,255,255,100); background: rgba(255,255,255,25); }}
            QCheckBox::indicator:checked {{ background: {self.accent_hex}; border: 1px solid {self.accent_hex}; }}
        """

    def toggle_widget_mode(self):
        """Toggle a transparent HUD-only presentation while keeping voice ready."""
        _ui_trace(
            "widget_mode.toggle.begin",
            current=getattr(self, "widget_mode", False),
            window_geometry=self.geometry().getRect(),
        )
        self.widget_mode = not getattr(self, "widget_mode", False)
        self.main_container.setProperty("widgetMode", self.widget_mode)
        self.main_container.style().unpolish(self.main_container)
        self.main_container.style().polish(self.main_container)
        for widget in getattr(self, "widget_chrome_widgets", []):
            widget.setVisible(not self.widget_mode)
        # Keep native frameless controls hidden in widget mode even after a
        # restore/fullscreen transition recreates their visibility state.
        for widget in (
            getattr(self, "fullscreen_button", None),
            getattr(self, "_window_minimize_button", None),
            getattr(self, "_window_close_button", None),
        ):
            if widget is not None:
                widget.setVisible(not self.widget_mode)
        if self.widget_mode:
            self.setWindowOpacity(1.0)
            self.pages.setCurrentIndex(0)
        else:
            self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        # The root window owns the complete theme.  Do not install a partial
        # stylesheet on main_container: that masks inherited rules and was the
        # source of white/unformatted descendants after mode switches.
        self.apply_styles()
        self.apply_hud_hitbox_offset()
        self.raise_hud_controls()
        self._refresh_sidebar_layout()
        _ui_trace(
            "widget_mode.toggle.end",
            current=self.widget_mode,
            window_geometry=self.geometry().getRect(),
            pinned_geometry=self.pinned_chats_list.geometry().getRect(),
            pinned_viewport=(
                self.pinned_chats_list.viewport().width(),
                self.pinned_chats_list.viewport().height(),
            ),
        )

    def _refresh_sidebar_layout(self):
        """Re-activate the sidebar after visibility changes before first input."""
        main_layout = self.layout()
        container_layout = getattr(self, "main_container", None)
        container_layout = container_layout.layout() if container_layout is not None else None
        if main_layout is not None:
            main_layout.activate()
        if container_layout is not None:
            container_layout.activate()
        sidebar_layout = getattr(self, "sidebar_layout", None)
        if sidebar_layout is not None:
            sidebar_layout.activate()
        for widget in (
            getattr(self, "pinned_chats_list", None),
            getattr(self, "chats_list", None),
        ):
            if widget is not None:
                widget.doItemsLayout()
                widget.updateGeometry()
                widget.viewport().update()
        _ui_trace(
            "sidebar.refresh",
            widget_mode=getattr(self, "widget_mode", None),
            window_geometry=self.geometry().getRect(),
            pinned_geometry=self.pinned_chats_list.geometry().getRect()
            if hasattr(self, "pinned_chats_list") else None,
            pinned_viewport=(self.pinned_chats_list.viewport().width(), self.pinned_chats_list.viewport().height())
            if hasattr(self, "pinned_chats_list") else None,
            pinned_count=self.pinned_chats_list.count() if hasattr(self, "pinned_chats_list") else None,
        )

    def showEvent(self, event):
        """Finalize sidebar geometry after the first native show/layout pass."""
        super().showEvent(event)
        _ui_trace("window.show", geometry=self.geometry().getRect(), widget_mode=getattr(self, "widget_mode", None))
        self._refresh_sidebar_layout()

    def handle_tech_action(self, name):
        """Execute the portable equivalent of each original TECH-A action."""
        try:
            if name == "CFG":
                self.ensure_full_ui()
            bound_name = self.widget_settings.get("actions", {}).get(name, name)
            if bound_name == "CUSTOM":
                self.open_custom_target(self.widget_settings.get("targets", {}).get(name, ""), name)
                return
            if bound_name in TECH_ACTION_BUTTONS and bound_name != name:
                name = bound_name
            if name == "COMP":
                os.startfile("shell:MyComputerFolder")
                message = "Открыт Этот компьютер"
            elif name == "DOCS":
                os.startfile(os.path.join(os.path.expanduser("~"), "Documents"))
                message = "Открыты Документы"
            elif name == "CTRL":
                os.startfile("ms-settings:")
                message = "Открыты Параметры Windows"
            elif name == "DESK":
                self.show_desktop()
                message = "Показан рабочий стол"
            elif name == "XPLR":
                enabled = self.hud.animation.toggle_big_animation()
                message = f"ANI {'ON' if enabled else 'OFF'}"
            elif name == "CHRM":
                browser = self.open_chrome()
                message = f"Открыт {browser}"
            elif name == "GAME":
                game_mode = self.hud.animation.toggle_game_mode()
                message = "GAME MODE" if game_mode else "DESK MODE"
            elif name == "CFG":
                self.menu.setCurrentRow(3)
                message = "Открыты настройки Jarvis"
            else:
                message = f"TECH-A: {name}"
            self.assistant_label.setText(message)
            print(f"TECH-A action: {name} -> {message}")
        except OSError as error:
            message = f"Не удалось выполнить {name}: {error}"
            self.assistant_label.setText(message)
            print(message)

    @staticmethod
    def open_chrome():
        chrome_candidates = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for chrome_path in chrome_candidates:
            if chrome_path and os.path.isfile(chrome_path):
                subprocess.Popen([chrome_path, "--new-window"])
                return "Chrome"
        webbrowser.open("about:blank")
        return "браузер по умолчанию"

    @staticmethod
    def show_desktop():
        try:
            import win32com.client
            win32com.client.Dispatch("Shell.Application").ToggleDesktop()
        except Exception:
            # Fallback for systems without the pywin32 COM wrapper.
            user32 = ctypes.windll.user32
            user32.keybd_event(0x5B, 0, 0, 0)
            user32.keybd_event(0x44, 0, 0, 0)
            user32.keybd_event(0x44, 0, 2, 0)
            user32.keybd_event(0x5B, 0, 2, 0)

    def register_tech_fonts(self):
        families = {}
        font_dir = os.path.join(BASE_DIR, "assets", "fonts")

        for label, filename in TECH_FONT_FILES.items():
            path = os.path.join(font_dir, filename)
            font_id = QFontDatabase.addApplicationFont(path)
            loaded = QFontDatabase.applicationFontFamilies(font_id)
            if loaded:
                families[label] = loaded[0]

        return families

    def apply_font_family(self, label):
        family = self.tech_font_families.get(label)
        if not family:
            return

        self._set_interface_font_family(family)

    def _set_interface_font_family(self, family):
        family = str(family or "").strip()
        if not family:
            return

        self.active_font_family = family
        self.ui_settings.setValue("font_family", family)
        self.apply_application_font()
        if hasattr(self, "hud"):
            self.hud.set_interface_font(family)
        if hasattr(self, "chat_view"):
            self.chat_view.page().runJavaScript(
                "window.applyThemeSettings && window.applyThemeSettings(" +
                # The conversation uses its own readable Codex-like stack;
                # changing the HUD font must not make chat text decorative.
                json.dumps({"font_family": "Inter, Segoe UI, Arial, sans-serif"}, ensure_ascii=False) + ");"
            )
        self._refresh_font_choice_state()

    def _refresh_font_choice_state(self):
        """Keep the visible font chips synchronized with the real active family."""
        for button, family in getattr(self, "_font_choice_buttons", []):
            active = str(family).casefold() == str(self.active_font_family).casefold()
            border = self.accent_hex if active else "transparent"
            background = f"rgba({self.accent_color.red()},{self.accent_color.green()},{self.accent_color.blue()},45)" if active else "transparent"
            button.setStyleSheet(
                f"QPushButton {{ color:{self.accent_hex if active else '#8da1a8'}; "
                f"font-weight:{'700' if active else '400'}; border:1px solid {border}; "
                f"border-radius:6px; padding:2px 7px; background:{background}; }}"
                f"QPushButton:hover {{ color:#eef5f7; border-color:{self.accent_hex}; }}"
            )

    def load_interface_font(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузить шрифт",
            "",
            "Шрифты (*.ttf *.otf *.woff *.woff2)"
        )
        if not path:
            return
        font_id = QFontDatabase.addApplicationFont(path)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            return
        family = families[0]
        self.tech_font_families["Custom"] = family
        self._set_interface_font_family(family)

    def apply_application_font(self):
        """Force the selected family onto existing and future Qt widgets."""
        font = QFont(self.active_font_family, 10)
        QApplication.instance().setFont(font)
        for widget in self.findChildren(QWidget):
            widget_font = widget.font()
            widget_font.setFamily(self.active_font_family)
            widget.setFont(widget_font)
        if hasattr(self, "status_widget"):
            self.status_widget.refresh_style()

    def status_widget_stylesheet(self):
        """Return the main-window glass style for the floating status label."""
        if self.visual_settings["glass_enabled"]:
            background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 rgba(20,20,25,220),stop:0.35 rgba(15,15,20,220),"
                "stop:0.65 rgba(10,10,15,230),stop:1 rgba(30,30,35,220))"
            )
        else:
            background = "rgba(15,15,20,220)"
        return (
            "QLabel { color: " + self.text_color_hex + "; background: " + background + "; "
            "border: none; border-radius: 10px; "
            "padding: 4px; font-family: '" + self.active_font_family + "'; font-size: 12px; }"
        )

    def apply_visual_settings(self):
        """Apply the existing main-window glass parameters to every popup."""
        if hasattr(self, "transparent_background_check"):
            self.visual_settings["transparent_background"] = self.transparent_background_check.isChecked()
            self.visual_settings["glass_enabled"] = self.glass_enabled_check.isChecked()
            self.visual_settings["window_opacity"] = self.window_opacity_spin.value()
            if hasattr(self, "glass_hint"):
                self.glass_hint.setText("Включено" if self.visual_settings["glass_enabled"] else "Выключено")
        for key, value in self.visual_settings.items():
            self.ui_settings.setValue(key, value)
        self.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        if hasattr(self, "status_widget"):
            self.status_widget.refresh_style()
        if hasattr(self, "detached_weather"):
            self.detached_weather.card.setStyleSheet(self.detached_weather._card_stylesheet())
        if hasattr(self, "main_container"):
            self.apply_styles()
        if hasattr(self, "status_widget"):
            self.status_widget.refresh_style()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog):
                widget.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
                widget.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
                widget.setStyleSheet(self.dialog_stylesheet())

    def _set_window_opacity_from_slider(self, value):
        value = max(20, min(100, int(value)))
        self.window_opacity_spin.blockSignals(True)
        self.window_opacity_spin.setValue(value)
        self.window_opacity_spin.blockSignals(False)
        self.visual_settings["window_opacity"] = value
        self.ui_settings.setValue("window_opacity", value)
        self.ui_settings.sync()
        self.setWindowOpacity(value / 100.0)

    def apply_datetime_settings(self):
        """Persist and apply the general clock/date presentation settings."""
        self.datetime_settings = {
            "time_format": self.time_format_combo.currentData(),
            "date_format": self.date_format_combo.currentData(),
            "time_size": self.time_size_spin.value(),
            "date_size": self.date_size_spin.value(),
        }
        for key, value in self.datetime_settings.items():
            self.ui_settings.setValue(key, value)
        if hasattr(self, "hud"):
            self.hud.set_datetime_settings(self.datetime_settings)

    def set_startup_diagnostic_enabled(self, enabled):
        self.ui_settings.setValue("startup_diagnostic_enabled", bool(enabled))

    def set_startup_widget_mode(self, enabled):
        self.startup_widget_mode = bool(enabled)
        self.ui_settings.setValue("startup_widget_mode", self.startup_widget_mode)

    def set_windows_autostart(self, enabled):
        """Manage the optional HKCU startup entry without administrator rights."""
        try:
            actual = set_windows_autostart(bool(enabled))
            if hasattr(self, "windows_autostart_check"):
                self.windows_autostart_check.blockSignals(True)
                self.windows_autostart_check.setChecked(actual)
                self.windows_autostart_check.blockSignals(False)
            self.assistant_label.setText(
                "Автозапуск Windows включён" if actual else "Автозапуск Windows выключен"
            )
        except (OSError, ImportError) as error:
            if hasattr(self, "windows_autostart_check"):
                self.windows_autostart_check.blockSignals(True)
                self.windows_autostart_check.setChecked(False)
                self.windows_autostart_check.blockSignals(False)
            self.assistant_label.setText(f"Автозапуск недоступен: {error}")

    @staticmethod
    def enumerate_audio_sources():
        sources = [("Системный выбор", -1)]
        try:
            import sounddevice as sd
            for index, device in enumerate(sd.query_devices()):
                if device.get("max_input_channels", 0) > 0:
                    sources.append((f"{index}: {device['name']}", index))
        except Exception as error:
            print(f"Audio device enumeration failed: {error}")
        return sources

    @staticmethod
    def enumerate_video_sources(preferred_index=0):
        """Return the configured camera without probing hardware at startup.

        Opening several DirectShow indices synchronously while constructing
        the settings page delayed the first HUD and produced repeated
        ``VideoCapture`` backend errors on machines without those devices.
        Actual availability is checked by the on-demand device capability and
        snapshot endpoints; the selected index remains editable here.
        """
        try:
            index = int(preferred_index)
        except (TypeError, ValueError):
            index = 0
        if index < 0:
            index = 0
        return [(f"Камера {index} (проверка по запросу)", index)]

    def apply_hardware_settings(self):
        if not hasattr(self, "audio_source_combo") or not hasattr(self, "video_source_combo"):
            return
        self.hardware_settings = {
            "audio_input_device": self.audio_source_combo.currentData(),
            "video_input_device": self.video_source_combo.currentData(),
        }
        for key, value in self.hardware_settings.items():
            self.ui_settings.setValue(key, value)
        try:
            requests.post(
                f"{API_ROOT}/hardware/settings",
                json=self.hardware_settings,
                timeout=2,
            )
        except requests.RequestException:
            print("Hardware settings saved locally; backend is unavailable")

    def _render_voice_model_status(self, data):
        selected = data.get("selected") or {}
        selected_id = str(
            data.get("selected_id") or selected.get("model_id") or "jarvis"
        )
        if hasattr(self, "voice_model_combo"):
            index = self.voice_model_combo.findData(selected_id)
            if index >= 0 and index != self.voice_model_combo.currentIndex():
                self.voice_model_combo.blockSignals(True)
                self.voice_model_combo.setCurrentIndex(index)
                self.voice_model_combo.blockSignals(False)
        if not hasattr(self, "voice_model_status_label"):
            return
        status = str(selected.get("status") or "Статус неизвестен")
        engine = str(selected.get("actual_engine") or selected.get("engine") or "")
        message = str(selected.get("message") or "")
        self.voice_model_status_label.setText(
            f"{status}. Фактический движок: {engine or 'не запущен'}. {message}"
        )

    def apply_voice_model_setting(self):
        if not hasattr(self, "voice_model_combo"):
            return
        model_id = str(self.voice_model_combo.currentData() or "fish_jarvis")
        self.ui_settings.setValue("voice_model_id", model_id)
        self.ui_settings.sync()
        try:
            response = requests.post(
                f"{API_ROOT}/voice/model",
                json={"model_id": model_id},
                timeout=3,
            )
            response.raise_for_status()
            self._render_voice_model_status(response.json())
        except (requests.RequestException, ValueError) as error:
            self.voice_model_status_label.setText(
                f"Выбор сохранён локально; backend недоступен: {error}"
            )

    def sync_voice_model(self):
        """Apply the persisted UI selection to the live backend runtime."""
        if not hasattr(self, "voice_model_combo"):
            return
        model_id = str(
            self.ui_settings.value("voice_model_id", "fish_jarvis") or "fish_jarvis"
        ).strip().lower()
        index = self.voice_model_combo.findData(model_id)
        if index < 0:
            model_id = "fish_jarvis"
            index = self.voice_model_combo.findData(model_id)
            self.ui_settings.setValue("voice_model_id", model_id)
            self.ui_settings.sync()
        if index >= 0 and index != self.voice_model_combo.currentIndex():
            self.voice_model_combo.blockSignals(True)
            self.voice_model_combo.setCurrentIndex(index)
            self.voice_model_combo.blockSignals(False)
        try:
            response = requests.post(
                f"{API_ROOT}/voice/model",
                json={"model_id": model_id},
                timeout=3,
            )
            response.raise_for_status()
            self._render_voice_model_status(response.json())
        except (requests.RequestException, ValueError) as error:
            self.voice_model_status_label.setText(
                f"Сохранённый профиль: {model_id}. Backend пока недоступен: {error}"
            )

    def pick_color(self, initial, title):
        dialog = QColorDialog(initial, self)
        dialog.setWindowFlag(Qt.WindowType.Dialog, True)
        dialog.setWindowTitle(title)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        # A translucent child dialog lets mouse events fall through to the
        # main window on Windows.  That was opening the assistant widget when
        # the user clicked OK.  Keep the dialog opaque and application-modal.
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setModal(True)
        dialog.setStyleSheet("""
            QColorDialog, QDialog { background:#171922; color:#F4F7FA; }
            QColorDialog QLabel, QDialog QLabel { color:#F4F7FA; }
            QColorDialog QSpinBox, QColorDialog QLineEdit {
                background:#252A36; color:#F4F7FA; border:1px solid #4A5263;
                border-radius:5px; padding:3px;
            }
            QColorDialog QPushButton {
                background:#27303D; color:#F4F7FA; border:1px solid #566176;
                border-radius:6px; padding:6px 14px;
            }
            QColorDialog QPushButton:hover { background:#3A4658; }
        """)
        result = dialog.exec()
        return dialog.selectedColor() if result == QDialog.DialogCode.Accepted else QColor()

    def choose_accent_color(self):
        color = self.pick_color(self.accent_color, "Выберите акцентный цвет")
        if not color.isValid():
            return

        self._set_accent_palette(color.name())

    def pick_glass_tint(self):
        current = QColor(self.visual_settings.get("glass_tint", "#00AAFF"))
        color = self.pick_color(current, "Выберите оттенок стекла")
        if color.isValid():
            self._set_glass_tint(color.name())

    def _set_accent_palette(self, value):
        color = QColor(str(value))
        if not color.isValid():
            return

        self.accent_color = color
        self.accent_hex = color.name()
        self.ui_settings.setValue("accent_color", self.accent_hex)
        self.hud.set_accent_color(color)
        self.jarvis_button.set_accent_color(color)
        self._refresh_start_button_style()
        for toggle in getattr(self, "sidebar_toggles", []):
            toggle.set_accent_color(color)
        # ProviderSwitch paints its own Figma control and therefore does not
        # inherit the stylesheet accent replacement used by the rest of the
        # settings page.  Refresh every live switch explicitly.
        for provider_switch in self.findChildren(ProviderSwitch):
            provider_switch.accent_color = QColor(color)
            provider_switch.update()
        self.accent_value_label.setText(
            f"{self.accent_hex.upper()}  RGB {color.red()}, {color.green()}, {color.blue()}"
        )
        self.apply_styles()
        self._refresh_font_choice_state()
        if hasattr(self, "general_page"):
            self.general_page.style().unpolish(self.general_page)
            self.general_page.style().polish(self.general_page)
            self.general_page.update()
        self._refresh_chat_identity()
        self._refresh_active_chat_visuals()

    def _set_glass_tint(self, value):
        """Change the Glass surface tint without changing the UI accent."""
        color = QColor(str(value))
        if not color.isValid():
            return
        self.visual_settings["glass_tint"] = color.name().upper()
        self.ui_settings.setValue("glass_tint", self.visual_settings["glass_tint"])
        self.apply_styles()
        if hasattr(self, "status_widget"):
            self.status_widget.refresh_style()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog):
                widget.setStyleSheet(self.dialog_stylesheet())

    def _refresh_start_button_style(self):
        """Rebuild the START sphere palette from the current accent color."""
        if not hasattr(self, "jarvis_button"):
            return
        accent = QColor(self.accent_color)
        light = accent.lighter(155).name()
        mid = accent.lighter(115).name()
        dark = accent.darker(220).name()
        deep = accent.darker(360).name()
        hover_light = accent.lighter(175).name()
        hover_mid = accent.lighter(130).name()
        self.jarvis_button.setStyleSheet(f"""
            QPushButton#jarvisStart {{
                color: {self.text_color_hex}; border-radius: 75px;
                border: 1px solid {accent.name()};
                background: qradialgradient(cx:0.5, cy:0.42, radius:0.62,
                    stop:0 {light}, stop:0.34 {mid}, stop:0.72 {dark}, stop:1 {deep});
            }}
            QPushButton#jarvisStart:hover {{
                border: 2px solid {hover_light};
                background: qradialgradient(cx:0.5, cy:0.42, radius:0.62,
                    stop:0 {hover_light}, stop:0.34 {hover_mid}, stop:1 {deep});
            }}
        """)
        self.jarvis_button.style().unpolish(self.jarvis_button)
        self.jarvis_button.style().polish(self.jarvis_button)
        self.jarvis_button.update()
        if hasattr(self, "glow"):
            self.glow.setColor(accent)

    def choose_text_color(self):
        color = self.pick_color(self.text_color, "Выберите цвет текста")
        if not color.isValid():
            return

        self.text_color = color
        self.text_color_hex = color.name()
        self.ui_settings.setValue("font_color", self.text_color_hex)
        self.hud.set_text_color(color)
        self.jarvis_button.set_text_color(color)
        self.font_color_value_label.setText(
            f"{self.text_color_hex.upper()}  RGB {color.red()}, {color.green()}, {color.blue()}"
        )
        self.apply_styles()


    # ---------------- HOVER MENU BUTTON ----------------

    def eventFilter(self, obj, event):

        if (event.type() == QEvent.Type.MouseButtonPress
                and os.getenv("JARVIS_UI_TRACE")
                and obj is self.windowHandle()):
            global_pos = event.globalPosition().toPoint()
            hit = QApplication.widgetAt(global_pos)

            def global_bounds(widget):
                if widget is None:
                    return None
                origin = widget.mapToGlobal(QPoint(0, 0))
                return (origin.x(), origin.y(), widget.width(), widget.height())

            hit_path = []
            node = hit
            while node is not None and len(hit_path) < 6:
                hit_path.append(f"{type(node).__name__}:{node.objectName()}")
                node = node.parentWidget()
            _ui_trace(
                "input.press",
                receiver=f"{type(obj).__name__}:{obj.objectName()}",
                hit=f"{type(hit).__name__}:{hit.objectName()}" if hit else None,
                hit_path=hit_path,
                global_pos=(global_pos.x(), global_pos.y()),
                window_geometry=self.geometry().getRect(),
                window_state=int(self.windowState().value),
                menu_bounds=global_bounds(getattr(self, "menu", None)),
                settings_nav_bounds=global_bounds(getattr(self, "settings_nav", None)),
                settings_scroll_bounds=global_bounds(getattr(self, "settings_scroll", None)),
            )

        # Never route events from a modal dialog through the HUD fallback.
        # The fallback is application-wide and otherwise interprets the
        # color picker's OK click as a click on the underlying VID cell.
        if QApplication.activeModalWidget() is not None:
            return super().eventFilter(obj, event)

        # QApplication-level fallback catches presses delivered to decorative
        # HUD children instead of the visible panel button.  Activating on
        # press makes the whole cell responsive in transparent widget mode;
        # the matching release is consumed to avoid a second activation.
        if event.type() == QEvent.Type.MouseButtonPress:
            if self.handle_hud_global_press(event):
                return True
        if event.type() == QEvent.Type.MouseButtonRelease and getattr(
            self, "_hud_fallback_pressed_button", None
        ) is not None:
            self._hud_fallback_pressed_button = None
            return True

        # Keep the release fallback for platforms/layers that do not deliver
        # the press to the application filter.
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and obj not in (
                getattr(self, "hud", None),
                getattr(self, "hud_container", None),
            )
            and obj not in getattr(self, "hud_panel_button_map", {}).values()
        ):
            if self.handle_hud_global_release(event):
                return True

        if obj in (getattr(self, "hud", None), getattr(self, "hud_container", None)):
            if event.type() == QEvent.Type.MouseButtonRelease:
                if self.handle_hud_background_release(event):
                    return True

        if obj in (getattr(self, "chat_header", None), getattr(self, "chat_avatar", None),
                   getattr(self, "chat_title", None), getattr(self, "chat_subtitle", None)):
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.show_chat_profile()
                return True

        if self.panel_calibration_mode and obj in getattr(self, "hud_panel_button_map", {}).values():
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._panel_drag = (obj, event.position().toPoint(), obj.pos())
                return True
            if event.type() == QEvent.MouseMove and self._panel_drag:
                dragged, start, origin = self._panel_drag
                delta = event.position().toPoint() - start
                dragged.move(origin + delta)
                return True
            if event.type() == QEvent.MouseButtonRelease and self._panel_drag:
                dragged, start, _ = self._panel_drag
                self._panel_drag = None
                delta = event.position().toPoint() - start
                if delta.manhattanLength() <= 6:
                    # Calibration consumes the native press/release pair so
                    # it can distinguish a drag. Re-emit a stationary click
                    # explicitly; otherwise the first click only arms the
                    # drag state and the user has to click twice.
                    dragged.click()
                else:
                    self.save_panel_position(dragged)
                return True

        chat_viewports = {
            getattr(self, "pinned_chats_list", None).viewport() if hasattr(self, "pinned_chats_list") else None,
            getattr(self, "chats_list", None).viewport() if hasattr(self, "chats_list") else None,
        }
        if obj in chat_viewports:
            list_widget = obj.parentWidget()

            if event.type() == QEvent.MouseMove:

                pos = event.pos()

                for i in range(list_widget.count()):

                    item = list_widget.item(i)
                    widget = list_widget.itemWidget(item)

                    if not widget or not hasattr(widget, "menu_btn"):
                        continue

                    rect = list_widget.visualItemRect(item)

                    if rect.contains(pos):
                        widget.menu_btn.show()
                    else:
                        widget.menu_btn.hide()

            elif event.type() == QEvent.Leave:

                for i in range(list_widget.count()):

                    item = list_widget.item(i)
                    widget = list_widget.itemWidget(item)

                    if widget and hasattr(widget, "menu_btn"):
                        widget.menu_btn.hide()

        return super().eventFilter(obj, event)

    def save_panel_position(self, button):
        for name, candidate in self.hud_panel_button_map.items():
            if candidate is button:
                anchor_offset_x = int(button.property("panelAnchorOffsetX") or 0)
                anchor_offset_y = int(button.property("panelAnchorOffsetY") or 0)
                anchor_x = int(button.x()) + anchor_offset_x
                anchor_y = int(button.y()) + anchor_offset_y
                button.setProperty("panelAnchorX", anchor_x)
                button.setProperty("panelAnchorY", anchor_y)
                # apply_hud_hitbox_offset() reapplies the stored base geometry
                # after mode switches; keep that base in sync with calibration.
                button.setProperty("hitboxBaseX", int(button.x()))
                button.setProperty("hitboxBaseY", int(button.y()))
                saved_position = {
                    "x": anchor_x,
                    "y": anchor_y,
                    "angle": round(getattr(button, "panel_angle", 0), 1),
                }
                if isinstance(button, RotatablePanelButton):
                    saved_position["font_size"] = int(button.panel_font_size)
                profiles = self.widget_settings.setdefault("panel_positions_by_mode", {})
                profiles.setdefault(self.panel_calibration_profile, {})[name] = saved_position
                # Keep the legacy key synchronized only for the accepted
                # widget profile. Fullscreen calibration remains independent.
                if self.panel_calibration_profile == "widget":
                    self.widget_settings.setdefault("panel_positions", {})[name] = saved_position
                self.ui_settings.setValue(
                    "widget_settings",
                    json.dumps(self.widget_settings, ensure_ascii=False),
                )
                print(f"Panel anchor saved: {name} -> ({anchor_x}, {anchor_y})")
                return


    # ---------------- CHAT MENU ----------------

    def chat_menu(self, pos, list_widget=None):

        list_widget = list_widget or self.sender()
        if not isinstance(list_widget, QListWidget):
            list_widget = self.chats_list
        item = list_widget.itemAt(pos)

        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return

        menu = QMenu(self)

        menu.setStyleSheet(f"""
        QMenu{{
        background:#1c1c24;
        border:1px solid rgba(255,255,255,40);
        border-radius:15px;
        color:white;
        padding:6px;
        }}

        QMenu::item{{
        padding:6px 8px;
        border-radius:6px;
        }}

        QMenu::item:selected{{
        background:{self.accent_hex};
        }}
        """)

        pin_icon = QIcon(os.path.join(BASE_DIR,"assets","pin.svg"))
        edit_icon = QIcon(os.path.join(BASE_DIR,"assets","pencil.svg"))
        del_icon = QIcon(os.path.join(BASE_DIR,"assets","trash.svg"))

        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        widget = list_widget.itemWidget(item)
        pixmap = widget.pin.pixmap() if widget is not None else None
        is_pinned = bool(pixmap is not None and not pixmap.isNull())
        pin_action = menu.addAction(pin_icon, "Открепить" if is_pinned else "Закрепить")
        rename_action = menu.addAction(edit_icon,"Переименовать")
        clear_action = menu.addAction("Очистить историю")
        archive_action = menu.addAction("Архивировать")
        delete_action = menu.addAction(del_icon,"Удалить")

        action = menu.exec(list_widget.mapToGlobal(pos))

        if action == pin_action:
            self.pin_chat(item)

        elif action == rename_action:
            self.rename_chat(item)

        elif action == clear_action:
            self.clear_chat_history(item)

        elif action == archive_action:
            self.archive_chat(item)

        elif action == delete_action:
            self.delete_chat(item)


    # ---------------- PIN CHAT ----------------

    def pin_chat(self, item):

        list_widget = item.listWidget() or self.chats_list
        widget = list_widget.itemWidget(item)

        if not widget:
            return

        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        try:
            response = requests.post(f"{API_ROOT}/chat/sessions/{chat_id}/pin", timeout=4)
            response.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                self.show_chat_notice(
                    "Закреплённые чаты",
                    "Можно закрепить не более четырёх чатов.",
                )
            return
        except requests.RequestException:
            return

        self.load_chat_sessions()

    def show_chat_notice(self, title: str, text: str, *, error: bool = False) -> None:
        """Show readable Jarvis-styled feedback instead of a native white box."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(str(title))
        dialog.setText(str(text))
        dialog.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.button(QMessageBox.StandardButton.Ok).setText("Понятно")
        dialog.setStyleSheet(f"""
            QMessageBox {{ background:#12151c; color:{self.text_color_hex}; }}
            QLabel {{ color:{self.text_color_hex}; min-width:340px; min-height:32px; }}
            QPushButton {{ background:#00aaff; color:#071116; border:none;
                border-radius:9px; padding:7px 18px; min-width:92px; }}
            QPushButton:hover {{ background:#32c8ff; }}
        """)
        dialog.exec()


    # ---------------- RENAME CHAT ----------------

    def rename_chat(self, item):

        list_widget = item.listWidget() or self.chats_list
        widget = list_widget.itemWidget(item)

        if not widget:
            return

        dialog = QInputDialog(self)
        dialog.setObjectName("renameChatDialog")
        dialog.setWindowTitle("Переименовать чат")
        dialog.setLabelText("Новое название:")
        dialog.setTextValue(widget.label.text())
        dialog.setOkButtonText("Сохранить")
        dialog.setCancelButtonText("Отмена")
        dialog.setStyleSheet(f"""
            QInputDialog#renameChatDialog {{
                background: #12151c; color: {self.text_color_hex};
                border: 1px solid rgba(0,170,255,150); border-radius: 15px;
            }}
            QInputDialog#renameChatDialog QLabel {{ color: {self.text_color_hex}; font-size: 13px; }}
            QInputDialog#renameChatDialog QLineEdit {{
                background: rgba(255,255,255,18); color: {self.text_color_hex};
                border: 1px solid rgba(0,170,255,150); border-radius: 8px;
                padding: 7px 9px;
            }}
            QInputDialog#renameChatDialog QPushButton {{
                background: #00aaff; color: #071116; border: none;
                border-radius: 9px; padding: 7px 16px; min-width: 88px;
            }}
            QInputDialog#renameChatDialog QPushButton:hover {{ background: #32c8ff; }}
        """)
        dialog.resize(390, 150)
        ok = dialog.exec() == QDialog.DialogCode.Accepted
        text = dialog.textValue().strip()

        if ok and text:
            widget.label.setText(text)
            chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
            try:
                requests.patch(
                    f"{API_ROOT}/chat/sessions/{chat_id}",
                    json={"title": text},
                    timeout=4,
                ).raise_for_status()
            except requests.RequestException:
                pass

    def clear_chat_history(self, item):
        list_widget = item.listWidget() or self.chats_list
        widget = list_widget.itemWidget(item)
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        title = widget.label.text() if widget else "этот чат"
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Очистить историю")
        dialog.setText(f"Очистить всю историю чата «{title}»?")
        dialog.setInformativeText("Сам чат и его название останутся.")
        dialog.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
        dialog.button(QMessageBox.StandardButton.Ok).setText("Очистить")
        dialog.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
        dialog.setStyleSheet(f"""
            QMessageBox {{ background:#12151c; color:{self.text_color_hex}; }}
            QLabel {{ color:{self.text_color_hex}; min-width:320px; }}
            QPushButton {{ background:rgba(255,255,255,18); color:{self.text_color_hex};
                border:1px solid rgba(0,170,255,150); border-radius:9px; padding:7px 16px; }}
            QPushButton:hover {{ background:#00aaff; color:#071116; }}
        """)
        if dialog.exec() != QMessageBox.StandardButton.Ok:
            return
        try:
            requests.delete(f"{API_ROOT}/chat/sessions/{chat_id}/messages", timeout=4).raise_for_status()
        except requests.RequestException:
            return
        if str(getattr(self, "current_chat_id", "default")) == chat_id:
            self.chat_view.page().runJavaScript("window.loadMessages && window.loadMessages([]);")
            self.chat_view.page().runJavaScript(
                "window.startPolling && window.startPolling(" + json.dumps(chat_id) + ");"
            )


    # ---------------- DELETE CHAT ----------------

    def delete_chat(self, item):
        list_widget = item.listWidget() or self.chats_list
        row = list_widget.row(item)
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        widget = list_widget.itemWidget(item)
        title = widget.label.text() if widget else "этот чат"

        dialog = QDialog(self)
        dialog.setObjectName("deleteChatDialog")
        dialog.setWindowTitle("Удалить чат")
        dialog.setModal(True)
        dialog.setFixedSize(430, 190)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        # This confirmation must be an opaque modal surface.  Inheriting the
        # translucent window treatment from the HUD makes the desktop and
        # chat list show through the delete action, reducing readability and
        # making the modal boundary look broken.
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        dialog.setAutoFillBackground(True)
        dialog.setStyleSheet(f"""
            QDialog#deleteChatDialog {{
                background: #12151c;
                color: {self.text_color_hex};
                border: 1px solid #4b5563;
                border-radius: 15px;
            }}
            QLabel#deleteTitle {{ color: {self.text_color_hex}; font-size: 17px; font-weight: 700; }}
            QLabel#deleteText {{ color: rgba(244,247,250,205); font-size: 13px; }}
            QPushButton {{ min-width: 92px; min-height: 34px; padding: 0 16px;
                border-radius: 9px; border: 1px solid rgba(255,255,255,35);
                color: {self.text_color_hex}; background: rgba(255,255,255,16); }}
            QPushButton:hover {{ background: rgba(255,255,255,28); }}
            QPushButton#deleteConfirm {{ background: #d94b5b; border: none; color: white; }}
            QPushButton#deleteConfirm:hover {{ background: #ed6271; }}
        """)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)
        title_label = QLabel("Удалить чат?")
        title_label.setObjectName("deleteTitle")
        message_label = QLabel(f"Удалить «{title}» вместе со всей историей?")
        message_label.setObjectName("deleteText")
        message_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("Отмена")
        delete_button = QPushButton("Удалить")
        delete_button.setObjectName("deleteConfirm")
        cancel_button.clicked.connect(dialog.reject)
        delete_button.clicked.connect(dialog.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(delete_button)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            requests.delete(f"{API_ROOT}/chat/sessions/{chat_id}", timeout=4).raise_for_status()
        except requests.RequestException:
            return
        list_widget.takeItem(row)

    def archive_chat(self, item):
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        try:
            requests.post(
                f"{API_ROOT}/chat/sessions/{chat_id}/archive",
                timeout=4,
            ).raise_for_status()
        except requests.RequestException:
            return
        self.chats_list.takeItem(self.chats_list.row(item))


    # ---------------- ADD CHAT ITEM ----------------

    def add_chat_item(self, text, pinned=False, chat_id="default", list_widget=None):

        list_widget = list_widget or self.chats_list

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, str(chat_id))

        chat_id = str(chat_id)
        widget = ChatItemWidget(text, pinned, mode=getattr(self, "_session_modes", {}).get(chat_id))
        widget.set_unread(
            chat_id in getattr(self, "_unread_chat_ids", set())
            and chat_id != str(getattr(self, "current_chat_id", "default")),
            self.accent_hex,
        )

        # Keep the QListWidget item geometry aligned with ChatItemWidget.
        # A larger item hint made the fourth card spill into the scrollbar
        # area even though the widget itself was visually reduced to 32 px.
        item.setSizeHint(QSize(max(1, list_widget.viewport().width() - 8), 26))

        _ui_trace(
            "chat_item.add",
            pinned=pinned,
            chat_id=chat_id,
            viewport=(list_widget.viewport().width(), list_widget.viewport().height()),
            list_geometry=list_widget.geometry().getRect(),
            item_width=item.sizeHint().width(),
        )

        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)

        widget.menu_btn.clicked.connect(
            lambda: self.chat_menu(list_widget.visualItemRect(item).center(), list_widget)
        )

    def load_chat_sessions(self):
        if self._closing_after_jobs:
            return
        _ui_trace("chat_sessions.load.begin")
        if self._sessions_read_pending:
            self._sessions_reload_requested = True
            return
        self._sessions_read_pending = True
        self._run_network_operation("sessions", self._apply_chat_sessions, self._chat_sessions_failed)

    def _apply_chat_sessions(self, data):
        self._sessions_read_pending = False
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
            self._chat_sessions_failed("некорректный ответ backend")
            return
        sessions = data["sessions"]
        self.pinned_chats_list.clear()
        self.chats_list.clear()
        self._session_modes = {
            str(session.get("id") or "default"): session.get("mode")
            for session in sessions
            if isinstance(session, dict)
        }
        pinned_sessions = [session for session in sessions if bool(session.get("pinned"))][:4]
        recent_limit = 8 if bool(
            getattr(self, "_fullscreen_mode", False) or self.isMaximized() or self.isFullScreen()
        ) else 4
        recent_sessions = [session for session in sessions if not bool(session.get("pinned"))]
        activity = getattr(self, "_recent_chat_activity", {})
        recent_sessions.sort(
            key=lambda session: activity.get(str(session.get("id") or "default"), 0),
            reverse=True,
        )
        recent_sessions = recent_sessions[:recent_limit]

        for session in pinned_sessions:
            self.add_chat_item(
                str(session.get("title") or "Новый чат"),
                True,
                str(session.get("id") or "default"),
                self.pinned_chats_list,
            )
        if recent_sessions:
            for session in recent_sessions:
                self.add_chat_item(
                    str(session.get("title") or "Новый чат"),
                    False,
                    str(session.get("id") or "default"),
                )
        if not pinned_sessions and not recent_sessions:
            self.add_chat_item("JARVIS CHAT", chat_id="default")
        current_chat_id = str(getattr(self, "current_chat_id", "default"))
        for list_widget in (self.pinned_chats_list, self.chats_list):
            for index in range(list_widget.count()):
                item = list_widget.item(index)
                if str(item.data(Qt.ItemDataRole.UserRole) or "") == current_chat_id:
                    list_widget.setCurrentItem(item)
                widget = list_widget.itemWidget(item)
                if isinstance(widget, ChatItemWidget):
                    item_chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
                    widget.set_active(item_chat_id == current_chat_id, self.accent_hex)
                    widget.set_unread(
                        item_chat_id in getattr(self, "_unread_chat_ids", set()),
                        self.accent_hex,
                    )
        _ui_trace(
            "chat_sessions.load.end",
            pinned_count=self.pinned_chats_list.count(),
            recent_count=self.chats_list.count(),
            pinned_geometry=self.pinned_chats_list.geometry().getRect(),
            pinned_viewport=(self.pinned_chats_list.viewport().width(), self.pinned_chats_list.viewport().height()),
        )
        self._refresh_sidebar_layout()
        if self._sessions_reload_requested:
            self._sessions_reload_requested = False
            self.load_chat_sessions()

    def _chat_sessions_failed(self, error):
        self._sessions_read_pending = False
        _ui_trace("chat_sessions.load.failed", error=error)
        if not self.pinned_chats_list.count() and not self.chats_list.count():
            unavailable = QListWidgetItem("Список чатов недоступен")
            unavailable.setFlags(Qt.ItemFlag.NoItemFlags)
            self.chats_list.addItem(unavailable)
        if self._sessions_reload_requested:
            self._sessions_reload_requested = False
            self.load_chat_sessions()

    def _run_network_operation(self, operation, callback, error_callback, *, params=None, payload=None):
        """Run a bounded network operation and deliver its result on the GUI thread."""
        return start_network_operation(
            self,
            operation,
            callback,
            error_callback,
            self._network_jobs,
            payload=payload,
            params=params,
            completion_callback=self._network_operation_finished,
        )

    def _prune_network_jobs(self):
        """Keep jobs until their GUI-thread completion callback releases them.

        A Python request can finish before its queued result callback is
        delivered. Pruning on thread liveness would drop that callback's Qt
        objects while the event is still pending.
        """
        return

    def _network_operation_finished(self, job_token=None):
        # Remove only the job whose QThread emitted finished. Scanning every
        # active QThread with isRunning() from a queued finish callback raced
        # with concurrent SSL/COM work and produced a native access violation.
        if job_token is None:
            JarvisUI._prune_network_jobs(self)
        else:
            self._network_jobs = [
                job for job in self._network_jobs
                if len(job) < 4 or job[3] is not job_token
            ]
        _ui_trace("network_job.finished", active_jobs=len(self._network_jobs))
        if self._closing_after_jobs and not self._network_jobs:
            QTimer.singleShot(0, self.close)

    def _refresh_active_chat_visuals(self) -> None:
        """Keep pinned and recent chat cards in sync with current_chat_id."""
        current_chat_id = str(getattr(self, "current_chat_id", "default"))
        for list_widget in (
            getattr(self, "pinned_chats_list", None),
            getattr(self, "chats_list", None),
        ):
            if list_widget is None:
                continue
            for index in range(list_widget.count()):
                item = list_widget.item(index)
                widget = list_widget.itemWidget(item)
                if isinstance(widget, ChatItemWidget):
                    item_chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
                    widget.set_active(item_chat_id == current_chat_id, self.accent_hex)
                    widget.set_unread(
                        item_chat_id in getattr(self, "_unread_chat_ids", set()),
                        self.accent_hex,
                    )

    def select_chat_item(self, item):
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        self._stop_voice_chat_before_switch(chat_id)
        self.current_chat_id = chat_id
        self._unread_chat_ids.discard(chat_id)
        self._refresh_active_chat_visuals()
        # Chat cards live outside the main navigation QListWidget.  Clear the
        # previous navigation selection so that opening a chat from the pinned
        # or recent lists cannot leave "Настройки" highlighted on top of the
        # chat page.
        if hasattr(self, "menu"):
            blocked = self.menu.blockSignals(True)
            self.menu.setCurrentRow(-1)
            self.menu.blockSignals(blocked)
        self.set_settings_header_visible(False)
        self.pages.setCurrentIndex(1)
        self.chat_view.page().runJavaScript(
            "window.setCurrentChatId && window.setCurrentChatId(" + json.dumps(chat_id) + ");"
        )
        self.load_chat_history()

    def load_history_sessions(self):
        if not hasattr(self, "history_list"):
            return
        self._history_sessions_generation += 1
        generation = self._history_sessions_generation
        self.history_hint.setText("Загрузка истории чатов…")
        self.refresh_history_button.setEnabled(False)
        self._run_network_operation(
            "history-sessions",
            lambda data: self._apply_history_sessions(data, generation),
            lambda error: self._history_sessions_failed(error, generation),
        )

    def _history_sessions_failed(self, _error, generation):
        if generation != self._history_sessions_generation:
            return
        self.refresh_history_button.setEnabled(True)
        self.history_hint.setText("Не удалось обновить историю. Нажмите «ОБНОВИТЬ» для повтора.")

    def _apply_history_sessions(self, data, generation):
        if generation != self._history_sessions_generation:
            return
        sessions = data.get("sessions") if isinstance(data, dict) else None
        if not isinstance(sessions, list) or any(not isinstance(item, dict) for item in sessions):
            self._history_sessions_failed("invalid response", generation)
            return
        self.refresh_history_button.setEnabled(True)
        self.history_hint.setText("Выберите чат, чтобы открыть его историю")
        self.history_list.clear()
        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(session.get("id") or "default"))
            # Keep an actual right-side gutter: a size hint equal to the viewport
            # width clips the rounded edge at fractional Windows DPI.
            item.setSizeHint(QSize(max(1, self.history_list.viewport().width() - 12), 64))
            row = QWidget()
            row.setObjectName("historyRow")
            row.setProperty(
                "active",
                str(item.data(Qt.ItemDataRole.UserRole)) == str(getattr(self, "current_chat_id", "default")),
            )
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            row.setAutoFillBackground(False)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(16, 9, 16, 9)
            row_layout.setSpacing(3)
            title = QLabel(str(session.get("title") or "Новый чат"))
            title.setStyleSheet("font-size:14px; color:white;")
            details = QLabel(
                "Архив" if session.get("archived") else
                ("Закреплён" if session.get("pinned") else "Недавний")
            )
            details.setStyleSheet("font-size:11px; color:#888;")
            row_layout.addWidget(title)
            row_layout.addWidget(details)
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, row)

    def open_history_chat(self, item):
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        self._stop_voice_chat_before_switch(chat_id)
        self.current_chat_id = chat_id
        self._refresh_active_chat_visuals()
        self.pages.setCurrentIndex(1)
        self.chat_view.page().runJavaScript(
            "window.setCurrentChatId && window.setCurrentChatId(" + json.dumps(chat_id) + ");"
        )
        self.load_chat_history()

    def create_new_chat(self):
        self._stop_voice_chat_before_switch("draft")
        self.current_chat_id = "draft_" + uuid.uuid4().hex
        self._refresh_active_chat_visuals()
        self.pages.setCurrentIndex(1)
        # A new chat must reflect the provider/model saved in AI settings.
        self.load_chat_model()
        self.composer.message_input.clear()
        self.chat_view.page().runJavaScript(
            "window.setCurrentChatId && window.setCurrentChatId(" + json.dumps(self.current_chat_id) + ");"
        )
        self.chat_view.page().runJavaScript("window.loadMessages && window.loadMessages([]);")
        self.chat_view.page().runJavaScript(
            "window.startPolling && window.startPolling(" + json.dumps(self.current_chat_id) + ");"
        )

    def load_chat_model(self):
        """Refresh the chat model through the existing background settings worker."""
        if self._closing_after_jobs:
            return
        self._chat_model_generation += 1
        generation = self._chat_model_generation
        self.chat_model_combo.setEnabled(False)
        self.chat_subtitle.setText("Загрузка провайдера и модели…")
        self._run_network_operation(
            "load",
            lambda data: self._apply_chat_model_settings(generation, data),
            lambda error: self._chat_model_failed(generation, error),
        )

    def _apply_chat_model_settings(self, generation, settings):
        if generation != self._chat_model_generation:
            return
        if not isinstance(settings, dict) or not settings.get("provider"):
            self._chat_model_failed(generation, "некорректный ответ backend")
            return
        provider = str(settings["provider"]).lower()
        connection = settings.get("llm_connection") or {}
        model = str(connection.get("model") or "").strip()
        config = settings.get("config") or {}
        if not model:
            self._chat_model_failed(generation, "активная модель не выбрана")
            return
        base_url_key = {
            "ollama": "HEL_OLLAMA_BASE_URL",
            "deepseek": "HEL_DEEPSEEK_BASE_URL",
            "freellmapi": "HEL_FREELLMAPI_BASE_URL",
        }.get(provider, "")
        base_url = str(config.get(base_url_key) or "")
        self._set_chat_model(provider, model, base_url, [model], config)
        if provider in {"ollama", "deepseek", "freellmapi"}:
            self._run_network_operation(
                "models",
                lambda data: self._apply_chat_model_catalog(generation, data),
                lambda error: self._chat_model_catalog_failed(generation, error),
                params={"provider": provider, "base_url": base_url},
            )

    def _apply_chat_model_catalog(self, generation, data):
        if generation != self._chat_model_generation:
            return
        models = [str(value) for value in data.get("models", []) if value] if isinstance(data, dict) else []
        current = self.chat_model_combo.currentText()
        if current not in models:
            models.insert(0, current)
        self.chat_model_combo.blockSignals(True)
        self.chat_model_combo.clear()
        self.chat_model_combo.addItems(models)
        self.chat_model_combo.setCurrentText(current)
        self.chat_model_combo.blockSignals(False)

    def _chat_model_catalog_failed(self, generation, error):
        if generation == self._chat_model_generation:
            self.chat_subtitle.setText(self.chat_subtitle.text() + f"  |  каталог недоступен: {error}")

    def _chat_model_failed(self, generation, error):
        if generation == self._chat_model_generation:
            self.chat_model_combo.setEnabled(False)
            self.chat_subtitle.setText(f"Не удалось загрузить активную модель: {error}")

    def _set_chat_model(self, provider, model, base_url, models, config):
        self._chat_provider = provider
        self._chat_model_confirmed = model
        self._chat_provider_base_url = str(config.get("HEL_FREELLMAPI_BASE_URL") or base_url)
        self._chat_ollama_base_url = base_url
        self.chat_model_combo.blockSignals(True)
        self.chat_model_combo.clear()
        self.chat_model_combo.addItems(models or [model])
        self.chat_model_combo.setCurrentText(model)
        self.chat_model_combo.blockSignals(False)
        self.chat_model_combo.setEnabled(True)
        self.chat_subtitle.setText(f"Провайдер: {provider.title()}  |  Модель: {model}")
        self._set_chat_status_dot("#00aaff", "Модель готова к работе")

    def on_chat_model_changed(self, model):
        model = str(model or "").strip()
        if not model or not hasattr(self, "_chat_provider"):
            return
        if model == getattr(self, "_chat_model_confirmed", None):
            return
        if self._chat_provider == "ollama":
            payload = {
                "provider": "ollama",
                "ollama_base_url": getattr(self, "_chat_ollama_base_url", "http://127.0.0.1:11434"),
                "ollama_model": model,
            }
        elif self._chat_provider == "freellmapi":
            payload = {
                "provider": "freellmapi",
                "freellmapi_base_url": getattr(self, "_chat_provider_base_url", ""),
                "freellmapi_model": model,
            }
        else:
            return
        self._chat_model_generation += 1
        generation = self._chat_model_generation
        self.chat_model_combo.setEnabled(False)
        self.chat_subtitle.setText(f"Сохраняю модель {model}…")
        def save_failed(error):
            if generation != self._chat_model_generation:
                return
            confirmed = self._chat_model_confirmed
            self.chat_model_combo.blockSignals(True)
            self.chat_model_combo.setCurrentText(confirmed)
            self.chat_model_combo.blockSignals(False)
            self.chat_model_combo.setEnabled(True)
            self.chat_subtitle.setText(f"Модель не сохранена: {error}. Активна {confirmed}.")
        self._run_network_operation(
            "save",
            lambda data: self._apply_chat_model_settings(generation, data),
            save_failed,
            payload=payload,
        )

    # ---------------- UI ----------------

    def build_ui(self):

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("container")
        # The application shell owns the normal window size.  Child pages
        # (including the fixed HUD and long Settings pages) must negotiate
        # their content inside it, never raise the top-level minimum size.
        container.setMinimumSize(0, 0)
        container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.main_container = container
        self.widget_chrome_widgets = []

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 20, 16, 20)

        # ---------- HEADER ----------

        header = QHBoxLayout()

        title = QLabel("JARVIS ASSIST")
        title.setObjectName("title")
        self.widget_chrome_widgets.append(title)

        header.addWidget(title)
        header.addStretch()

        btn_min = QPushButton()
        self.fullscreen_button = QPushButton()
        btn_close = QPushButton()
        self._window_minimize_button = btn_min
        self._window_close_button = btn_close

        btn_min.setFixedSize(32, 32)
        self.fullscreen_button.setFixedSize(32, 32)
        btn_close.setFixedSize(32, 32)
        btn_min.setIcon(QIcon(str(Path(BASE_DIR) / "assets" / "chevron-down.svg")))
        self.fullscreen_button.setIcon(QIcon(str(Path(BASE_DIR) / "assets" / "полноэкранный.svg")))
        btn_close.setIcon(QIcon(str(Path(BASE_DIR) / "assets" / "close.svg")))
        btn_min.setIconSize(QSize(24, 24))
        btn_close.setIconSize(QSize(24, 24))
        btn_min.setToolTip("Свернуть")
        self.fullscreen_button.setToolTip("Развернуть на весь экран")
        btn_close.setToolTip("Закрыть")
        btn_min.setAccessibleName("Свернуть окно")
        btn_close.setAccessibleName("Закрыть окно")
        self.fullscreen_button.setAccessibleName("Полноэкранный режим")

        btn_close.setObjectName("closeBtn")
        self.widget_chrome_widgets.extend([btn_min, self.fullscreen_button, btn_close])

        btn_min.clicked.connect(self.showMinimized)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen_window)
        btn_close.clicked.connect(self.close)

        header.addWidget(btn_min)
        header.addWidget(self.fullscreen_button)
        header.addWidget(btn_close)

        container_layout.addLayout(header)

        # ---------- MAIN ----------

        main = QHBoxLayout()
        main.setSpacing(25)

        # ---------- LEFT PANEL ----------

        left = QVBoxLayout()
        self.sidebar_layout = left
        # Keep the sidebar compact enough for four pinned cards before the
        # recent-chat heading while preserving a small readable separation.
        left.setSpacing(8)

        self.menu = QListWidget()
        self.menu.setAttribute(Qt.WA_StyledBackground, True)
        self.menu.setObjectName("menu")

        self.menu.addItems([
            "АССИСТЕНТ",
            "НОВЫЙ ЧАТ",
            "ВОЗМОЖНОСТИ",
            "НАСТРОЙКИ"
        ])

        self.menu.setFixedWidth(180)
        self.menu.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # The four navigation entries fit in a shorter block; reclaim the
        # unused vertical space so the pinned-chat section can show all four.
        self.menu.setFixedHeight(180)
        self.widget_chrome_widgets.append(self.menu)

        left.addWidget(self.menu)


        # ---------- PINNED CHATS ----------

        # заголовок закреплённых чатов; список ниже не прокручивается
        chats_title = QLabel("Закрепленные чаты")
        chats_title.setStyleSheet("color:#888; font-size:12px;")
        self.widget_chrome_widgets.append(chats_title)

        left.addWidget(chats_title)

        self.pinned_chats_list = QListWidget()
        self.pinned_chats_list.setObjectName("pinnedChatList")
        self.pinned_chats_list.setFrameShape(QFrame.Shape.NoFrame)
        self.pinned_chats_list.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.pinned_chats_list.setAutoFillBackground(False)
        self.pinned_chats_list.setFixedWidth(240)
        self.pinned_chats_list.setFixedHeight(125)
        self.pinned_chats_list.setContentsMargins(0, 0, 0, 0)
        self.pinned_chats_list.setViewportMargins(2, 0, 2, 0)
        self.pinned_chats_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.pinned_chats_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pinned_chats_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pinned_chats_list.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.pinned_chats_list.viewport().setAutoFillBackground(False)
        self.pinned_chats_list.viewport().setStyleSheet("background: transparent; border: none;")
        self.pinned_chats_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pinned_chats_list.customContextMenuRequested.connect(
            lambda pos: self.chat_menu(pos, self.pinned_chats_list)
        )
        self.pinned_chats_list.setSpacing(3)
        self.pinned_chats_list.itemClicked.connect(self.select_chat_item)
        self.pinned_chats_list.viewport().installEventFilter(self)
        self.widget_chrome_widgets.append(self.pinned_chats_list)
        left.addWidget(self.pinned_chats_list)

        recent_title = QLabel("Недавние")
        recent_title.setStyleSheet("color:#888; font-size:12px;")
        self.widget_chrome_widgets.append(recent_title)
        left.addWidget(recent_title)

        # список недавних чатов; прокручивается только эта область
        self.chats_list = QListWidget()
        self.chats_list.setObjectName("chatList")
        self.chats_list.setFrameShape(QFrame.Shape.NoFrame)
        self.chats_list.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chats_list.setAutoFillBackground(False)
        self.chats_list.setFixedWidth(240)
        self.chats_list.setContentsMargins(0, 0, 0, 0)
        self.chats_list.setViewportMargins(2, 0, 2, 0)
        self.chats_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.chats_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chats_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chats_list.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chats_list.viewport().setAutoFillBackground(False)
        self.chats_list.viewport().setStyleSheet("background: transparent; border: none;")
        self.chats_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chats_list.customContextMenuRequested.connect(
            lambda pos: self.chat_menu(pos, self.chats_list)
        )
        # Recent chats take the remaining sidebar space in both window modes.
        # A fullscreen-only fixed height made the normal layout request 1090 px
        # while the shell was restoring to 850 px.
        self.chats_list.setMinimumHeight(60)
        self.chats_list.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.chats_list.setSpacing(3)
        self.widget_chrome_widgets.append(self.chats_list)
        self.chats_list.viewport().installEventFilter(self)

        self.chats_list.itemClicked.connect(self.select_chat_item)
        QTimer.singleShot(0, self.load_chat_sessions)
        QTimer.singleShot(0, self.load_chat_model)

        left.addWidget(self.chats_list, 1)

        # ---------- USER PROFILE ----------

        profile_button = QPushButton()
        profile_button.setObjectName("profileCard")
        profile_button.setCursor(Qt.CursorShape.PointingHandCursor)
        profile_button.setFixedWidth(220)
        profile_button.setFixedHeight(66)
        profile_layout = QHBoxLayout(profile_button)
        profile_layout.setContentsMargins(10, 7, 10, 7)
        profile_layout.setSpacing(9)
        self.profile_avatar = QLabel()
        self.profile_avatar.setFixedSize(42, 42)
        self.profile_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_avatar.setStyleSheet("border-radius:21px; background:rgba(0,235,245,0.22); color:white; font-size:18px; font-weight:bold;")
        profile_layout.addWidget(self.profile_avatar)
        profile_identity = QVBoxLayout()
        profile_identity.setSpacing(0)
        self.profile_name_label = QLabel()
        self.profile_name_label.setObjectName("profileCardName")
        self.profile_username_label = QLabel()
        self.profile_username_label.setObjectName("profileCardUsername")
        profile_identity.addWidget(self.profile_name_label)
        profile_identity.addWidget(self.profile_username_label)
        profile_layout.addLayout(profile_identity, 1)
        # The existing profile affordance is the Account Panel entry point.
        # The legacy local profile editor remains available from Settings.
        profile_button.clicked.connect(self.show_account_center)
        self.profile_button = profile_button
        self.widget_chrome_widgets.append(profile_button)
        self._refresh_user_profile_card()

        tandem_footer = QLabel(
            '<a style="color:#ffffff;" href="https://tandemarketing.ru">© Разработано Tandem Marketing</a>'
        )
        tandem_footer.setObjectName("tandemFooter")
        tandem_footer.setOpenExternalLinks(True)
        tandem_footer.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        tandem_footer.setCursor(Qt.CursorShape.PointingHandCursor)
        tandem_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tandem_footer.setFixedWidth(240)
        tandem_footer.setFixedHeight(22)
        tandem_footer.setWordWrap(True)
        tandem_footer.setStyleSheet("font-size:11px;")
        self.tandem_footer = tandem_footer
        self.widget_chrome_widgets.append(tandem_footer)


        # ---------- TOGGLES ----------

        toggles = QFrame()
        toggles.setObjectName("miniCard")
        toggles.setFixedSize(180,80)
        self.widget_chrome_widgets.append(toggles)

        t_layout = QVBoxLayout(toggles)

        row1 = QHBoxLayout()
        label1 = QLabel("Ассистент")
        label1.setStyleSheet("color:white; font-size:14px;")
        toggle1 = ToggleSwitch()
        toggle1.set_accent_color(self.accent_color)
        toggle1.setChecked(True)
        self.assistant_toggle = toggle1

        row1.addWidget(label1)
        row1.addStretch()
        row1.addWidget(toggle1)


        row2 = QHBoxLayout()
        label2 = QLabel("Микрофон")
        label2.setStyleSheet("color:white; font-size:14px;")
        toggle2 = ToggleSwitch()
        toggle2.set_accent_color(self.accent_color)
        toggle2.setChecked(True)
        self.microphone_toggle = toggle2
        self.sidebar_toggles = [toggle1, toggle2]
        toggle1.toggled.connect(self._assistant_toggle)
        toggle2.toggled.connect(self._toggle_microphone_from_sidebar)

        row2.addWidget(label2)
        row2.addStretch()
        row2.addWidget(toggle2)

        t_layout.addLayout(row1)
        t_layout.addLayout(row2)


        # ---------- WEATHER ----------

        weather = WeatherCardFrame(self)
        weather_settings = self.widget_settings.get("weather", {})
        weather.setFixedSize(
            int(weather_settings.get("card_width", 220)),
            int(weather_settings.get("card_height", 110)),
        )
        self.widget_chrome_widgets.append(weather)

        # Keep the icon inside the card; the previous layout-owned label had
        # no parent after switching to absolute visual positioning.
        self.weather_icon = QLabel(weather)
        self.weather_icon.setAlignment(Qt.AlignCenter)
        self.weather_city_label = QLabel("Мурино", weather)
        self.weather_temp_label = QLabel("--°C", weather)
        self.weather_desc_label = QLabel("Загрузка...", weather)
        self.weather_label = self.weather_desc_label  # compatibility for error handling
        for label in (self.weather_city_label, self.weather_temp_label, self.weather_desc_label):
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.weather_icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.weather_card = weather
        self.apply_weather_card_settings()


        # ---------- LAYOUT ----------

        left.addStretch()

        # Keep weather where the profile card used to be, and place the
        # profile at the very bottom of the sidebar.
        left.addWidget(toggles)
        left.addWidget(weather)
        left.addWidget(profile_button)
        left.addWidget(tandem_footer)

    
        # ---------- CHAT ----------

        chat_frame = QFrame()
        self.chat_frame = chat_frame
        chat_frame.setObjectName("chatFrame")

        chat_layout = QVBoxLayout(chat_frame)
        chat_layout.setContentsMargins(20, 20, 20, 20)
        chat_layout.setSpacing(0)

        # Crazy Tad native chat header: identity, provider/model context and
        # a dedicated settings entry point live above the message renderer.
        self.chat_header = QFrame()
        self.chat_header.setObjectName("chatHeader")
        self.chat_header.setFixedHeight(64)
        header_layout = QHBoxLayout(self.chat_header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(10)
        self.chat_avatar = QLabel("J")
        self.chat_avatar.setObjectName("chatAvatar")
        self.chat_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chat_avatar.setFixedSize(40, 40)
        self.chat_avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.chat_avatar)
        self.chat_identity = QWidget(self.chat_header)
        self.chat_identity.setObjectName("chatIdentity")
        self.chat_identity.setFixedWidth(430)
        chat_info = QVBoxLayout(self.chat_identity)
        chat_info.setContentsMargins(0, 0, 0, 0)
        chat_info.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        self.chat_title = QLabel("JARVIS CHAT")
        self.chat_title.setObjectName("chatTitle")
        self.chat_title.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.chat_title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.chat_status_dot = QLabel()
        self.chat_status_dot.setObjectName("chatStatusDot")
        self.chat_status_dot.setFixedSize(10, 10)
        self.chat_status_dot.setToolTip("Состояние Jarvis не определено")
        title_row.addWidget(self.chat_title, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        self.chat_subtitle = QLabel("Провайдер: Ollama  |  Модель: по умолчанию")
        self.chat_subtitle.setObjectName("chatSubtitle")
        for profile_widget in (self.chat_header, self.chat_avatar, self.chat_title, self.chat_status_dot, self.chat_subtitle):
            profile_widget.installEventFilter(self)
        chat_info.addLayout(title_row)
        model_status_row = QHBoxLayout()
        model_status_row.setContentsMargins(0, 0, 0, 0)
        model_status_row.setSpacing(15)
        model_status_row.addWidget(self.chat_subtitle, 0, Qt.AlignmentFlag.AlignVCenter)
        model_status_row.addWidget(self.chat_status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        model_status_row.addStretch(1)
        chat_info.addLayout(model_status_row)
        header_layout.addWidget(self.chat_identity)
        header_layout.addStretch()
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.setObjectName("modelCombo")
        self.chat_model_combo.addItems(["Ollama", "Codex", "Claude", "FreeLLMAPI"])
        self.chat_model_combo.setMinimumWidth(150)
        self.chat_model_combo.currentTextChanged.connect(self.on_chat_model_changed)
        header_layout.addWidget(self.chat_model_combo)
        self.chat_settings_button = QToolButton()
        self.chat_settings_button.setObjectName("chatSettingsBtn")
        settings_icon = Path(BASE_DIR) / "assets" / "CHAT" / "icons" / "chat_settings.svg"
        self.chat_settings_button.setIcon(QIcon(str(settings_icon)))
        self.chat_settings_button.setIconSize(QSize(20, 20))
        self.chat_settings_button.setToolTip("Настройки чата")
        self.chat_settings_button.clicked.connect(self.open_chat_settings)
        header_layout.addWidget(self.chat_settings_button)
        chat_layout.addWidget(self.chat_header)
        chat_layout.addSpacing(20)

        # IMPORTED CRAZY TAD CHAT FRONTEND

        self.chat_view = QWebEngineView()
        self.chat_view.setObjectName("jarvisChatWebView")
        self.chat_view.page().setBackgroundColor(QColor("#121212"))
        chat_palette = self.chat_view.palette()
        chat_palette.setColor(QPalette.ColorRole.Base, QColor("#121212"))
        chat_palette.setColor(QPalette.ColorRole.Window, QColor("#121212"))
        self.chat_view.setPalette(chat_palette)
        self.chat_view.setAutoFillBackground(True)
        self.chat_view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.chat_view.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        self.chat_view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.chat_channel = QWebChannel(self.chat_view.page())
        self.chat_bridge = JarvisChatBridge(self)
        self.chat_channel.registerObject("pywebchannel", self.chat_bridge)
        self.chat_view.page().setWebChannel(self.chat_channel)
        self.chat_view.loadFinished.connect(self._on_chat_frontend_loaded)
        chat_html = Path(BASE_DIR) / "assets" / "CHAT" / "chat.html"
        self.chat_view.setUrl(QUrl.fromLocalFile(str(chat_html.resolve())))
        # QtWebEngine's native compositor can expose its outermost right and
        # bottom device pixels at fractional Windows DPI.  Host it in an
        # opaque clipping surface and overscan those two edges outside the
        # visible rectangle instead of letting the desktop shine through.
        self.chat_surface = OpaqueWebSurface(self.chat_view)
        chat_layout.addWidget(self.chat_surface, 1)

        self.chat_composer_guard = QFrame()
        self.chat_composer_guard.setObjectName("chatComposerGuard")
        self.chat_composer_guard.setFixedHeight(20)
        self.chat_composer_guard.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chat_composer_guard.setStyleSheet(
            "QFrame#chatComposerGuard{background:#121212; border:none;}"
        )
        chat_layout.addWidget(self.chat_composer_guard)

        # ---------- CHAT COMPOSER ----------

        self.composer = ChatComposer(
            os.path.join(BASE_DIR, "assets", "CHAT"),
            self.accent_hex,
            self,
        )
        self.composer.send_requested.connect(self.send_command)
        self.composer.cancel_requested.connect(self.cancel_chat_request)
        self.composer.emote_requested.connect(self.open_chat_emote_picker)
        self.composer.voice_requested.connect(self.toggle_voice_from_composer)
        self.composer.voice_cancel_requested.connect(self.cancel_voice_dictation)
        self.composer.voice_chat_requested.connect(self.toggle_voice_chat_from_composer)
        self.composer.voice_chat_stop_requested.connect(self.stop_voice_chat_from_composer)
        self.composer.tool_requested.connect(self.handle_composer_tool)
        chat_layout.addWidget(self.composer)

        # ---------- PAGES ----------

        self.pages = QStackedWidget()
        self.pages.setMinimumSize(0, 0)
        self.pages.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        # страница ассистента
        assistant_page = QWidget()

        assistant_layout = QVBoxLayout(assistant_page)
        assistant_layout.setContentsMargins(0,0,0,0)
        self.hud = JarvisHUD(
            self.accent_color,
            self.active_font_family,
            self.text_color,
            calibration_mode="--calibrate-cpu" in sys.argv,
        )
        self.hud.apply_widget_settings(self.widget_settings)
        self.hud.set_datetime_settings(self.widget_settings.get("datetime", {}))
        self.hud.setFixedSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)
        self.assistant_label = QLabel("Нажмите кнопку чтобы активировать JARVIS")
        self.assistant_label.setAlignment(Qt.AlignCenter)
        self.assistant_label.setStyleSheet("color:white; font-size:16px;")
        self.assistant_label.setFixedSize(JarvisHUD.HUD_SIZE, 42)
        self.assistant_label.setWordWrap(True)
        self.assistant_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # состояние jarvis
        self.jarvis_state = False

        # кнопка jarvis
        self.jarvis_button = StartButton("START", self.text_color, self.accent_color)
        self.jarvis_button.setFixedSize(150,150)
        self.jarvis_button.setObjectName("jarvisStart")
        self.jarvis_button.setCursor(Qt.PointingHandCursor)

        # эффект свечения вокруг кнопки
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setBlurRadius(60)
        self.glow.setColor(QColor(0,170,255))
        self.glow.setOffset(0)

        # анимация пульса
        self.pulse_anim = QPropertyAnimation(self.glow, b"blurRadius")
        self.pulse_anim.setStartValue(20)
        self.pulse_anim.setEndValue(200)
        self.pulse_anim.setDuration(800)
        self.pulse_anim.setLoopCount(-1)

        # анимация "дыхания" кнопки
        self.jarvis_button.setGraphicsEffect(self.glow)

        assistant_layout.addStretch()

        hud_container = QWidget()
        self.hud_container = hud_container
        hud_container.setFixedSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)
        hud_container.setMinimumSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)
        hud_container.setMaximumSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)
        hud_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        stack = QStackedLayout(hud_container)
        stack.setStackingMode(QStackedLayout.StackAll)

        # слой HUD
        stack.addWidget(self.hud)

        # START is a direct HUD child. A full-size button layer used to sit
        # above the decorative HUD and could swallow clicks from panel buttons.
        self.jarvis_button.setParent(hud_container)
        self.jarvis_button.move(
            (JarvisHUD.HUD_SIZE - self.jarvis_button.width()) // 2,
            (JarvisHUD.HUD_SIZE - self.jarvis_button.height()) // 2,
        )
        self.jarvis_button.show()
        self.jarvis_button.raise_()

        # TECH-A action buttons are direct children of the HUD container so
        # their transparent PNGs stay above the rings without covering START.
        self.tech_action_buttons = self.create_tech_action_buttons(hud_container)
        self.hud_panel_buttons = self.create_hud_panel_buttons(hud_container)
        # Some transparent decorative layers can receive a near-miss click
        # instead of the child button. Let the HUD itself route that click to
        # the nearest lower panel icon.
        self.hud.installEventFilter(self)
        hud_container.installEventFilter(self)
        QTimer.singleShot(0, self.raise_hud_controls)

        assistant_layout.addWidget(hud_container, alignment=Qt.AlignCenter)

        assistant_layout.addSpacing(20)

        assistant_layout.addWidget(
        self.assistant_label,
        alignment=Qt.AlignHCenter
        )
        assistant_layout.addStretch()

        self.jarvis_button.clicked.connect(self._toggle_voice_runtime)

        self.pages.addWidget(assistant_page)
        
        # страница чата
        chat_page = QWidget()
        chat_page_layout = QVBoxLayout(chat_page)
        chat_page_layout.setContentsMargins(0,0,0,0)
        chat_page_layout.addWidget(chat_frame)

        self.pages.addWidget(chat_page)

        # Keep the left navigation indices aligned with the stacked pages.
        history_page = QFrame()
        history_page.setObjectName("settingsCard")
        history_page.setMaximumWidth(960)
        history_layout = QVBoxLayout(history_page)
        history_layout.setContentsMargins(20, 20, 20, 20)
        history_layout.setSpacing(14)
        history_title = QLabel("ИСТОРИЯ ЧАТОВ")
        history_title.setObjectName("settingsCardTitle")
        history_layout.addWidget(history_title)
        history_toolbar = QHBoxLayout()
        history_hint = QLabel("Выберите чат, чтобы открыть его историю")
        history_hint.setObjectName("settingsHint")
        self.history_hint = history_hint
        history_toolbar.addWidget(history_hint)
        history_toolbar.addStretch()
        refresh_history = QPushButton("ОБНОВИТЬ")
        refresh_history.setObjectName("historyRefresh")
        refresh_history.setFixedSize(92, 32)
        refresh_history.clicked.connect(self.load_history_sessions)
        self.refresh_history_button = refresh_history
        history_layout.addLayout(history_toolbar)
        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setFrameShape(QFrame.Shape.NoFrame)
        self.history_list.setSpacing(6)
        self.history_list.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.history_list.setAutoFillBackground(False)
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_list.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.history_list.viewport().setAutoFillBackground(False)
        self.history_list.viewport().setObjectName("historyListViewport")
        self.history_list.itemClicked.connect(self.open_history_chat)
        history_layout.addWidget(self.history_list, 1)
        history_actions = QHBoxLayout()
        history_actions.addWidget(refresh_history)
        history_actions.addStretch(1)
        history_layout.addLayout(history_actions)

        # страница настроек
        settings_page = QWidget()
        settings_page.setObjectName("settingsPage")
        self.settings_page_widget = settings_page
        settings_layout = QVBoxLayout(settings_page)
        # The header labels end above this body. Leave a readable gap while
        # giving navigation and content the full height and width of the shell.
        settings_layout.setContentsMargins(4, 60, 0, 0)
        settings_layout.setSpacing(14)

        settings_title = QLabel("НАСТРОЙКИ JARVIS")
        settings_title.setObjectName("settingsTitle")
        settings_title.setStyleSheet("font-size: 27px; font-weight: 700;")
        settings_subtitle = QLabel("Внешний вид интерфейса и HUD")
        settings_subtitle.setObjectName("settingsHint")
        settings_hub_hint = QLabel("Выберите раздел ниже — настройки открываются внутри Jarvis и сохраняются сразу.")
        settings_hub_hint.setObjectName("settingsHint")
        # Keep these three labels in the main content host so they can sit on
        # the same upper line as the JARVIS ASSIST logo without changing the
        # width or geometry of the settings cards below.
        self.settings_title_widget = settings_title
        self.settings_subtitle_widget = settings_subtitle
        self.settings_hub_hint_widget = settings_hub_hint
        for header_widget in (settings_title, settings_subtitle, settings_hub_hint):
            header_widget.setParent(container)
            header_widget.hide()
        self.settings_header_host = container

        settings_body = QHBoxLayout()
        settings_body.setSpacing(14)
        settings_nav = QListWidget()
        settings_nav.setObjectName("settingsNavigation")
        settings_nav.setFixedWidth(240)
        settings_sections = (
            ("ОБЩИЕ", "Общие настройки"),
            ("УЧЁТНАЯ ЗАПИСЬ", "Профиль пользователя"),
            ("УВЕДОМЛЕНИЯ", "Уведомления"),
            ("IRON", "HUD, слои и метрики"),
            ("ПОГОДА", "API и карточка погоды"),
            ("AI", "Провайдеры и модели"),
            ("ГОЛОС AI", "Микрофон и голос"),
            ("КОМАНДЫ", "Команды Jarvis"),
            ("ПЕРСОНАЛИЗАЦИЯ", "Инструкции и память"),
            ("ПРИВАТНОСТЬ", "История и обработка данных"),
            ("ДАННЫЕ", "Хранилище и экспорт"),
            ("ЧАТ", "История, вложения и плееры"),
            ("ИСТОРИЯ ЧАТОВ", "Сохранённые диалоги и быстрый переход к ним"),
        )
        for label, _hint in settings_sections:
            settings_nav.addItem(label)
        settings_stack = CurrentPageStack()
        settings_stack.setObjectName("settingsContent")
        # The fixed application shell must own the horizontal constraint.
        # Ignore the widest hidden settings page's size hint so selecting
        # Settings cannot request a 1600 px native window from Qt.
        settings_stack.setMinimumWidth(0)
        settings_stack.setMinimumSize(0, 0)
        settings_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        settings_scroll = QScrollArea()
        settings_scroll.setObjectName("settingsScroll")
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        settings_scroll.setMinimumSize(0, 0)
        settings_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        settings_scroll.setWidget(settings_stack)
        # QScrollArea.setWidget() enables palette-based auto-fill on its child.
        # On Windows that Base color is light, so it covered the entire Glass
        # settings surface even though the root theme stayed dark.
        settings_stack.setAutoFillBackground(False)
        settings_scroll.viewport().setObjectName("settingsScrollViewport")
        settings_scroll.viewport().setAutoFillBackground(False)
        self.settings_scroll = settings_scroll
        settings_nav.currentRowChanged.connect(settings_stack.setCurrentIndex)
        if os.getenv("JARVIS_UI_TRACE"):
            def trace_settings_layout(row):
                QTimer.singleShot(0, lambda: _ui_trace(
                    "settings.layout",
                    row=row,
                    viewport_height=settings_scroll.viewport().height(),
                    stack_height=settings_stack.height(),
                    stack_hint_height=settings_stack.sizeHint().height(),
                    current_hint_height=settings_stack.currentWidget().sizeHint().height(),
                    scroll_max=settings_scroll.verticalScrollBar().maximum(),
                ))
            settings_nav.currentRowChanged.connect(trace_settings_layout)
        def refresh_settings_history(row):
            if row >= 0 and settings_nav.item(row).text().strip() == "ИСТОРИЯ ЧАТОВ":
                self.load_history_sessions()
        settings_nav.currentRowChanged.connect(refresh_settings_history)
        settings_nav.setCurrentRow(0)
        self.settings_nav = settings_nav
        settings_body.addWidget(settings_nav)
        settings_body.addWidget(settings_scroll, 1)
        settings_layout.addLayout(settings_body, 1)

        def section_page(title, hint, callback=None, button_text="ОТКРЫТЬ НАСТРОЙКИ", fields=(), checks=(), extra_builder=None, max_width=960, min_width=0):
            page = QFrame()
            page.setObjectName("settingsCard")
            page.setMinimumSize(0, 0)
            page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            page.setMaximumWidth(max_width)
            if min_width:
                page.setMinimumWidth(min_width)
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(20, 20, 20, 20)
            page_layout.setSpacing(14)
            if not (title == "AI" and extra_builder):
                heading = QLabel(title)
                heading.setObjectName("settingsCardTitle")
                page_layout.addWidget(heading)
                description = QLabel(hint)
                description.setObjectName("settingsHint")
                description.setWordWrap(True)
                page_layout.addWidget(description)
            content_host = QWidget()
            content_host.setObjectName("settingsSectionContent")
            content_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            content_layout = QVBoxLayout(content_host)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(14)
            page_layout.addWidget(content_host, 1)
            footer_layout = QHBoxLayout()
            footer_layout.setContentsMargins(0, 0, 0, 0)
            footer_layout.setSpacing(12)
            edits = {}
            for key, label, default in fields:
                if key == "custom_instructions":
                    edit = QPlainTextEdit(str(self.ui_settings.value(key, default)))
                    edit.setObjectName("customInstructionsEditor")
                    edit.setMinimumHeight(260)
                    edit.setMaximumHeight(420)
                    edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
                    edit.setPlaceholderText("Введите длинную системную инструкцию для Jarvis…")
                else:
                    edit = QLineEdit(str(self.ui_settings.value(key, default)))
                edits[key] = edit
                content_layout.addWidget(QLabel(label))
                content_layout.addWidget(edit)
            checkboxes = {}
            for key, label, default in checks:
                check = QCheckBox(label)
                check.setChecked(self.ui_settings.value(key, default, type=bool))
                checkboxes[key] = check
                content_layout.addWidget(check)
            if extra_builder:
                extra_builder(content_layout, edits, footer_layout)
            if title not in {"AI", "КОМАНДЫ JARVIS"}:
                # Keep ordinary forms compact at the top while the action row
                # remains anchored at the bottom. Future fields can grow this
                # content naturally instead of inheriting artificial gaps.
                content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            if fields or checks:
                action = QPushButton("СОХРАНИТЬ")
                action.setObjectName("settingsTileButton")
                def save_section():
                    for key, edit in edits.items():
                        value = edit.toPlainText() if hasattr(edit, "toPlainText") else edit.text()
                        self.ui_settings.setValue(key, value.strip())
                    for key, check in checkboxes.items():
                        self.ui_settings.setValue(key, check.isChecked())
                    self.ui_settings.sync()
                    self.assistant_label.setText(f"Раздел «{title}» сохранён")
                action.clicked.connect(save_section)
                footer_layout.addWidget(action)
                if callback and not extra_builder:
                    quick = QPushButton(button_text)
                    quick.setObjectName("settingsTileButton")
                    quick.clicked.connect(callback)
                    footer_layout.addWidget(quick)
            elif callback and not extra_builder:
                action = QPushButton(button_text)
                action.setObjectName("settingsTileButton")
                action.clicked.connect(callback)
                footer_layout.addWidget(action)
            footer_layout.addStretch(1)
            page_layout.addLayout(footer_layout)
            settings_stack.addWidget(page)
            settings_stack.layout().setAlignment(page, Qt.AlignLeft | Qt.AlignTop)
            return page

        general_page = QFrame()
        self.general_page = general_page
        general_page.setObjectName("settingsCard")
        general_page.setMinimumSize(0, 0)
        general_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # The settings navigation (240 px) shares the fixed 1280 px shell
        # with the content card.  Keep the card bounded so Qt cannot expand
        # the whole frameless window when the settings page is selected.
        general_page.setMaximumWidth(960)
        # The settings stack must be able to shrink inside the fixed
        # 1280x850 application shell.  A hard 760px minimum here, combined
        # with the header and shell margins, made Qt expand the whole window
        # to 1600x1166 and emit repeated "Unable to set geometry" warnings.
        general_page.setMinimumHeight(0)
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(20, 20, 20, 20)
        general_layout.setSpacing(14)

        general_heading = QLabel("ОБЩИЕ")
        general_heading.setObjectName("settingsCardTitle")
        general_layout.addWidget(general_heading)
        general_hint = QLabel("Внешний вид интерфейса и HUD")
        general_hint.setObjectName("settingsHint")
        general_layout.addWidget(general_hint)

        def make_tile():
            tile = QFrame()
            tile.setObjectName("settingsGlassTile")
            tile.setMinimumHeight(62)
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(16, 10, 16, 10)
            tile_layout.setSpacing(3)
            return tile, tile_layout

        font_tile, font_layout = make_tile()
        font_row = QHBoxLayout()
        font_info = QVBoxLayout()
        font_title = QLabel("Шрифт интерфейса")
        font_title.setStyleSheet("font-size:12px; font-weight:700;")
        font_info.addWidget(font_title)
        self.font_combo = QComboBox(general_page)
        self.font_combo.addItems(list(self.tech_font_families.keys()))
        for index in range(self.font_combo.count()):
            if self.tech_font_families.get(self.font_combo.itemText(index)) == self.active_font_family:
                self.font_combo.setCurrentIndex(index)
                break
        self.font_combo.currentTextChanged.connect(self.apply_font_family)
        self.font_combo.hide()
        installed_fonts = set(QFontDatabase.families())

        def installed(preferred, fallback="Segoe UI"):
            for family in preferred:
                if family in installed_fonts:
                    return family
            return fallback if fallback in installed_fonts else sorted(installed_fonts)[0]

        jarvis_family = self.tech_font_families.get("Good Times")
        font_choices = (
            (jarvis_family or installed(("Inter", "Segoe UI")), jarvis_family or installed(("Inter", "Segoe UI"))),
            (installed(("Inter", "Segoe UI")), installed(("Inter", "Segoe UI"))),
            (installed(("Arial", "Segoe UI")), installed(("Arial", "Segoe UI"))),
            (self.tech_font_families.get("Imagine font") or installed(("Times New Roman", "Times", "Segoe UI")),
             self.tech_font_families.get("Imagine font") or installed(("Times New Roman", "Times", "Segoe UI"))),
        )
        font_choice_row = QHBoxLayout()
        self._font_choice_buttons = []
        for label, family in font_choices:
            choice = QPushButton(label)
            choice.setFlat(True)
            choice.clicked.connect(lambda checked=False, value=family: self._set_interface_font_family(value))
            self._font_choice_buttons.append((choice, family))
            font_choice_row.addWidget(choice, 0, Qt.AlignLeft)
        font_choice_row.addStretch()
        font_info.addLayout(font_choice_row)
        self._refresh_font_choice_state()
        font_row.addLayout(font_info, 1)
        font_button = QPushButton("Загрузить шрифт")
        font_button.setFixedWidth(126)
        font_button.clicked.connect(self.load_interface_font)
        font_row.addWidget(font_button, 0, Qt.AlignVCenter)
        font_layout.addLayout(font_row)
        general_layout.addWidget(font_tile)

        accent_tile, accent_layout = make_tile()
        accent_row = QHBoxLayout()
        accent_info = QVBoxLayout()
        accent_title = QLabel("Цвет акцента")
        accent_title.setStyleSheet("font-size:12px; font-weight:700;")
        accent_info.addWidget(accent_title)
        self.accent_value_label = QLabel(self.accent_hex.upper())
        self.accent_value_label.setProperty("role", "hint")
        accent_info.addWidget(self.accent_value_label)
        accent_row.addLayout(accent_info, 1)
        self.accent_button = QPushButton("Изменить")
        self.accent_button.setFixedWidth(126)
        self.accent_button.clicked.connect(self.choose_accent_color)
        accent_row.addWidget(self.accent_button, 0, Qt.AlignVCenter)
        accent_layout.addLayout(accent_row)
        general_layout.addWidget(accent_tile)

        opacity_tile, opacity_layout = make_tile()
        opacity_title_row = QHBoxLayout()
        opacity_title = QLabel("Прозрачность окна")
        opacity_title.setStyleSheet("font-size:12px; font-weight:700;")
        opacity_title_row.addWidget(opacity_title)
        opacity_title_row.addStretch()
        opacity_value_label = QLabel(f"{self.visual_settings['window_opacity']}%")
        opacity_value_label.setProperty("role", "hint")
        opacity_title_row.addWidget(opacity_value_label)
        opacity_layout.addLayout(opacity_title_row)
        opacity_row = QHBoxLayout()
        self.window_opacity_spin = QSpinBox(general_page)
        self.window_opacity_spin.setRange(20, 100)
        self.window_opacity_spin.setValue(self.visual_settings["window_opacity"])
        self.window_opacity_spin.valueChanged.connect(self.apply_visual_settings)
        self.window_opacity_spin.valueChanged.connect(lambda value: opacity_value_label.setText(f"{value}%"))
        self.window_opacity_spin.hide()
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider = opacity_slider
        opacity_slider.setRange(20, 100)
        opacity_slider.setValue(self.visual_settings["window_opacity"])
        opacity_slider.valueChanged.connect(self._set_window_opacity_from_slider)
        opacity_row.addWidget(opacity_slider)
        opacity_layout.addLayout(opacity_row)
        general_layout.addWidget(opacity_tile)

        # Keep the existing runtime hooks available to the rest of the UI;
        # these controls are intentionally not duplicated in this reference
        # frame and remain driven by the redesigned tiles above.
        self.transparent_background_check = QCheckBox(general_page)
        self.transparent_background_check.setChecked(self.visual_settings["transparent_background"])
        self.transparent_background_check.hide()
        self.startup_widget_check = QCheckBox(general_page)
        self.startup_widget_check.setChecked(self.startup_widget_mode)
        self.startup_widget_check.toggled.connect(self.set_startup_widget_mode)
        self.startup_widget_check.hide()
        self.windows_autostart_check = QCheckBox(general_page)
        self.windows_autostart_check.setChecked(windows_autostart_enabled())
        self.windows_autostart_check.toggled.connect(self.set_windows_autostart)
        self.windows_autostart_check.hide()
        self.video_source_combo = QComboBox(general_page)
        for label, device_id in self.enumerate_video_sources(
            self.hardware_settings.get("video_input_device", 0)
        ):
            self.video_source_combo.addItem(label, device_id)
        video_index = self.video_source_combo.findData(self.hardware_settings["video_input_device"])
        self.video_source_combo.setCurrentIndex(max(0, video_index))
        self.video_source_combo.currentIndexChanged.connect(self.apply_hardware_settings)
        self.video_source_combo.hide()
        self.acrylic_status = QLabel(general_page)
        self.acrylic_status.hide()
        self.font_color_value_label = QLabel(general_page)
        self.font_color_value_label.hide()
        self.font_color_button = QPushButton(general_page)
        self.font_color_button.hide()

        glass_tile, glass_layout = make_tile()
        glass_row = QHBoxLayout()
        glass_info = QVBoxLayout()
        glass_title = QLabel("Стекло / blur")
        glass_title.setStyleSheet("font-size:12px; font-weight:700;")
        glass_info.addWidget(glass_title)
        glass_hint = QLabel("Включено")
        glass_hint.setProperty("role", "hint")
        self.glass_hint = glass_hint
        glass_info.addWidget(glass_hint)
        glass_row.addLayout(glass_info, 1)
        self.glass_enabled_check = ToggleSwitch(general_page)
        self.glass_enabled_check.set_accent_color(self.accent_hex)
        self.glass_enabled_check.setChecked(self.visual_settings["glass_enabled"])
        self.glass_enabled_check.toggled.connect(self.apply_visual_settings)
        glass_row.addWidget(self.glass_enabled_check, 0, Qt.AlignVCenter)
        glass_layout.addLayout(glass_row)
        general_layout.addWidget(glass_tile)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color:rgba(255,255,255,24);")
        general_layout.addWidget(divider)
        quick_title = QLabel("Быстрые переходы")
        quick_title.setStyleSheet("font-size:11px; font-weight:600; color:#73909a;")
        general_layout.addWidget(quick_title)
        quick_row = QHBoxLayout()
        for text, section, color in (("AI PROVIDERS", "AI", "#7448e8"), ("IRON / HUD", "IRON", self.accent_hex), ("CHAT", "ЧАТ", "#5b8995")):
            quick = QPushButton(text)
            quick.setFixedHeight(27)
            quick.setStyleSheet(f"color:{color}; border:1px solid {color}; border-radius:9px; padding:0 10px; background:rgba(0,0,0,45);")
            quick.clicked.connect(lambda checked=False, target=section: self._jump_to_settings_section(target))
            quick_row.addWidget(quick, 0, Qt.AlignLeft)
        quick_row.addStretch()
        general_layout.addLayout(quick_row)

        palette_tile, palette_layout = make_tile()
        palette_row = QHBoxLayout()
        palette_title = QLabel("Акценты прозрачности")
        palette_title.setStyleSheet("font-size:12px; font-weight:700;")
        palette_row.addWidget(palette_title)
        palette_row.addStretch()
        for color in ("#00AAFF", "#24B59F", "#2675DB", "#6240E8", "#C64C91", "#DCE8EB"):
            swatch = QToolButton()
            swatch.setFixedSize(28, 28)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setStyleSheet(
                f"QToolButton {{ background:{color}; border:none; border-radius:14px; }}"
                f"QToolButton:hover {{ border:2px solid #eef5f7; }}"
            )
            swatch.clicked.connect(lambda checked=False, value=color: self._set_glass_tint(value))
            palette_row.addWidget(swatch)
        palette_button = QPushButton("ВЫБРАТЬ")
        palette_button.clicked.connect(lambda: self.pick_glass_tint())
        palette_row.addWidget(palette_button)
        palette_layout.addLayout(palette_row)
        general_layout.addWidget(palette_tile)
        general_layout.addStretch(1)
        settings_stack.addWidget(general_page)
        settings_stack.layout().setAlignment(general_page, Qt.AlignLeft | Qt.AlignTop)
        section_page("УЧЁТНАЯ ЗАПИСЬ", "Локальный профиль и опциональное подключение Account System.", self.show_user_profile, "ОТКРЫТЬ ПРОФИЛЬ", fields=(("profile_display_name", "Имя", "Данил"), ("profile_username", "Username", "sheff"), ("profile_email", "Электронная почта", ""), ("profile_age", "Возраст", ""), ("profile_address", "Как обращаться", "Данил")), extra_builder=self._account_section_extra)
        section_page("УВЕДОМЛЕНИЯ", "Поведение стартовой диагностики и уведомлений ответов.", fields=(), checks=(("notify_startup", "Показывать уведомления запуска", True), ("notify_chat", "Уведомления новых ответов", True)))
        def iron_inline(layout, edits, actions):
            layer_box = QGroupBox("СЛОИ")
            layer_layout = QGridLayout(layer_box)
            layer_checks = {}
            for index, name in enumerate(("BG1", "BG2/BG000", "BG3", "BG4", "BG5", "BG6", "ROTATOR 1", "ROTATOR 2")):
                check = QCheckBox(name)
                check.setChecked(self.widget_settings.get("layers", {}).get(name, True))
                layer_checks[name] = check
                layer_layout.addWidget(check, index // 2, index % 2)
            layout.addWidget(layer_box)
            metric_box = QGroupBox("МЕТРИКИ")
            metric_layout = QHBoxLayout(metric_box)
            metric_checks = {}
            for name in ("CPU", "RAM", "GPU", "DISK"):
                check = QCheckBox(name)
                check.setChecked(self.widget_settings.get("metrics", {}).get(name, True))
                metric_checks[name] = check
                metric_layout.addWidget(check)
            layout.addWidget(metric_box)
            form = QFormLayout()
            motion_spins = {}
            for key, label, fallback in (("rotator_1_seconds", "ROTATOR 1, сек.", 75), ("rotator_2_seconds", "ROTATOR 2, сек.", 125), ("bg000_seconds", "BG000, сек.", 40)):
                spin = QSpinBox()
                spin.setRange(1, 600)
                spin.setValue(int(self.widget_settings.get("motion", {}).get(key, fallback)))
                spin.setSuffix(" сек")
                motion_spins[key] = spin
                form.addRow(label, spin)
            layout.addLayout(form)
            save = QPushButton("СОХРАНИТЬ IRON")
            save.setObjectName("settingsTileButton")
            def save_iron():
                self.widget_settings["layers"] = {key: value.isChecked() for key, value in layer_checks.items()}
                self.widget_settings["metrics"] = {key: value.isChecked() for key, value in metric_checks.items()}
                self.widget_settings.setdefault("motion", {}).update({key: value.value() for key, value in motion_spins.items()})
                self.ui_settings.setValue("widget_settings", json.dumps(self.widget_settings, ensure_ascii=False))
                self.hud.apply_widget_settings(self.widget_settings)
                self.assistant_label.setText("Настройки IRON сохранены")
            save.clicked.connect(save_iron)
            actions.addWidget(save)
            quick = QPushButton("ОТКРЫТЬ РАСШИРЕННЫЙ РЕДАКТОР IRON")
            quick.clicked.connect(self.open_widget_settings)
            actions.addWidget(quick)
        section_page("IRON", "Слои, метрики, панели, размеры и скорость анимаций.", extra_builder=iron_inline)
        def weather_inline(layout, edits, actions):
            status = QLabel("Ключ проверяется запросом к OpenWeather и не выводится в журнал.")
            status.setObjectName("settingsHint")
            button = QPushButton("ПРОВЕРИТЬ API И СОХРАНИТЬ")
            def save_weather():
                city = edits["weather_city"].text().strip()
                key = edits["weather_api_key"].text().strip()
                self._validate_and_save_weather(city, key, status, button)
            button.clicked.connect(save_weather)
            layout.addWidget(status)
            actions.addWidget(button)
        section_page("ПОГОДА", "OpenWeather API, город и визуальная настройка карточки.", self.open_weather_settings, fields=(("weather_city", "Город", "Мурино"), ("weather_api_key", "OpenWeather API key", "")), extra_builder=weather_inline)
        def ai_inline(layout, _edits, _actions=None):
            """Figma's provider panel backed by the existing LLM settings API."""
            provider_specs = (
                ("ollama", "Ollama", "ollama.png", "ollama"),
                ("openai", "OpenAI", "openai.png", "openai"),
                ("codex", "Codex", "codex.png", "codex"),
                ("claude", "Claude", "claude.png", "claude"),
                ("freellmapi", "FreeLLMAPI", "freellmapi.png", "freellmapi"),
                ("openai_compatible", "Подключить свою модель", "custom.png", "openai"),
            )
            labels = {key: label for key, label, _asset, _prefix in provider_specs}
            defaults = {
                "ollama": ("http://127.0.0.1:11434", "qwen3:8b"),
                "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
                "codex": ("", ""),
                "claude": ("https://api.anthropic.com/v1", ""),
                "freellmapi": ("", ""),
                "openai_compatible": ("", ""),
            }
            profiles = {}
            enabled = set()
            active = {"value": "ollama"}
            provider_state = {"loaded": False, "pending": False, "dirty": False}
            cards = {}
            provider_jobs = []
            status = QLabel("Загрузка профилей…")
            status.setObjectName("settingsHint")

            panel = QFrame()
            panel.setObjectName("providerModelsPanel")
            # 840x760 is the Figma reference size, not a window minimum.  The
            # panel must shrink when embedded beside the settings navigation;
            # otherwise the shell's fixed 1280x850 size is rejected by Qt.
            panel.setMinimumSize(0, 0)
            panel.setMaximumWidth(960)
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(22, 24, 22, 20)
            panel_layout.setSpacing(0)

            header = QHBoxLayout()
            header.setSpacing(10)
            title_box = QVBoxLayout()
            title = QLabel("ПРОВАЙДЕРЫ И МОДЕЛИ AI")
            title.setObjectName("providerModelsTitle")
            subtitle = QLabel("Отдельные профили провайдеров с выбором активного")
            subtitle.setObjectName("providerModelsSubtitle")
            title_box.addWidget(title)
            title_box.addWidget(subtitle)
            header.addLayout(title_box, 1)
            saved = QPushButton("SAVED")
            saved.setObjectName("providerSaved")
            saved.setFixedSize(86, 38)
            saved.setEnabled(False)
            header.addWidget(saved, 0, Qt.AlignmentFlag.AlignTop)
            panel_layout.addLayout(header)
            panel_layout.addSpacing(28)

            def profile_for(provider_id):
                base, model = defaults.get(provider_id, ("", ""))
                return profiles.setdefault(provider_id, {
                    "base_url": base, "model": model, "api_key_masked": "",
                    "active": False, "enabled": provider_id in enabled,
                })

            def provider_payload(provider_id=None):
                provider_id = provider_id or active["value"]
                payload = {"provider": provider_id, "enabled_providers": sorted(enabled)}
                for key, _label, _asset, prefix in provider_specs:
                    value = profile_for(key)
                    payload[f"{prefix}_base_url"] = str(value.get("base_url") or "").strip()
                    payload[f"{prefix}_model"] = str(value.get("model") or "").strip()
                return payload

            def run_operation(operation, payload=None, params=None, callback=None):
                start_network_operation(
                    panel,
                    operation,
                    callback,
                    lambda error: operation_failed(operation, error),
                    provider_jobs,
                    payload=payload,
                    params=params,
                )
                if operation == "load":
                    QTimer.singleShot(
                        10000,
                        lambda: status.setText(
                            "Не удалось загрузить профили: backend не ответил вовремя."
                            if status.text().startswith("Загрузка профилей") else status.text()
                        ),
                    )

            def mark_saved(text="SAVED"):
                provider_state["dirty"] = False
                saved.setText(text)
                saved.setEnabled(False)

            def mark_dirty():
                if provider_state["loaded"] and not provider_state["pending"]:
                    provider_state["dirty"] = True
                    saved.setText("SAVE")
                    saved.setEnabled(True)

            def operation_failed(operation, error):
                if operation == "save":
                    provider_state["pending"] = False
                    for card in cards.values():
                        card["toggle"].setEnabled(True)
                    mark_saved("RETRY")
                status.setText(f"Операция не выполнена: {error}")

            def update_card(provider_id):
                card = cards.get(provider_id)
                if not card:
                    return
                value = profile_for(provider_id)
                profile_status = value.get("status") or {}
                model_text = str(value.get("model") or "").strip()
                if not profile_status.get("ok"):
                    model_text = "Не настроен"
                elif not model_text:
                    model_text = str(profile_status.get("model") or "Профиль настроен")
                if not model_text:
                    model_text = "Не настроен"
                card["model"].setText(model_text)
                card["toggle"].blockSignals(True)
                card["toggle"].setChecked(provider_id in enabled)
                card["toggle"].blockSignals(False)
                border = self.accent_hex if provider_id == active["value"] else "rgba(166,242,242,33)"
                card["frame"].setStyleSheet(
                    "QFrame#providerModelCard {"
                    "background:rgba(0,0,0,61);"
                    f"border:1px solid {border};"
                    "border-radius:13px;}"
                )

            def select_active(provider_id):
                if not provider_state["loaded"] or provider_state["pending"]:
                    return
                if provider_id != active["value"]:
                    active["value"] = provider_id
                    enabled.clear()
                    enabled.add(provider_id)
                    for key in cards:
                        update_card(key)
                    mark_dirty()

            def save_state(provider_id=None, callback=None):
                if not provider_state["loaded"] or provider_state["pending"] or not provider_state["dirty"]:
                    return
                provider_id = provider_id or active["value"]
                payload = provider_payload(provider_id)
                payload["enabled_providers"] = [provider_id]
                saved.setText("SAVING…")
                provider_state["pending"] = True
                for card in cards.values():
                    card["toggle"].setEnabled(False)
                status.setText(f"Сохраняю {labels[provider_id]}…")
                def saved_state(data):
                    load_data(data)
                    status.setText(f"Активный провайдер: {labels[active['value']]}. Сохранено в backend.")
                    if callback:
                        callback(data)
                run_operation("save", payload=payload, callback=saved_state)

            def toggle_provider(provider_id, checked):
                card_toggle = cards[provider_id]["toggle"]
                if not provider_state["loaded"] or provider_state["pending"]:
                    return
                if not checked and provider_id == active["value"]:
                    card_toggle.blockSignals(True)
                    card_toggle.setChecked(True)
                    card_toggle.blockSignals(False)
                    status.setText("Нельзя отключить единственный активный профиль. Включите другой.")
                    return
                if checked:
                    active["value"] = provider_id
                    enabled.clear()
                    enabled.add(provider_id)
                    for key in cards:
                        update_card(key)
                    mark_dirty()
                else:
                    card_toggle.blockSignals(True)
                    card_toggle.setChecked(True)
                    card_toggle.blockSignals(False)
                    status.setText("Оставьте активный профиль включённым или включите другой.")

            def configure(provider_id):
                dialog = AIProviderDialog(self, provider_id)
                dialog.setWindowTitle(f"НАСТРОЙКА — {labels[provider_id].upper()}")
                dialog.finished.connect(lambda _code: run_operation("load", callback=load_data))
                dialog.show()

            for row, (provider_id, label, asset_name, _prefix) in enumerate(provider_specs):
                frame = QFrame()
                frame.setObjectName("providerModelCard")
                frame.setProperty("active", False)
                frame.setMinimumHeight(66)
                frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                card_layout = QHBoxLayout(frame)
                card_layout.setContentsMargins(17, 7, 16, 7)
                card_layout.setSpacing(16)
                icon = QLabel()
                icon.setFixedSize(50, 50)
                pixmap = QPixmap(str(Path(BASE_DIR) / "assets" / "providers" / asset_name))
                if not pixmap.isNull():
                    icon.setPixmap(pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    icon.setText(label[:1])
                card_layout.addWidget(icon)
                text_box = QVBoxLayout()
                text_box.setSpacing(1)
                name = QLabel(label)
                name.setObjectName("providerModelName")
                model = QLabel("Не настроен")
                model.setObjectName("providerModelValue")
                text_box.addWidget(name)
                text_box.addWidget(model)
                card_layout.addLayout(text_box, 1)
                toggle = ProviderSwitch()
                toggle.setObjectName("providerModelToggle")
                toggle.setEnabled(False)
                toggle.accent_color = QColor(self.accent_hex)
                toggle.setCursor(Qt.CursorShape.PointingHandCursor)
                toggle.toggled.connect(lambda checked, key=provider_id: toggle_provider(key, checked))
                card_layout.addWidget(toggle)
                configure_button = QPushButton("Настроить")
                configure_button.setObjectName("providerConfigure")
                configure_button.setFixedSize(84, 32)
                configure_button.clicked.connect(lambda _checked=False, key=provider_id: configure(key))
                card_layout.addWidget(configure_button)
                cards[provider_id] = {"frame": frame, "model": model, "toggle": toggle}
                frame.setCursor(Qt.CursorShape.PointingHandCursor)
                frame.mousePressEvent = lambda _event, key=provider_id: select_active(key)
                panel_layout.addWidget(frame)
                if row < len(provider_specs) - 1:
                    panel_layout.addSpacing(20)

            panel_layout.addStretch(1)
            panel_layout.addWidget(status)
            panel_layout.addSpacing(10)
            actions = QHBoxLayout()
            actions.setSpacing(28)
            test_button = QPushButton("ПРОВЕРИТЬ")
            test_button.setObjectName("providerAction")
            test_button.setFixedSize(112, 34)
            models_button = QPushButton("ПОЛУЧИТЬ МОДЕЛИ")
            models_button.setObjectName("providerAction")
            models_button.setFixedSize(170, 34)
            actions.addWidget(test_button)
            actions.addWidget(models_button)
            actions.addStretch(1)
            panel_layout.addLayout(actions)
            layout.addWidget(panel, 1)

            def load_data(data):
                _ui_trace(
                    "provider.ui.loaded",
                    provider=data.get("provider"),
                    profile_count=len(data.get("profiles", []) or []),
                    panel_geometry=panel.geometry().getRect(),
                )
                profiles.clear()
                for item in data.get("profiles", []):
                    provider_id = str(item.get("id") or "").strip()
                    if provider_id in cards:
                        profiles[provider_id] = dict(item)
                enabled.clear()
                active["value"] = str(data.get("provider") or "ollama")
                if active["value"] not in cards:
                    active["value"] = "ollama"
                enabled.update(
                    provider_id for provider_id in data.get("enabled_providers", [])
                    if provider_id in cards
                )
                enabled.add(active["value"])
                provider_state["loaded"] = True
                provider_state["pending"] = False
                for provider_id in cards:
                    update_card(provider_id)
                    cards[provider_id]["toggle"].setEnabled(True)
                status.setText("Профили загружены из backend. Состояние карточек актуально.")
                mark_saved()

            def test_all():
                provider_id = active["value"]
                status.setText(f"Проверяю {labels[provider_id]}…")
                run_operation("test", payload=provider_payload(provider_id), callback=lambda data: status.setText(str(data.get("message") or "Проверка завершена.")))

            def fetch_all_models():
                provider_id = active["value"]
                value = profile_for(provider_id)
                status.setText(f"Получаю модели {labels[provider_id]}…")
                params = {"provider": provider_id, "base_url": value.get("base_url", ""), "api_key": ""}
                def received(data):
                    models = [str(item) for item in data.get("models", []) if item]
                    if models:
                        status.setText("Модели получены: " + ", ".join(models[:5]))
                    else:
                        status.setText(str(data.get("message") or "Каталог моделей не найден."))
                run_operation("models", params=params, callback=received)

            test_button.clicked.connect(test_all)
            models_button.clicked.connect(fetch_all_models)
            saved.clicked.connect(save_state)
            QTimer.singleShot(0, lambda: run_operation("load", callback=load_data))

        ai_page = QWidget()
        ai_page_layout = QVBoxLayout(ai_page)
        ai_page_layout.setContentsMargins(0, 0, 0, 0)
        ai_inline(ai_page_layout, {})
        settings_stack.addWidget(ai_page)
        settings_stack.layout().setAlignment(ai_page, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        voice_page = QFrame()
        voice_page.setObjectName("settingsCard")
        voice_page.setMaximumWidth(960)
        voice_layout = QVBoxLayout(voice_page)
        voice_layout.setContentsMargins(20, 20, 20, 20)
        voice_layout.setSpacing(14)
        voice_form = QFormLayout()
        voice_form.setSpacing(14)
        voice_title = QLabel("ГОЛОС AI")
        voice_title.setObjectName("settingsCardTitle")
        voice_layout.addWidget(voice_title)
        voice_hint = QLabel(
            "Микрофон, голосовая модель и фраза диагностики. Состояние модели "
            "проверяется фактическим backend-инференсом."
        )
        voice_hint.setObjectName("settingsHint")
        voice_hint.setWordWrap(True)
        voice_layout.addWidget(voice_hint)

        self.startup_diagnostic_check = QCheckBox("Говорить диагностику при запуске")
        self.startup_diagnostic_check.setChecked(
            self.ui_settings.value("startup_diagnostic_enabled", True, type=bool)
        )
        self.startup_diagnostic_check.toggled.connect(self.set_startup_diagnostic_enabled)
        voice_form.addRow(self.startup_diagnostic_check)

        self.audio_source_combo = QComboBox()
        for label, device_id in self.enumerate_audio_sources():
            self.audio_source_combo.addItem(label, device_id)
        audio_index = self.audio_source_combo.findData(self.hardware_settings["audio_input_device"])
        self.audio_source_combo.setCurrentIndex(max(0, audio_index))
        self.audio_source_combo.currentIndexChanged.connect(self.apply_hardware_settings)
        voice_form.addRow(QLabel("Микрофон"), self.audio_source_combo)

        self.voice_model_combo = QComboBox()
        self.voice_model_combo.addItem(
            "Fish Audio — Джарвис (облачный профиль)", "fish_jarvis"
        )
        self.voice_model_combo.addItem(
            "Fish Audio — Дин Винчестер (отдельный ключ)", "fish_dean"
        )
        stored_voice_model = str(
            self.ui_settings.value("voice_model_id", "fish_jarvis") or "fish_jarvis"
        ).strip().lower()
        if stored_voice_model not in {"fish_jarvis", "fish_dean"}:
            stored_voice_model = "fish_jarvis"
            self.ui_settings.setValue("voice_model_id", stored_voice_model)
            self.ui_settings.sync()
        voice_model_index = self.voice_model_combo.findData(stored_voice_model)
        self.voice_model_combo.setCurrentIndex(max(0, voice_model_index))
        voice_form.addRow(QLabel("Голосовая модель"), self.voice_model_combo)
        save_voice_model_button = QPushButton("СОХРАНИТЬ ГОЛОСОВУЮ МОДЕЛЬ")
        save_voice_model_button.setObjectName("settingsTileButton")
        save_voice_model_button.clicked.connect(self.apply_voice_model_setting)
        self.voice_model_status_label = QLabel("Проверка доступности…")
        self.voice_model_status_label.setObjectName("settingsHint")
        self.voice_model_status_label.setWordWrap(True)
        voice_form.addRow(QLabel("Статус голоса"), self.voice_model_status_label)
        voice_form.addRow(QLabel("Фактический движок"), QLabel(
            "Fish Audio: S2.1 Pro Free"
        ))
        voice_layout.addLayout(voice_form)
        voice_layout.addStretch(1)
        voice_actions = QHBoxLayout()
        voice_actions.addWidget(save_voice_model_button)
        voice_actions.addStretch(1)
        voice_layout.addLayout(voice_actions)
        settings_stack.addWidget(voice_page)
        settings_stack.layout().setAlignment(voice_page, Qt.AlignLeft | Qt.AlignTop)
        QTimer.singleShot(0, self.apply_hardware_settings)

        def commands_inline(layout, edits, actions):
            command_path = Path(BASE_DIR).parent / "backend" / "voice_engine" / "commands.yaml"
            search = QLineEdit()
            search.setPlaceholderText("Поиск команды или голосовой фразы")
            layout.addWidget(search)
            command_view = QListWidget()
            command_view.setObjectName("commandsPreview")
            command_view.setMinimumSize(560, 300)
            command_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            command_view.setSpacing(5)
            layout.addWidget(command_view, 1)
            count_label = QLabel()
            count_label.setObjectName("settingsHint")
            layout.addWidget(count_label)
            try:
                import yaml
                command_data = yaml.safe_load(command_path.read_text(encoding="utf-8")) or {}
                command_rows = []
                for intent, phrases in command_data.items():
                    values = [str(item) for item in (phrases or [])]
                    command_rows.append((str(intent), values))
                    item = QListWidgetItem(f"{str(intent).upper()}\n" + "  • " + "\n  • ".join(values))
                    item.setData(Qt.UserRole, " ".join([str(intent), *values]).lower())
                    command_view.addItem(item)
                count_label.setText(f"Команд: {len(command_rows)}. Выберите фразу — обработка идёт через существующий router.")

                def filter_commands(value):
                    needle = value.lower().strip()
                    visible = 0
                    for index in range(command_view.count()):
                        item = command_view.item(index)
                        show = not needle or needle in str(item.data(Qt.UserRole))
                        item.setHidden(not show)
                        visible += int(show)
                    count_label.setText(f"Показано: {visible} из {len(command_rows)} команд")

                search.textChanged.connect(filter_commands)
            except Exception as error:
                command_view.addItem(f"Не удалось прочитать commands.yaml: {error}")
            edit_button = QPushButton("ОТКРЫТЬ ФАЙЛ КОМАНД")
            edit_button.clicked.connect(lambda: os.startfile(str(command_path)))
            actions.addWidget(edit_button)
            add_button = QPushButton("ДОБАВИТЬ СВОЮ КОМАНДУ")
            add_button.clicked.connect(lambda: self.open_preference_dialog("КОМАНДЫ JARVIS", fields=(("custom_commands", "Дополнительные команды", ""),)))
            actions.addWidget(add_button)
        section_page("КОМАНДЫ JARVIS", "Системные команды загружаются из backend/voice_engine/commands.yaml.", extra_builder=commands_inline)
        section_page("ПЕРСОНАЛИЗАЦИЯ", "Инструкции, предпочтительное обращение и локальная память.", fields=(("custom_instructions", "Ваши инструкции Jarvis", ""), ("preferred_address", "Как обращаться", "Данил")), checks=(("memory_enabled", "Использовать память", True),), max_width=960, min_width=0)
        section_page("КОНФИДЕНЦИАЛЬНОСТЬ", "История чатов и локальная диагностика.", fields=(), checks=(("history_enabled", "Сохранять историю", True), ("analytics_enabled", "Локальная диагностика", True),))
        def data_inline(layout, edits, footer):
            layout.addWidget(QLabel("Папка локальных данных"))
            data_path_edit = QLineEdit(str(self.ui_settings.value("data_path", str(Path(BASE_DIR).parent / "data"))))
            layout.addWidget(data_path_edit)
            backup_status = QLabel("Проверка фоновых резервных копий…")
            backup_status.setObjectName("settingsHint")
            backup_status.setWordWrap(True)
            layout.addWidget(backup_status)

            def refresh_backup_status():
                backup_now.setEnabled(False)
                backup_status.setText("Проверка фоновых резервных копий…")

                def success(data):
                    backup_now.setEnabled(True)
                    state = "включены" if data.get("enabled") else "не запущены"
                    backup_status.setText(
                        f"Фоновые резервные копии: {state}; интервал: {data.get('interval_hours', '?')} ч. "
                        f"Последняя: {data.get('last_backup') or 'ещё не создавалась'}"
                    )

                def failure(_error):
                    backup_now.setEnabled(True)
                    backup_status.setText("Backend недоступен: статус резервных копий не получен.")

                self._run_network_operation("backup-status", success, failure)

            def run_backup_now():
                if not backup_now.isEnabled():
                    return
                backup_now.setEnabled(False)
                backup_status.setText("Создание резервной копии…")

                def success(data):
                    backup_now.setEnabled(True)
                    backup_status.setText(f"Резервная копия создана: {data.get('path', '')}")

                def failure(_error):
                    backup_now.setEnabled(True)
                    backup_status.setText("Backup не выполнен: backend не ответил или вернул ошибку.")

                self._run_network_operation("backup-run", success, failure)

            save_path = QPushButton("СОХРАНИТЬ ПУТЬ")
            backup_now = QPushButton("СОЗДАТЬ КОПИЮ")
            save_path.setObjectName("settingsTileButton")
            backup_now.setObjectName("settingsTileButton")
            save_path.clicked.connect(lambda: (self.ui_settings.setValue("data_path", data_path_edit.text().strip()), self.ui_settings.sync(), backup_status.setText("Путь данных сохранён.")))
            backup_now.clicked.connect(run_backup_now)
            footer.addWidget(save_path)
            footer.addWidget(backup_now)
            QTimer.singleShot(0, refresh_backup_status)

        section_page("ДАННЫЕ", "Папка локальных данных и фоновые резервные копии.", extra_builder=data_inline)
        def chat_inline(layout, edits, actions):
            checks = []
            for key, label, fallback in (("chat_incoming_acrylic", "Стеклянные входящие сообщения", True), ("chat_outgoing_acrylic", "Стеклянные исходящие сообщения", False), ("chat_show_avatars", "Показывать аватары", True), ("chat_show_timestamps", "Показывать время сообщений", True), ("chat_compact_mode", "Компактный режим", False), ("chat_media_autoplay", "Автовоспроизведение медиа", False)):
                check = QCheckBox(label)
                check.setChecked(self.ui_settings.value(key, fallback, type=bool))
                checks.append((key, check))
                layout.addWidget(check)
            save = QPushButton("СОХРАНИТЬ НАСТРОЙКИ ЧАТА")
            save.setObjectName("settingsTileButton")
            save.clicked.connect(lambda: ([(self.ui_settings.setValue(key, check.isChecked())) for key, check in checks], self.ui_settings.sync(), self.assistant_label.setText("Настройки чата сохранены")))
            actions.addWidget(save)
        section_page("ЧАТ", "История, вложения, реакции, закрепления и медиаплееры.", extra_builder=chat_inline)
        settings_stack.addWidget(history_page)
        settings_stack.layout().setAlignment(history_page, Qt.AlignLeft | Qt.AlignTop)

        devices_page = QFrame()
        devices_page.setObjectName("settingsCard")
        devices_page.setMinimumWidth(0)
        devices_page.setMaximumWidth(960)
        devices_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        devices_layout = QVBoxLayout(devices_page)
        devices_layout.setContentsMargins(20, 12, 20, 20)
        devices_layout.setSpacing(0)
        devices_title = QLabel("УСТРОЙСТВА И ВОЗМОЖНОСТИ")
        devices_title.setObjectName("settingsCardTitle")
        devices_layout.addWidget(devices_title)
        devices_layout.addSpacing(10)
        devices_hint = QLabel(
            "Функции подключаются лениво. Обычные текстовые и голосовые ответы "
            "не запускают камеру, vision, жесты или CAD."
        )
        devices_hint.setObjectName("settingsHint")
        devices_hint.setWordWrap(True)
        devices_layout.addWidget(devices_hint)
        devices_layout.addSpacing(18)
        capability_specs = (
            ("camera", "Камера и видеозахват", "01_camera_video_capture.png"),
            ("vision", "Изображения и распознавание", "02_object_recognition.png"),
            ("gesture", "Жестовое управление", "03_gesture_control.png"),
            ("printer", "Принтер", "04_3d_printer.png"),
            ("cad", "CAD / 3D-генерация", "05_cad_3d_generation.png"),
            ("streaming", "Потоковое аудио / видео", "06_streaming_audio_video.png"),
            ("cuda", "CUDA / GPU", "07_cuda_gpu.png"),
            ("external_devices", "Внешние устройства / LAN", "08_external_devices_lan.png"),
        )
        capability_grid_host = QWidget()
        capability_grid_host.setObjectName("capabilityGrid")
        capability_grid = QGridLayout(capability_grid_host)
        capability_grid.setContentsMargins(0, 8, 0, 8)
        capability_grid.setHorizontalSpacing(14)
        capability_grid.setVerticalSpacing(14)
        capability_grid.setColumnStretch(0, 1)
        capability_grid.setColumnStretch(1, 1)
        capability_cards = {}
        capability_details = {}
        capability_assets_dir = Path(BASE_DIR) / "assets" / "capabilities"
        for index, (capability_id, capability_name, asset_name) in enumerate(capability_specs):
            card = CapabilityCard(capability_name, capability_assets_dir / asset_name)
            capability_grid.addWidget(card, index // 2, index % 2)
            capability_cards[capability_id] = card
        devices_layout.addWidget(capability_grid_host)
        devices_layout.addStretch(1)
        devices_status = QLabel("Проверка возможностей…")
        devices_status.setObjectName("settingsHint")
        devices_status.setWordWrap(True)
        devices_layout.addWidget(devices_status)
        devices_layout.addSpacing(12)

        def refresh_capabilities(deep=False):
            if not refresh_devices.isEnabled():
                return
            refresh_devices.setEnabled(False)
            devices_status.setText("Проверка возможностей…")

            def success(data):
                refresh_devices.setEnabled(True)
                for capability in data.get("capabilities", []):
                    capability_id = str(capability.get("id", ""))
                    card = capability_cards.get(capability_id)
                    if card is None:
                        continue
                    available = bool(capability.get("available"))
                    capability_details[capability_id] = capability
                    card.set_capability_state(
                        str(capability.get("name", capability_id)),
                        available,
                        str(capability.get("status", "нет данных")),
                    )
                    card.setToolTip(str(capability.get("details") or ""))
                devices_status.setText(
                    "Готово. Глубокая проверка необязательных модулей выполняется только по кнопке."
                    if not deep else "Глубокая проверка завершена. Тяжёлые адаптеры запускаются только при вызове."
                )

            def failure(_error):
                refresh_devices.setEnabled(True)
                devices_status.setText("Backend недоступен: возможности не получены. Повторите проверку.")

            self._run_network_operation("capabilities", success, failure, params={"deep": deep})

        def capture_camera():
            if not snapshot_button.isEnabled():
                return
            snapshot_button.setEnabled(False)
            devices_status.setText("Получение кадра…")

            def success(data):
                snapshot_button.setEnabled(True)
                devices_status.setText(f"Кадр сохранён: {data.get('path', 'неизвестный путь')}")

            def failure(_error):
                snapshot_button.setEnabled(True)
                devices_status.setText("Снимок не выполнен: backend не ответил или вернул ошибку.")

            self._run_network_operation(
                "camera-snapshot", success, failure,
                params={"index": int(self.hardware_settings.get("video_input_device", 0))},
            )

        def activate_capability(capability_id):
            capability = capability_details.get(capability_id, {})
            details = str(capability.get("details") or "")
            if capability_id == "camera":
                capture_camera()
                return
            if capability_id == "gesture":
                self._jump_to_settings_section("КОМАНДЫ")
                return
            if capability_id == "streaming":
                self._jump_to_settings_section("ГОЛОС AI")
                return
            if capability_id == "cuda":
                self._jump_to_settings_section("AI")
                return
            if capability_id in {"vision", "printer", "cad", "external_devices"}:
                devices_status.setText(
                    ((details + " ") if details else "")
                    + "Функция вызывается из чата; открыт новый диалог."
                )
                self.menu.setCurrentRow(1)

        for capability_id, card in capability_cards.items():
            card.clicked.connect(
                lambda _checked=False, selected=capability_id: activate_capability(selected)
            )

        devices_actions = QHBoxLayout()
        devices_actions.setSpacing(12)
        refresh_devices = QPushButton("ОБНОВИТЬ СТАТУСЫ")
        snapshot_button = QPushButton("СДЕЛАТЬ СНИМОК")
        refresh_devices.setObjectName("providerAction")
        snapshot_button.setObjectName("providerAction")
        refresh_devices.setFixedSize(220, 38)
        snapshot_button.setFixedSize(220, 38)
        refresh_devices.clicked.connect(lambda: refresh_capabilities(True))
        snapshot_button.clicked.connect(capture_camera)
        devices_actions.addWidget(refresh_devices)
        devices_actions.addWidget(snapshot_button)
        devices_actions.addStretch(1)
        devices_layout.addLayout(devices_actions)
        QTimer.singleShot(0, refresh_capabilities)
        self.pages.addWidget(settings_page)
        self.pages.addWidget(devices_page)
        QTimer.singleShot(350, self.position_settings_header)

        # страница команд
        commands_page = QWidget()
        commands_layout = QVBoxLayout(commands_page)
        commands_layout.addWidget(QLabel("НАСТРОЙКИ"))
        self.pages.addWidget(commands_page)

        main.addLayout(left)
        main.addWidget(self.pages)

        container_layout.addLayout(main)

        root.addWidget(container)

        self.apply_styles()

    # ---------------- USER PROFILE ----------------

    def _refresh_user_profile_card(self, profile=None):
        profile = profile or {
            "display_name": self.ui_settings.value("profile_display_name", "Данил"),
            "username": self.ui_settings.value("profile_username", "sheff"),
            "avatar_path": self.ui_settings.value("profile_avatar_path", ""),
        }
        name = str(profile.get("display_name") or "Данил")
        username = str(profile.get("username") or "sheff")
        self.profile_name_label.setText(name)
        self.profile_username_label.setText(f"@{username}")
        avatar_path = Path(str(profile.get("avatar_path") or ""))
        if avatar_path.is_file():
            pixmap = QPixmap(str(avatar_path)).scaled(
                42, 42, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.profile_avatar.setPixmap(pixmap)
            self.profile_avatar.setText("")
        else:
            self.profile_avatar.clear()
            self.profile_avatar.setText(name[:1].upper())
        self._refresh_chat_identity()
        self._refresh_active_chat_visuals()

    def _profile_avatar_url(self):
        path = Path(str(self.ui_settings.value("profile_avatar_path", "") or ""))
        if not path.is_file():
            return ""
        return QUrl.fromLocalFile(str(path.resolve())).toString()

    def _refresh_chat_identity(self):
        if not hasattr(self, "chat_avatar"):
            return
        self.chat_avatar.setStyleSheet(
            f"background:{self.accent_hex}; color:#071018; border-radius:20px; "
            "font-size:18px; font-weight:bold;"
        )
        if hasattr(self, "chat_view"):
            self.chat_view.page().runJavaScript(
                "window.applyThemeSettings && window.applyThemeSettings(" +
                json.dumps({
                    "accent_color": self.accent_hex,
                    "user_avatar_path": self._profile_avatar_url(),
                }, ensure_ascii=False) + ");"
            )

    def show_user_profile(self):
        self._sync_authenticated_email_to_profile()
        dialog = UserProfileDialog(self.ui_settings, self.accent_hex, self, self.dialog_stylesheet())
        dialog.saved.connect(self._refresh_user_profile_card)
        dialog.exec()

    def _account_section_extra(self, layout, edits, actions):
        del layout, edits
        button = QPushButton("ОТКРЫТЬ ACCOUNT CENTER")
        button.setObjectName("settingsTileButton")
        button.clicked.connect(self.show_account_center)
        actions.addWidget(button)

    def show_account_center(self):
        coordinator = self._account_coordinator
        if coordinator is None:
            self.assistant_label.setText("Account Layer недоступен; Local Mode продолжает работать")
            return
        dialog = AccountCenterDialog(coordinator, self)
        dialog.exec()

    def _sync_authenticated_email_to_profile(self):
        """Expose the verified Account identity in both local profile views."""
        coordinator = getattr(self, "_account_coordinator", None)
        if coordinator is None:
            return
        try:
            email = str(coordinator.context().account.email or "").strip()
        except (AttributeError, OSError, ValueError, TypeError):
            return
        if email and not str(self.ui_settings.value("profile_email", "")).strip():
            self.ui_settings.setValue("profile_email", email)
            self.ui_settings.sync()

    # ---------------- WEATHER ----------------

    @staticmethod
    def _read_local_env_value(name):
        """Read one local development value without exposing the env file."""
        candidates = (
            Path(BASE_DIR).parent / "backend" / "dev.env",
            Path(BASE_DIR).parent / "backend" / ".env",
        )
        prefix = f"{name}="
        for env_path in candidates:
            try:
                if not env_path.is_file():
                    continue
                for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or not line.startswith(prefix):
                        continue
                    value = line[len(prefix):].strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    return value.strip() or None
            except (OSError, UnicodeError):
                continue
        return None

    @staticmethod
    def _tech_weather_code(condition_id, icon_code):
        """Map OpenWeather conditions to the original TECH-A 0..47 icons."""
        condition_id = int(condition_id or 0)
        is_night = str(icon_code or "").endswith("n")

        if 200 <= condition_id <= 232:
            return 37 if condition_id in (200, 201, 230, 231) else 38
        if 300 <= condition_id <= 321:
            return 9
        if condition_id == 511:
            return 10
        if 500 <= condition_id <= 504:
            return 12
        if 520 <= condition_id <= 531:
            return 40 if condition_id in (520, 521, 522) else 11
        if 600 <= condition_id <= 602:
            return 13 if condition_id == 600 else (41 if condition_id == 602 else 16)
        if 611 <= condition_id <= 616:
            return 18
        if 620 <= condition_id <= 622:
            return 42 if condition_id == 621 else 14
        if condition_id == 781:
            return 0
        if condition_id in (701, 711, 721, 731, 741, 751, 761, 762, 771):
            if condition_id == 741:
                return 20
            if condition_id in (721, 731, 751, 761):
                return 21 if condition_id == 721 else 19
            if condition_id == 711:
                return 22
            return 23
        if condition_id == 800:
            return 31 if is_night else 32
        if condition_id == 801:
            return 29 if is_night else 30
        if condition_id == 802:
            return 29 if is_night else 30
        if condition_id in (803, 804):
            return 27 if is_night else 28
        return None

    @classmethod
    def _load_tech_weather_icon(cls, condition_id, icon_code):
        code = cls._tech_weather_code(condition_id, icon_code)
        weather_dir = Path(BASE_DIR) / "assets" / "WEATHER"
        icon_path = weather_dir / f"{code}.png" if code is not None else weather_dir / "na.png"
        if not icon_path.is_file():
            icon_path = weather_dir / "na.png"
        pixmap = QPixmap(str(icon_path))
        return pixmap, code, icon_path.name

    def open_detached_weather(self):
        """Show a desktop copy while keeping the sidebar card untouched."""
        self.set_detached_weather_visible(True)
        floating = getattr(self, "detached_weather", None)
        if floating is None:
            floating = FloatingWeatherWidget(self)
            self.detached_weather = floating
            floating.apply_saved_size(self.widget_settings.get("weather_detached_size", "medium"))
            position = self.widget_settings.get("weather_detached_position", {})
            if isinstance(position, dict) and {"x", "y"}.issubset(position):
                floating.move(int(position["x"]), int(position["y"]))
            else:
                screen = QApplication.primaryScreen()
                available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 850)
                floating.move(available.right() - floating.width() - 30, available.top() + 120)
        floating.refresh_from_owner()
        floating.show()
        floating.raise_()
        floating.activateWindow()

    def set_detached_weather_visible(self, visible):
        self.widget_settings["weather_detached_visible"] = bool(visible)
        self.ui_settings.setValue(
            "widget_settings", json.dumps(self.widget_settings, ensure_ascii=False)
        )

    def save_detached_weather_position(self, widget):
        self.widget_settings["weather_detached_position"] = {
            "x": widget.x(), "y": widget.y()
        }
        self.ui_settings.setValue(
            "widget_settings", json.dumps(self.widget_settings, ensure_ascii=False)
        )

    def set_detached_weather_opacity(self, opacity):
        value = max(35, min(100, int(opacity)))
        self.widget_settings["weather_detached_opacity"] = value
        self.ui_settings.setValue(
            "widget_settings", json.dumps(self.widget_settings, ensure_ascii=False)
        )
        if getattr(self, "detached_weather", None) is not None:
            self.detached_weather.setWindowOpacity(1.0)
            self.detached_weather.card.setStyleSheet(self.detached_weather._card_stylesheet())

    def apply_weather_card_settings(self):
        """Apply saved visual positions and scales to the live weather card."""
        card = getattr(self, "weather_card", None)
        if card is None:
            return
        values = self.widget_settings.get("weather", {})
        card_width = int(values.get("card_width", 220))
        card_height = int(values.get("card_height", 110))
        card.setFixedSize(card_width, card_height)
        labels = (
            ("city", self.weather_city_label, "city_font", 14, 12, 8, 92, 24),
            ("temp", self.weather_temp_label, "temp_font", 16, 12, 42, 92, 28),
            ("desc", self.weather_desc_label, "desc_font", 12, 12, 82, 108, 24),
        )
        for name, label, font_key, default_font, default_x, default_y, default_w, default_h in labels:
            font_size = int(values.get(font_key, default_font))
            label.setStyleSheet(f"color:white; font-size:{font_size}px;")
            label.setGeometry(
                int(values.get(f"{name}_x", default_x)),
                int(values.get(f"{name}_y", default_y)),
                int(values.get(f"{name}_w", default_w)),
                int(values.get(f"{name}_h", default_h)),
            )
        icon_size = int(values.get("icon_size", 64))
        self.weather_icon.setGeometry(
            int(values.get("icon_x", card_width - icon_size - 12)),
            int(values.get("icon_y", (card_height - icon_size) // 2)),
            icon_size,
            icon_size,
        )
        current_pixmap = self.weather_icon.pixmap()
        if current_pixmap and not current_pixmap.isNull():
            self.weather_icon.setPixmap(
                current_pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        card.raise_()
        self.weather_icon.raise_()
        self.weather_city_label.raise_()
        self.weather_temp_label.raise_()
        self.weather_desc_label.raise_()

    def load_weather(self):
        self._weather_generation += 1
        generation = self._weather_generation
        api_key = str(self.ui_settings.value("weather_api_key", "")).strip() or os.getenv("OPENWEATHER_API_KEY") or self._read_local_env_value(
            "OPENWEATHER_API_KEY"
        )
        if not api_key:
            self.weather_city_label.setText("Мурино")
            self.weather_temp_label.setText("--°C")
            self.weather_desc_label.setText("не настроена")
            return
        city = str(self.ui_settings.value("weather_city", "")).strip() or os.getenv("WEATHER_CITY") or self._read_local_env_value(
            "WEATHER_CITY"
        )
        self.weather_desc_label.setText("загрузка...")
        self._run_network_operation(
            "weather",
            lambda data: self._apply_weather_result(data, generation),
            lambda error: self._weather_fetch_failed(error, generation),
            payload={"city": city, "api_key": api_key},
        )

    def _apply_weather_result(self, data, generation):
        if generation != self._weather_generation:
            return
        pixmap, _, _ = self._load_tech_weather_icon(data.get("condition_id"), data.get("icon_code"))
        self.weather_icon.setPixmap(
            pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.weather_city_label.setText(str(data["city"]))
        self.weather_temp_label.setText(f"{data['temp']}°C")
        self.weather_desc_label.setText(str(data["description"]))
        if getattr(self, "detached_weather", None) is not None:
            self.detached_weather.refresh_from_owner()

    def _weather_fetch_failed(self, _error, generation):
        if generation != self._weather_generation:
            return
        self.weather_city_label.setText("Мурино")
        self.weather_temp_label.setText("--°C")
        self.weather_desc_label.setText("недоступна")
        if getattr(self, "detached_weather", None) is not None:
            self.detached_weather.refresh_from_owner()

    def _validate_and_save_weather(self, city, key, status, button):
        if not city or not key:
            status.setText("Укажи город и API key.")
            return
        button.setEnabled(False)
        status.setText("Проверка подключения...")

        def success(data):
            self.ui_settings.setValue("weather_city", city)
            self.ui_settings.setValue("weather_api_key", key)
            self.ui_settings.sync()
            self._weather_generation += 1
            self._apply_weather_result(data, self._weather_generation)
            button.setEnabled(True)
            status.setText("Проверка успешна. Погода обновлена.")

        def failure(_error):
            button.setEnabled(True)
            status.setText("Проверка не пройдена: проверь город или API key.")

        self._run_network_operation(
            "weather-validate", success, failure,
            payload={"city": city, "api_key": key},
        )

    # ---------------- STYLES ----------------

    def apply_styles(self):

        accent = self.accent_hex
        accent_hover = self.accent_color.lighter(120).name()
        accent_rgb = self.accent_color.getRgb()[:3]
        accent_soft = f"rgba({accent_rgb[0]},{accent_rgb[1]},{accent_rgb[2]},0.12)"
        tint = QColor(self.visual_settings.get("glass_tint", "#00AAFF"))
        tint_rgb = tint.getRgb()[:3] if tint.isValid() else (0, 170, 255)
        glass_rgb = tuple(round(base * 0.68 + component * 0.32) for base, component in zip((12, 18, 24), tint_rgb))
        if self.visual_settings.get("glass_enabled", True):
            container_background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 rgba({glass_rgb[0]},{glass_rgb[1]},{glass_rgb[2]},220),"
                f"stop:0.35 rgba({max(0, glass_rgb[0]-5)},{max(0, glass_rgb[1]-5)},{max(0, glass_rgb[2]-5)},220),"
                f"stop:0.65 rgba({max(0, glass_rgb[0]-9)},{max(0, glass_rgb[1]-9)},{max(0, glass_rgb[2]-9)},230),"
                f"stop:1 rgba({glass_rgb[0]+8},{glass_rgb[1]+8},{glass_rgb[2]+8},220))"
            )
        else:
            container_background = "rgba(15,15,20,245)"

        stylesheet = ("""

#container{

border-radius:30px;

background:__JARVIS_CONTAINER_BACKGROUND__;

border:1px solid rgba(255,255,255,40);

}

#container[widgetMode="true"]{
background:transparent;
border:none;
}

#title{
font-size:20px;
font-weight:bold;
color:#2E89FF;
}

#tandemFooter{
color:#ffffff;
font-size:12px;
padding:3px 16px 7px 16px;
}

#tandemFooter:hover{
color:#00EBF5;
}

QListWidget {
background: transparent;
color: #FFFFFF;
border: none;
outline: none;
}

#menu{
background: transparent;
border: none;
outline: none;
}

#settingsNavigation{
background: rgba(10,12,18,90);
border: 1px solid rgba(255,255,255,35);
border-radius: 12px;
padding: 6px;
outline: none;
}

#settingsNavigation::item{
color: rgba(255,255,255,190);
padding: 10px 8px;
margin: 2px 0;
border-radius: 8px;
}

#settingsNavigation::item:selected{
background: #00aef0;
color: #FFFFFF;
}

#menu::item{
height:44px;
color:white;
padding-left:14px;
border-radius:10px;
}

#menu::item:selected{
background:#2E89FF;
color:#111111;
}

#menu::item:hover{
background:#2E89FF;
color:white;
}

#hudPanelTop{
background:transparent;
border:1px solid transparent;
border-radius:4px;
color:#FFFFFF;
font-size:8px;
padding:1px 4px;
}

#hudPanelTop:hover{
background:transparent;
border:1px solid transparent;
color:#FFFFFF;
}

#hudPanelIcon{
background:transparent;
border:1px solid transparent;
border-radius:6px;
}

#hudPanelIcon:hover{
background:transparent;
border:1px solid transparent;
}

#hudPanelTop:focus,
#hudPanelIcon:focus{
background:transparent;
border:1px solid transparent;
outline:none;
}
                           
#chatList{
background: transparent;
border: none;
outline: none;
}

#chatList::item{
color:white;
padding:0;
margin:0;
border:none;
background:transparent;
}

#chatList::item:selected{
background:transparent;
}

#chatList::item:hover{
background:transparent;
}

#chatItem{
border-radius:8px;
background:transparent;
}

#chatItem:hover{
background: rgba(255,255,255,0.05);
}

#techTool{
background:transparent;
border:none;
padding:0;
}

#techTool:hover{
background:transparent;
border:none;
}

QPushButton{
border:none;
}

QPushButton:hover{
color:white;
}                                                      

#miniCard{
border:1px solid rgba(255,255,255,40);
border-radius:10px;
background:rgba(255,255,255,0.08);
}

#profileCard{
border:1px solid rgba(255,255,255,45);
border-radius:10px;
background:rgba(255,255,255,0.08);
text-align:left;
}

#profileCard:hover{
border:1px solid #2E89FF;
background:rgba(0,235,245,0.12);
}

#profileCardName{
color:#FFFFFF;
font-size:14px;
font-weight:bold;
}

#profileCardUsername{
color:rgba(255,255,255,160);
font-size:11px;
}

QCheckBox::indicator:checked{
background:#2E89FF;
}       

QLabel{
color:#FFFFFF;
}

QCheckBox, QRadioButton, QGroupBox{
color:#FFFFFF;
}

QComboBox{
color:#f0f4f8;
background:rgba(4,10,18,180);
border:1px solid rgba(255,255,255,55);
border-radius:8px;
padding:4px 8px;
}

QComboBox QAbstractItemView{
color:#f0f4f8;
background:#171b24;
selection-background-color:#00aaff;
selection-color:#071116;
}

#settingsTitle{
font-size:22px;
font-weight:bold;
color:#FFFFFF;
}

#settingsCard{
background:rgba(10,12,18,118);
border:1px solid rgba(255,255,255,35);
border-radius:24px;
}

QFrame#settingsGlassTile{
background:rgba(8,12,14,185);
border:1px solid rgba(255,255,255,28);
border-radius:14px;
}

QFrame#settingsGlassTile QLabel { color:#dce8eb; }
QFrame#settingsGlassTile QLabel[role="hint"] { color:#71858b; font-size:10px; }
QFrame#settingsGlassTile QPushButton {
min-height:28px; padding:0 12px; border-radius:9px;
color:#dce8eb; background:__SETTINGS_ACCENT_SOFT_18__;
border:1px solid #00aaff;
}
QFrame#settingsGlassTile QPushButton:hover { background:__SETTINGS_ACCENT_SOFT_38__; }
QFrame#settingsGlassTile QComboBox {
min-height:26px; padding:0 8px; color:#dce8eb;
background:transparent; border:none;
}
QFrame#settingsGlassTile QSlider::groove:horizontal {
height:1px; background:rgba(220,232,235,150);
}
QFrame#settingsGlassTile QSlider::handle:horizontal {
width:12px; height:12px; margin:-6px 0;
border-radius:6px; background:#00aaff; border:none;
}

#capabilityGrid { background:transparent; border:none; }
#capabilityCard {
text-align:left;
padding:0;
background:rgba(8,12,14,185);
border:1px solid rgba(166,242,242,33);
border-radius:14px;
}
#capabilityCardTitle { color:#dcecf4; font-size:14px; font-weight:700; }
#capabilityCardStatus { color:#71858b; font-size:10px; font-weight:400; }
#capabilityCardImageSlot, #capabilityCardImage { background:transparent; border:none; }
#capabilityCard:hover {
background:rgba(0,170,255,24);
border:1px solid #00aaff;
}
#capabilityCard[available="true"] { border:1px solid rgba(0,170,255,165); }
#capabilityCard[available="true"] #capabilityCardStatus { color:#00aaff; }

#settingsScroll, #settingsScrollViewport, #settingsContent {
background: transparent;
border: none;
}

#settingsCardTitle{
font-size:18px;
font-weight:bold;
color:#eef5f7;
}

#settingsHint{
color:#73909a;
font-size:11px;
}

#historyList, #historyListViewport{
background:transparent;
border:none;
}

QWidget#historyRow{
background:rgba(8,12,14,185);
border:1px solid rgba(166,242,242,33);
border-radius:14px;
}

QWidget#historyRow:hover,
QWidget#historyRow[active="true"]{
background:rgba(0,170,255,24);
border:1px solid #00aaff;
}

#historyRefresh{
background:transparent;
border:1px solid #00aaff;
border-radius:9px;
color:#dcecf4;
padding:3px 16px;
font-weight:600;
}

#historyRefresh:hover{
background:rgba(0,170,255,35);
}

#settingsPage QLabel,
#settingsPage QCheckBox,
#settingsPage QRadioButton,
#settingsPage QGroupBox,
#settingsPage QFormLabel{
color:#FFFFFF;
}

#settingsPage QPushButton{
background:transparent;
color:#dcecf4;
border:1px solid #00aaff;
border-radius:9px;
min-height:34px;
max-width:280px;
padding:3px 16px;
font-weight:600;
}

#settingsPage QPushButton:hover{ background:rgba(0,170,255,35); }
#settingsPage QPushButton:pressed{ background:rgba(0,170,255,60); }
#settingsPage QPushButton:disabled{
color:rgba(220,236,244,115);
border-color:rgba(0,170,255,90);
background:rgba(0,170,255,12);
}

#settingsPage QPlainTextEdit{
background:rgba(4,10,18,180);
color:#FFFFFF;
border:1px solid rgba(255,255,255,55);
border-radius:8px;
}

#providerModelsPanel{
background:rgba(10,12,18,118);
border:1px solid rgba(255,255,255,35);
border-radius:24px;
}

#providerModelsTitle{
font-size:20px;
font-weight:700;
color:#f0f4f8;
}

#providerModelsSubtitle{
font-size:12px;
color:#8c9baa;
}

#providerSaved, #providerConfigure, #providerAction{
background:transparent;
border:1px solid #00aaff;
border-radius:9px;
color:#dcecf4;
font-weight:600;
}

#providerSaved{
color:#00aaff;
}

#providerSaved:disabled{
color:#00aaff;
}

#providerConfigure:hover, #providerAction:hover{
background:rgba(0,170,255,35);
}

#providerModelCard{
background:rgba(0,0,0,61);
border:1px solid rgba(166,242,242,33);
border-radius:13px;
}

#providerModelCard[active="true"]{
border:1px solid #00aaff;
}

#providerModelName{
font-size:14px;
font-weight:700;
color:#f0f4f8;
}

#providerModelValue{
font-size:12px;
color:#8c9baa;
}

#providerModelToggle{
background:rgba(0,0,0,0);
border:1px solid rgba(0,170,255,120);
border-radius:14px;
padding:0 6px;
color:#00aaff;
font-size:11px;
font-weight:700;
}

#providerModelToggle:checked{
background:#e4edf1;
color:#00aaff;
}

#providerModelToggle::indicator{
width:0px;
height:0px;
}
                                               
#chatFrame{

border-radius:30px;
border:1px solid rgba(255,255,255,40);

background:qlineargradient(
x1:0,y1:0,
x2:1,y2:1,
stop:0 rgba(30,30,35,220),
stop:0.3 rgba(20,20,25,220),
stop:0.7 rgba(15,15,20,230),
stop:1 rgba(35,35,40,220)
);

}

#chatWebSurface,
#jarvisChatWebView{
background:#121212;
border:none;
}

#chatHeader{
background:rgba(24,28,34,0.72);
border:1px solid rgba(255,255,255,35);
border-radius:12px;
}

#chatAvatar{
background:#00EBF5;
color:#071018;
border-radius:20px;
font-size:18px;
font-weight:bold;
}

#chatTitle{
color:#FFFFFF;
font-size:15px;
font-weight:600;
}

#chatSubtitle{
color:rgba(255,255,255,150);
font-size:11px;
}

#chatSettingsBtn{
background:transparent;
border:none;
border-radius:7px;
padding:6px;
}

#chatSettingsBtn:hover{
background:rgba(0,235,245,0.16);
}

QLineEdit{
background:rgba(4,10,18,180);
color:#f0f4f8;
border:1px solid rgba(255,255,255,55);
border-radius:10px;
padding:5px 10px;
}

QSpinBox, QPlainTextEdit, QTextEdit{
background:rgba(4,10,18,180);
color:#f0f4f8;
border:1px solid rgba(255,255,255,55);
border-radius:8px;
padding:5px;
}

QPushButton{
background:#2E89FF;
border:none;
border-radius:8px;
color:white;
}

QPushButton:hover{
background:#4aa0ff;
}

#closeBtn{
background:#ff4d4d;
}

#closeBtn:hover{
background:#ff2c2c;
}

#jarvisStart{
color:rgba(235,250,255,245);
font-size:26px;
font-weight:bold;
letter-spacing:3px;
border-radius:75px;
border:1px solid rgba(220,250,255,180);
background:qradialgradient(
cx:0.5, cy:0.42, radius:0.62,
 stop:0 rgba(220,250,255,235),
 stop:0.34 rgba(90,190,230,220),
 stop:0.72 rgba(25,70,100,235),
 stop:1 rgba(8,18,28,245)
);
}

#jarvisStart:hover{
border:2px solid rgba(235,255,255,230);
background:qradialgradient(
cx:0.5, cy:0.42, radius:0.62,
 stop:0 rgba(240,255,255,245),
 stop:0.34 rgba(80,210,255,230),
 stop:1 rgba(8,18,28,245)
);
}

#jarvisStart:focus{
outline:none;
}

#jarvisStart[active="true"]{
color:#bdf7ff;
border:2px solid rgba(0,220,255,235);
background:qradialgradient(
cx:0.5, cy:0.42, radius:0.62,
 stop:0 rgba(235,255,255,245),
 stop:0.32 rgba(0,210,255,235),
 stop:1 rgba(5,35,55,248)
);
}
                           
                         
QCheckBox::indicator{
width:40px;
height:22px;
border-radius:11px;
background:#444;
}

/* Provider cards follow the Figma outline controls, after the global button
   and checkbox rules so they cannot be overridden by the app theme. */
#providerModelsPanel #providerConfigure,
#providerModelsPanel #providerAction,
#providerModelsPanel #providerSaved{
background:transparent;
border:1px solid #00aaff;
border-radius:9px;
color:#dcecf4;
}

#providerModelsPanel #providerConfigure:hover,
#providerModelsPanel #providerAction:hover{
background:rgba(0,170,255,35);
}

#providerModelsPanel #providerSaved,
#providerModelsPanel #providerSaved:disabled{
color:#00aaff;
}

#providerModelsPanel #providerModelToggle{
width:69px;
height:28px;
padding:0 6px;
border:1px solid #00aaff;
border-radius:14px;
background:transparent;
color:#00aaff;
}

#providerModelsPanel #providerModelToggle:checked{
background:#e4edf1;
color:#00aaff;
}

#providerModelsPanel #providerModelToggle::indicator{
width:22px;
height:22px;
border:none;
border-radius:11px;
background:#00aaff;
}

#providerModelsPanel #providerModelToggle:checked::indicator{
background:#00aaff;
}

""".replace("#2E89FF", accent)
        .replace("#4aa0ff", accent_hover)
        .replace("#00aef0", accent)
        .replace("#00aaff", accent)
        .replace("#00EBF5", accent)
        .replace("rgba(0,235,245,0.12)", accent_soft)
        .replace("#FFFFFF", self.text_color_hex)
        .replace("__SETTINGS_ACCENT_SOFT_18__", f"rgba({accent_rgb[0]},{accent_rgb[1]},{accent_rgb[2]},18)")
        .replace("__SETTINGS_ACCENT_SOFT_38__", f"rgba({accent_rgb[0]},{accent_rgb[1]},{accent_rgb[2]},38)")
        .replace(
            "__JARVIS_CONTAINER_BACKGROUND__",
             "transparent" if getattr(self, "widget_mode", False) else container_background,
        ))
        self.setStyleSheet(stylesheet)

        if hasattr(self, "chat_avatar"):
            self.chat_avatar.setStyleSheet(
                f"background:{accent}; color:#071018; border-radius:20px; "
                "font-size:18px; font-weight:bold;"
            )

        if hasattr(self, "chats_list"):
            self.chats_list.setStyleSheet(f"""
                QListWidget#chatList, QListWidget#pinnedChatList {{
                    background: transparent;
                    border: none;
                    outline: none;
                }}
                QListWidget#historyList {{
                    background: transparent;
                    border: none;
                    outline: none;
                }}
                QListWidget#chatList::item, QListWidget#pinnedChatList::item {{
                    color: {self.text_color_hex};
                    padding: 0;
                    margin: 0;
                    border: none;
                    background: transparent;
                }}
                QListWidget#chatList::item:selected,
                QListWidget#chatList::item:hover,
                QListWidget#pinnedChatList::item:selected,
                QListWidget#pinnedChatList::item:hover {{
                    background: transparent;
                    border: none;
                    outline: none;
                }}
                QListWidget#historyList::item,
                QListWidget#historyList::item:selected,
                QListWidget#historyList::item:hover {{
                    background: transparent;
                    border: none;
                    outline: none;
                    padding: 0;
                }}
                QLabel#chatSectionLabel {{
                    color: {self.accent_hex};
                    font-size: 11px;
                    font-weight: 600;
                    padding-left: 2px;
                }}
                QScrollBar:vertical {{
                    width: 4px;
                    background: transparent;
                    margin: 0;
                }}
                QScrollBar::handle:vertical {{
                    min-height: 22px;
                    background: {self.accent_hex};
                    border-radius: 2px;
                }}
                QScrollBar::handle:vertical:hover {{ background: {accent_hover}; }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    height: 0;
                    background: transparent;
                }}
            """)

        if hasattr(self, "settings_nav"):
            self.settings_nav.setStyleSheet(f"""
                QListWidget#settingsNavigation {{
                    background: rgba(10,12,18,90); border: 1px solid rgba(255,255,255,35);
                    border-radius: 12px; padding: 6px; outline: none;
                }}
                QListWidget#settingsNavigation::item {{
                    color: rgba(255,255,255,190); padding: 10px 8px; margin: 2px 0; border-radius: 8px;
                }}
                QListWidget#settingsNavigation::item:selected {{ background: {accent}; color: #FFFFFF; }}
            """)

        if hasattr(self, "general_page"):
            if hasattr(self, "glass_enabled_check"):
                self.glass_enabled_check.set_accent_color(accent)
            self._refresh_font_choice_state()

        self._refresh_start_button_style()

    # ---------------- COMMAND ----------------

    def send_command(self, text=None, attachments=None):
        if text is None:
            text = self.composer.message_input.toPlainText().strip()
        attachments = attachments or []
        text = str(text).strip()
        if not text and not attachments:
            return
        if getattr(self, "_chat_request_in_flight", False):
            return

        display_text = text or "[Вложение]"
        local_user_id = self.add_message(display_text, True, attachments=attachments)
        self._chat_request_local_id = local_user_id
        self._chat_request_display_text = display_text
        self._chat_request_chat_id = getattr(self, "current_chat_id", "default")
        self._recent_chat_sequence += 1
        self._recent_chat_activity[str(self._chat_request_chat_id)] = self._recent_chat_sequence
        self.load_chat_sessions()
        self._chat_request_turn_id = str(uuid.uuid4())
        self._chat_request_cancelled = False
        self._chat_request_in_flight = True
        self._chat_overlay_generation = getattr(self, "_chat_overlay_generation", 0) + 1
        self._set_chat_status_override("#00aaff", "Jarvis обрабатывает запрос", 90.0)
        self._set_text_turn_overlay_state("processing")
        self._chat_request_processing_id = self.add_message(
            "[Processing...]", False, status="processing"
        )
        self.composer.set_sending(True)
        self._run_network_operation(
            "chat-send",
            self._chat_request_finished,
            self._chat_request_failed,
            payload={
                "message": text,
                "attachments": attachments,
                "chat_id": self._chat_request_chat_id,
                "turn_id": self._chat_request_turn_id,
                "custom_instructions": str(self.ui_settings.value("custom_instructions", "") or ""),
                "preferred_address": str(self.ui_settings.value("preferred_address", "") or ""),
                "chat_system_prompt": str(self.ui_settings.value("chat_system_prompt", "") or ""),
            },
        )
        self._start_runtime_delta_worker()

    def _start_runtime_delta_worker(self):
        self._stop_runtime_delta_worker()
        turn_id = getattr(self, "_chat_request_turn_id", "")
        if not turn_id:
            return
        self._runtime_delta_generation += 1
        generation = self._runtime_delta_generation
        worker = RuntimeDeltaWorker(turn_id)

        def apply_delta(text):
            if self._runtime_delta_generation == generation:
                self._apply_runtime_delta(text)

        def apply_stage(text):
            if self._runtime_delta_generation == generation:
                self._apply_runtime_stage(text)

        def finish():
            self._runtime_delta_done(generation, worker)

        worker.delta.connect(apply_delta, Qt.ConnectionType.QueuedConnection)
        worker.stage.connect(apply_stage, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(finish, Qt.ConnectionType.QueuedConnection)
        thread = threading.Thread(
            target=worker.run,
            name=f"jarvis-runtime-delta-{turn_id[:8]}",
            daemon=True,
        )
        self._runtime_delta_worker = worker
        self._runtime_delta_thread = thread
        thread.start()

    def _stop_runtime_delta_worker(self):
        worker = getattr(self, "_runtime_delta_worker", None)
        if worker:
            worker.request_stop()

    @Slot(str)
    def _apply_runtime_delta(self, accumulated):
        if getattr(self, "_chat_request_cancelled", False):
            return
        if self.current_chat_id != getattr(self, "_chat_request_chat_id", "default"):
            return
        processing_id = getattr(self, "_chat_request_processing_id", None)
        if not processing_id or not accumulated:
            return
        self.chat_view.page().runJavaScript(
            "window.updateMessage && window.updateMessage(" + json.dumps({
                "id": processing_id,
                "role": "agent",
                "content": accumulated,
                "status": "processing",
                "attachments": [], "reactions": [], "pinned": False,
            }, ensure_ascii=False) + ");"
        )

    @Slot(str)
    def _apply_runtime_stage(self, text):
        if getattr(self, "_chat_request_cancelled", False):
            return
        if hasattr(self, "assistant_label") and text:
            self.assistant_label.setText(str(text))

    def _runtime_delta_done(self, generation, worker):
        worker.deleteLater()
        if generation != self._runtime_delta_generation:
            return
        if self._runtime_delta_worker is not worker:
            return
        self._runtime_delta_thread = None
        self._runtime_delta_worker = None

    @Slot()
    def cancel_chat_request(self):
        turn_id = getattr(self, "_chat_request_turn_id", "")
        if not turn_id or not getattr(self, "_chat_request_in_flight", False):
            return
        self._chat_request_cancelled = True
        self._stop_runtime_delta_worker()
        self.composer.set_sending(False, "Запрос отменён")
        processing_id = getattr(self, "_chat_request_processing_id", None)
        if processing_id:
            self.chat_view.page().runJavaScript(
                "window.removeMessage && window.removeMessage(" + json.dumps(processing_id) + ");"
            )
        self._run_network_operation(
            "chat-cancel",
            lambda _data: None,
            lambda _error: None,
            params={"turn_id": turn_id},
        )

    @Slot(object)
    def _chat_request_finished(self, data):
        self._stop_runtime_delta_worker()
        if getattr(self, "_chat_request_cancelled", False):
            self._chat_request_done()
            return
        metrics = data.get("last_turn_metrics") or data.get("metrics") or {}
        route = str(metrics.get("route") or data.get("route") or "").lower()
        if route in {"knowledge", "library", "local_response", "conversational", "instant"}:
            self._set_chat_status_override("#00aaff", "Модель готова · ответ из локальной библиотеки", 8.0)
        else:
            self._set_chat_status_override("#00aaff", "Jarvis отвечает", 8.0)
        response_chat_id = str(getattr(self, "_chat_request_chat_id", "default"))
        if str(self.current_chat_id) != response_chat_id:
            self._unread_chat_ids.add(response_chat_id)
        self._set_text_turn_overlay_state("speaking", duration_ms=3200)
        cached = data.get("attachments") or []
        if cached:
            self.chat_view.page().runJavaScript(
                "window.updateMessage && window.updateMessage(" + json.dumps({
                    "id": self._chat_request_local_id,
                    "role": "user",
                    "content": self._chat_request_display_text,
                    "attachments": cached,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "reactions": [], "pinned": False,
                }, ensure_ascii=False) + ");"
            )
        processing_id = getattr(self, "_chat_request_processing_id", None)
        if processing_id and self.current_chat_id == getattr(self, "_chat_request_chat_id", "default"):
            self.chat_view.page().runJavaScript(
                "window.updateMessage && window.updateMessage(" + json.dumps({
                    "id": processing_id,
                    "role": "agent",
                    "content": "[Typing...]",
                    "status": "processing",
                    "attachments": [], "reactions": [], "pinned": False,
                }, ensure_ascii=False) + ");"
            )
            QTimer.singleShot(140, lambda payload=data: self._complete_processing_message(payload))
        elif self.current_chat_id == getattr(self, "_chat_request_chat_id", "default"):
            self.add_message(data.get("response", "Нет ответа"), False)
        self.load_chat_sessions()
        self._chat_request_done()

    def _complete_processing_message(self, data):
        if self.current_chat_id != getattr(self, "_chat_request_chat_id", "default"):
            return
        processing_id = getattr(self, "_chat_request_processing_id", None)
        if processing_id:
            self.chat_view.page().runJavaScript(
                "window.completeProcessingMessage && window.completeProcessingMessage(" +
                json.dumps(processing_id) + "," + json.dumps({
                    "id": data.get("message_id") or f"local_{uuid.uuid4().hex}",
                    "role": "assistant",
                    "content": data.get("response", "Нет ответа"),
                    "status": "sent",
                    "attachments": [], "reactions": [], "pinned": False,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }, ensure_ascii=False) + ");"
            )
        else:
            self.add_message(data.get("response", "Нет ответа"), False)
        self._chat_request_processing_id = None

    @Slot(str)
    def _chat_request_failed(self, _error):
        self._stop_runtime_delta_worker()
        if getattr(self, "_chat_request_cancelled", False):
            self._chat_request_done()
            return
        if self.current_chat_id == getattr(self, "_chat_request_chat_id", "default"):
            processing_id = getattr(self, "_chat_request_processing_id", None)
            if processing_id:
                self.chat_view.page().runJavaScript(
                    "window.removeMessage && window.removeMessage(" + json.dumps(processing_id) + ");"
                )
            self.add_message("Ошибка соединения", False)
        self.composer.set_sending(False, "Не удалось отправить сообщение")
        self._set_chat_status_override("#ff3b4d", "Ошибка ответа Jarvis", 8.0)
        self._set_text_turn_overlay_state("waiting")
        self._chat_request_done()

    @Slot()
    def _chat_request_done(self):
        self.composer.set_sending(False)
        self._chat_request_in_flight = False
        self._chat_request_thread = None
        self._chat_request_worker = None

    def _set_chat_status_override(self, color: str, tooltip: str, seconds: float = 0.0) -> None:
        """Keep ordinary text turns visible in the same status indicator as voice turns."""
        self._chat_status_override = (str(color), str(tooltip), time.monotonic() + max(0.0, seconds))
        self._set_chat_status_dot(color, tooltip)

    def _set_text_turn_overlay_state(self, state: str, duration_ms: int = 0) -> None:
        """Reflect a normal chat request in an already-open Voice Mode surface."""
        overlay = getattr(self, "voice_mode_overlay", None)
        if overlay is None or not overlay.isVisible():
            return
        generation = getattr(self, "_chat_overlay_generation", 0)
        overlay.set_state(state)
        if state == "speaking":
            overlay.set_voice_activity(0.75, True)
        elif state == "processing":
            overlay.set_voice_activity(0.45, True)
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda: (
                overlay.set_state("waiting")
                if getattr(self, "_chat_overlay_generation", 0) == generation and overlay.isVisible()
                else None
            ))

    # ---------------- CHAT ----------------

    def _on_chat_frontend_loaded(self, ok):
        if not ok:
            return
        theme = {
            "accent": self.accent_hex,
            "accent_color": self.accent_hex,
            "user_avatar_path": self._profile_avatar_url(),
            "accent_hover": self.accent_color.lighter(120).name(),
            # Chat readability is intentionally independent of the app HUD
            # font. Use the neutral system stack used by Codex-like clients.
            "font_family": "Inter, Segoe UI, Arial, sans-serif",
            "font_size": 14,
            "show_avatars": self.ui_settings.value("chat_show_avatars", True, type=bool),
            "show_timestamps": self.ui_settings.value("chat_show_timestamps", True, type=bool),
            "media_autoplay": self.ui_settings.value("chat_media_autoplay", False, type=bool),
            "incoming_bubble_acrylic": self.ui_settings.value("chat_incoming_acrylic", True, type=bool),
            "outgoing_bubble_acrylic": self.ui_settings.value("chat_outgoing_acrylic", False, type=bool),
            "compact_mode": self.ui_settings.value("chat_compact_mode", False, type=bool),
            "chat_history_page_size": int(self.ui_settings.value("chat_history_page_size", 25)),
            "incoming_bubble_opacity": 0.72,
            "outgoing_bubble_opacity": 1.0,
        }
        self.chat_view.page().runJavaScript(
            "window.applyThemeSettings && window.applyThemeSettings(" +
            json.dumps(theme, ensure_ascii=False) + ");"
        )
        self.chat_view.page().runJavaScript(
            "window.applyChatPreferences && window.applyChatPreferences(" +
            json.dumps(theme, ensure_ascii=False) + ");"
        )
        # The page is populated from Jarvis' 8000 API by the native host.  Set
        # the same origin for media-cache URLs; leaving the HTML fallback
        # (8765, the old donor service) produces broken GIF/image elements in
        # message bubbles even when the attachment itself is cached correctly.
        self.chat_view.page().runJavaScript(
            "window.setBackendBaseUrl && window.setBackendBaseUrl(" +
            json.dumps(API_ROOT) + ");"
        )
        self.chat_view.page().runJavaScript(
            "window.setCurrentChatId && window.setCurrentChatId(" +
            json.dumps(getattr(self, "current_chat_id", "default")) + ");"
        )
        self.load_chat_history()

    def open_chat_emote_picker(self):
        """Open Crazy Tad's real HTML picker next to the native composer."""
        self.composer.capture_picker_cursor()
        self.chat_view.page().runJavaScript(
            "window.openEmojiPicker && window.openEmojiPicker();"
        )

    def open_chat_settings(self):
        dialog = JarvisChatSettingsDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet(self.dialog_stylesheet())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_chat_preferences(dialog.values())

    def show_chat_profile(self):
        dialog = JarvisChatProfileDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        dialog.setStyleSheet(self.dialog_stylesheet())
        dialog.show()
        self._chat_profile_dialog = dialog

    def apply_chat_preferences(self, values):
        keys = {
            "incoming_bubble_acrylic": "chat_incoming_acrylic",
            "outgoing_bubble_acrylic": "chat_outgoing_acrylic",
            "show_avatars": "chat_show_avatars",
            "show_timestamps": "chat_show_timestamps",
            "compact_mode": "chat_compact_mode",
            "media_autoplay": "chat_media_autoplay",
            "chat_history_page_size": "chat_history_page_size",
        }
        for key, setting_key in keys.items():
            if key in values:
                self.ui_settings.setValue(setting_key, values[key])
        payload = {
            "accent_color": self.accent_hex,
            "user_avatar_path": self._profile_avatar_url(),
            **values,
        }
        self.chat_view.page().runJavaScript(
            "window.applyThemeSettings && window.applyThemeSettings(" + json.dumps(payload, ensure_ascii=False) + ");"
        )
        self.chat_view.page().runJavaScript(
            "window.applyChatPreferences && window.applyChatPreferences(" + json.dumps(payload, ensure_ascii=False) + ");"
        )

    def load_chat_history(self):
        try:
            page_size = int(self.ui_settings.value("chat_history_page_size", 25))
        except (TypeError, ValueError):
            page_size = 25
        chat_id = str(getattr(self, "current_chat_id", "default"))
        self._chat_history_generation += 1
        generation = self._chat_history_generation
        if self._displayed_chat_id != chat_id:
            self._displayed_chat_id = chat_id
            self.chat_view.page().runJavaScript("window.loadMessages && window.loadMessages([]);")
        self._run_network_operation(
            "chat-history",
            lambda data: self._apply_chat_history(data, chat_id, generation),
            lambda error: self._chat_history_failed(error, chat_id, generation),
            params={"chat_id": chat_id, "limit": max(10, min(100, page_size)), "latest": "true"},
        )

    def _apply_chat_history(self, data, chat_id, generation):
        if generation != self._chat_history_generation or chat_id != str(self.current_chat_id):
            return
        messages = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(messages, list):
            self._chat_history_failed("invalid response", chat_id, generation)
            return
        self.chat_view.page().runJavaScript(
            "window.loadMessages && window.loadMessages(" +
            json.dumps(messages, ensure_ascii=False) + ");"
        )

    def _chat_history_failed(self, _error, chat_id, generation):
        if generation != self._chat_history_generation or chat_id != str(self.current_chat_id):
            return
        self._set_chat_status_override("#ff3b4d", "Не удалось загрузить историю чата", 8.0)
        self.chat_view.page().runJavaScript(
            "window.showNotification && window.showNotification(" +
            json.dumps("Не удалось загрузить историю чата. Повторите открытие чата.") +
            ", 'error');"
        )
        self.chat_view.page().runJavaScript(
            "window.startPolling && window.startPolling(" +
            json.dumps(getattr(self, "current_chat_id", "default")) + ");"
        )

    def add_message(self, text, user, attachments=None, status=""):
        message_id = f"local_{uuid.uuid4().hex}"
        message = {
            "id": message_id,
            "role": "user" if user else "assistant",
            "content": str(text),
            "status": status,
            "attachments": list(attachments or []),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "reactions": [],
            "pinned": False,
        }
        self.chat_view.page().runJavaScript(
            "window.appendMessage && window.appendMessage(" +
            json.dumps(message, ensure_ascii=False) + ");"
        )
        return message_id

    # ---------------- DRAG WINDOW ----------------

    def contextMenuEvent(self, event):
        """Quick actions for the transparent main HUD surface."""
        menu = QMenu(self)
        menu.setStyleSheet(self.dialog_stylesheet())
        new_chat = menu.addAction("Новый чат")
        agents = menu.addAction("Агенты")
        providers = menu.addAction("Провайдеры")
        menu.addSeparator()
        exit_action = menu.addAction("Выход")
        selected = menu.exec(event.globalPos())
        if selected is new_chat:
            self.ensure_full_ui()
            self.menu.setCurrentRow(1)
            self.pages.setCurrentIndex(1)
        elif selected is agents:
            self.show_panel_dialog("ДОСТУПНЫЕ АГЕНТЫ", [
                "Main Agent", "Planner", "Executor", "Critic", "File",
                "Network", "Web", "Vision", "Memory", "Performance",
            ])
        elif selected is providers:
            self.show_panel_dialog("ПРОВАЙДЕРЫ", [
                "Ollama", "Codex", "Claude", "FreeLLMAPI",
            ])
        elif selected is exit_action:
            self.close()
        event.accept()

    def resizeEvent(self, event):
        """Keep the TECH-A HUD at its canonical size when the window grows."""
        super().resizeEvent(event)
        _ui_trace(
            "window.resize",
            geometry=self.geometry().getRect(),
            widget_mode=getattr(self, "widget_mode", None),
            pinned_geometry=self.pinned_chats_list.geometry().getRect()
            if hasattr(self, "pinned_chats_list") else None,
            sidebar_min_height=self.sidebar_layout.minimumSize().height()
            if hasattr(self, "sidebar_layout") else None,
            root_min_height=self.layout().minimumSize().height()
            if self.layout() is not None else None,
        )
        container = getattr(self, "hud_container", None)
        if container is None:
            return
        size = JarvisHUD.HUD_SIZE
        if container.size() != QSize(size, size):
            container.setFixedSize(size, size)
        hud = getattr(self, "hud", None)
        if hud is not None and hud.size() != QSize(size, size):
            hud.setFixedSize(size, size)
        self.raise_hud_controls()

    def closeEvent(self, event):
        """Release the microphone when the Jarvis window is closed."""
        self.voice_status_timer.stop()
        self.voice_status_client.shutdown()
        self.weather_timer.stop()
        self._stop_runtime_delta_worker()
        if self._network_jobs:
            # Let bounded HTTP workers deliver their queued result while the
            # event loop is alive instead of destroying a live bridge.
            self._closing_after_jobs = True
            _ui_trace("window.close.deferred", active_jobs=len(self._network_jobs))
            event.ignore()
            self.hide()
            return
        _ui_trace("window.close.accepted")
        QApplication.instance().removeEventFilter(self)
        worker = getattr(self, "_dictation_worker", None)
        thread = getattr(self, "_dictation_thread", None)
        if worker and thread and thread.isRunning():
            worker.request_cancel()
            thread.quit()
            thread.wait(1500)
        if hasattr(self, "status_widget"):
            self.status_widget.close()
        try:
            requests.post(f"{API_ROOT}/voice/stop", timeout=2)
        except requests.RequestException:
            pass
        super().closeEvent(event)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        current_pos = event.globalPosition().toPoint()
        if self.oldPos is None:
            self.oldPos = current_pos
            return
        delta = QPoint(current_pos - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = current_pos

def main() -> int:
    app = QApplication(sys.argv)
    window = JarvisUI()
    window.show()
    QTimer.singleShot(0, window.capture_initial_window_geometry)
    if "--fullscreen" in sys.argv:
        # Keep this as a launch-time option so calibration can be repeated in
        # fullscreen without overwriting the accepted widget-mode profile.
        QTimer.singleShot(0, window.toggle_fullscreen_window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
