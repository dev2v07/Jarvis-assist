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

from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from toggle_switch import ToggleSwitch
from jarvis_hud import JarvisHUD
from chat_composer import ChatComposer
from profile_dialog import UserProfileDialog
from autostart import is_enabled as windows_autostart_enabled, set_enabled as set_windows_autostart

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

print(os.path.join(BASE_DIR, "assets", "jarvis_off.png"))

API_URL = "http://127.0.0.1:8000/chat"
STARTUP_DIAGNOSTIC_WAV = os.path.abspath(os.path.join(
    BASE_DIR, "..", "backend", "voice_engine", "sound",
    "Начинаю диагностику системы (второй).wav"
))

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


class ChatRequestWorker(QObject):
    """Run the backend chat request away from the Qt GUI thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    @Slot()
    def run(self):
        try:
            response = requests.post(API_URL, json=self.payload, timeout=60)
            response.raise_for_status()
            self.finished.emit(response.json())
        except Exception as error:
            self.failed.emit(str(error))


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
                        "http://127.0.0.1:8000/runtime/events",
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
                f"http://127.0.0.1:8000/chat/messages/{requests.utils.quote(message_id, safe='')}/reaction",
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
            requests.post(f"http://127.0.0.1:8000/chat/messages/{message_id}/pin", timeout=3)
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
            QDesktopServices.openUrl(QUrl(f"http://127.0.0.1:8000/api/media/{requests.utils.quote(value, safe='')}"))
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
                    f"http://127.0.0.1:8000/api/media/{requests.utils.quote(value, safe='')}",
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
            source = QUrl(f"http://127.0.0.1:8000/api/media/{requests.utils.quote(value, safe='')}")
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
        test = QPushButton("ПРОВЕРИТЬ API И СОХРАНИТЬ")
        test.clicked.connect(self.validate_and_save)
        root.addWidget(test)
        layout = QPushButton("ОТКРЫТЬ ВИЗУАЛЬНЫЙ РЕДАКТОР")
        layout.clicked.connect(owner.open_weather_layout_editor)
        root.addWidget(layout)

    def validate_and_save(self):
        city, key = self.city.text().strip(), self.key.text().strip()
        if not city or not key:
            self.status.setText("Укажи город и API key.")
            return
        try:
            response = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": key, "units": "metric", "lang": "ru"},
                timeout=8,
            )
            response.raise_for_status()
            self.owner.ui_settings.setValue("weather_city", city)
            self.owner.ui_settings.setValue("weather_api_key", key)
            self.owner.ui_settings.sync()
            self.owner.load_weather()
            self.status.setText("Подключение успешно. Погода обновлена.")
        except requests.RequestException:
            self.status.setText("Проверка не пройдена: город или ключ недоступны.")


class AIProviderDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
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
        self.provider.addItems(["ollama", "openai", "codex", "claude", "freellmapi"])
        self.provider.setCurrentText("ollama")
        self.base = QLineEdit("http://127.0.0.1:11434")
        self.model = QLineEdit("llama3.2")
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

    def load_current(self):
        try:
            data = requests.get("http://127.0.0.1:8000/settings/llm", timeout=4).json()
            self.provider.setCurrentText(data.get("provider", "ollama"))
            config = data.get("config", {})
            self.base.setText(config.get("HEL_OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
            self.model.setText(config.get("HEL_OLLAMA_MODEL", "llama3.2"))
            self.status.setText("Конфигурация загружена. Секреты скрыты.")
        except requests.RequestException:
            self.status.setText("Backend недоступен.")

    def update_defaults(self, provider):
        if provider == "ollama":
            self.base.setText("http://127.0.0.1:11434")
        elif provider == "claude":
            self.base.setText("https://api.anthropic.com/v1")

    def payload(self):
        key = self.key.text().strip()
        return {"provider": self.provider.currentText(), "ollama_base_url": self.base.text().strip(),
                "ollama_model": self.model.text().strip(), "openai_base_url": self.base.text().strip(),
                "openai_model": self.model.text().strip(), "codex_base_url": self.base.text().strip(),
                "codex_model": self.model.text().strip(), "claude_base_url": self.base.text().strip(),
                "claude_model": self.model.text().strip(), "freellmapi_base_url": self.base.text().strip(),
                "freellmapi_model": self.model.text().strip(), "openai_api_key": key or None,
                "codex_api_key": key or None, "claude_api_key": key or None, "freellmapi_api_key": key or None}

    def fetch_models(self):
        try:
            data = requests.get("http://127.0.0.1:8000/settings/llm/models", params={"provider": self.provider.currentText(), "base_url": self.base.text().strip(), "api_key": self.key.text().strip()}, timeout=10).json()
            models = data.get("models", [])
            if models:
                self.model.setText(models[0])
                self.status.setText("Модели получены: " + ", ".join(models[:5]))
            else:
                self.status.setText(data.get("message", "Модели не найдены."))
        except requests.RequestException:
            self.status.setText("Не удалось получить список моделей.")

    def test_provider(self):
        try:
            data = requests.post("http://127.0.0.1:8000/settings/llm/test", json=self.payload(), timeout=15).json()
            self.status.setText(data.get("message", "Проверка завершена."))
        except requests.RequestException:
            self.status.setText("Backend недоступен.")

    def save_provider(self):
        try:
            requests.post("http://127.0.0.1:8000/settings/llm", json=self.payload(), timeout=10).raise_for_status()
            self.status.setText("Провайдер сохранён. Новые запросы используют выбранную конфигурацию.")
        except requests.RequestException:
            self.status.setText("Не удалось сохранить конфигурацию.")


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

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.panel_angle = 0.0
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

    def wheelEvent(self, event):
        if self.property("calibrationEnabled"):
            step = 2 if event.angleDelta().y() > 0 else -2
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

class ChatItemWidget(QWidget):

    def __init__(self, text, pinned=False):
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
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(6)

        self.label = QLabel(text)
        self.label.setStyleSheet("color:white;font-size:14px;")
        self.label.setMinimumWidth(0)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.pin = QLabel()
        self.pin.setFixedSize(12,12)

        if pinned:
            pin_path = os.path.join(BASE_DIR,"assets","pin.svg")
            self.pin.setPixmap(QIcon(pin_path).pixmap(12,12))

        self.menu_btn = QPushButton("⋯")
        self.menu_btn.setFixedSize(26,26)
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
        layout.addStretch()
        layout.addWidget(self.pin)
        layout.addWidget(self.menu_btn)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 30 if self.underMouse() else 18))
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


class StartButton(QPushButton):
    """START button with a restrained readable shadow and accent contour."""

    def __init__(self, text, text_color, accent_color, parent=None):
        super().__init__(text, parent)
        self.start_text_color = QColor(text_color)
        self.start_accent_color = QColor(accent_color)
        self.start_hovered = False

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

class JarvisUI(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Jarvis Assist")
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, "assets", "jarvis.ico")))
        self.resize(1280, 850)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.ui_settings = QSettings("Jarvis", "Jarvis Assist")
        self.visual_settings = {
            "window_opacity": int(self.ui_settings.value("window_opacity", 96)),
            "transparent_background": self.ui_settings.value(
                "transparent_background", True, type=bool
            ),
            "glass_enabled": self.ui_settings.value("glass_enabled", True, type=bool),
        }
        self.hardware_settings = {
            "audio_input_device": int(self.ui_settings.value("audio_input_device", -1)),
            "video_input_device": int(self.ui_settings.value("video_input_device", 0)),
        }
        self.startup_widget_mode = self.ui_settings.value("startup_widget_mode", True, type=bool)
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

        self.build_ui()
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

        self.voice_status_timer = QTimer(self)
        self.voice_status_timer.timeout.connect(self.refresh_voice_status)
        self.voice_status_timer.start(1500)
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
        if row == 1 and hasattr(self, "create_new_chat"):
            self.create_new_chat()
            self.set_settings_header_visible(False)
            return
        if row == 2 and hasattr(self, "load_history_sessions"):
            self.load_history_sessions()
        self.pages.setCurrentIndex(row)
        self.set_settings_header_visible(row == 3)

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
        self.menu.setCurrentRow(3)
        if hasattr(self, "settings_nav"):
            self.settings_nav.setCurrentRow(index)

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
        dialog = AIProviderDialog(self)
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
            self.assistant_toggle.setChecked(True)
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

    def _assistant_toggle_stub(self, checked):
        """Assistant switch is intentionally a visual placeholder for now."""
        if hasattr(self, "assistant_toggle") and not checked:
            self.assistant_toggle.blockSignals(True)
            self.assistant_toggle.setChecked(True)
            self.assistant_toggle.blockSignals(False)
        self.assistant_label.setText("Переключатель ассистента пока не активен")

    def _toggle_microphone_from_sidebar(self, checked):
        """Mute/unmute audio capture without stopping Jarvis itself."""
        self._microphone_enabled = bool(checked)
        if not self.jarvis_state:
            return
        try:
            response = requests.post(
                "http://127.0.0.1:8000/voice/microphone",
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
            requests.post("http://127.0.0.1:8000/voice/stop", timeout=3)
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
                    "http://127.0.0.1:8000/voice/start",
                    json={
                        "microphone_index": self._voice_microphone_index(),
                        "microphone_enabled": self._microphone_enabled,
                    },
                    timeout=4,
                )
            else:
                response = requests.post("http://127.0.0.1:8000/voice/stop", timeout=4)
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

    def refresh_device_summary(self):
        """Show a compact real capability summary on the main assistant page."""

        if not hasattr(self, "device_summary_label"):
            return
        try:
            data = requests.get(
                "http://127.0.0.1:8000/devices/capabilities",
                timeout=0.8,
            ).json()
            available = [
                str(item.get("name"))
                for item in data.get("capabilities", [])
                if item.get("available")
            ]
            unavailable = [
                str(item.get("name"))
                for item in data.get("capabilities", [])
                if not item.get("available")
            ]
            shown = ", ".join(available[:3]) or "базовые адаптеры"
            suffix = f"; недоступно: {len(unavailable)}" if unavailable else ""
            self.device_summary_label.setText(f"Доступно: {shown}{suffix}")
        except (requests.RequestException, ValueError, TypeError):
            self.device_summary_label.setText("Возможности устройств: backend недоступен")

    def refresh_voice_status(self):
        try:
            response = requests.get("http://127.0.0.1:8000/voice/status", timeout=1)
            response.raise_for_status()
            data = response.json()
            self._update_voice_debug(data)
            if data.get("voice_model"):
                self._render_voice_model_status(data["voice_model"])
            if data.get("enabled") and data.get("conversation_worker") is False:
                # Recover a conversation worker that may have been interrupted
                # during backend/UI startup without toggling the microphone off.
                try:
                    requests.post(
                        "http://127.0.0.1:8000/voice/start",
                        json={
                            "microphone_index": self._voice_microphone_index(),
                            "microphone_enabled": self._microphone_enabled,
                        },
                        timeout=2,
                    )
                except requests.RequestException:
                    pass
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
                else:
                    self.assistant_label.setText("Голосовой runtime: ошибка")
        except requests.RequestException:
            return

    def _update_voice_debug(self, data):
        """Show the live voice handler state in the assistant page."""
        phase = data.get("phase") or ("слушаю" if data.get("listening") else "выключен")
        transcript = str(data.get("last_transcript") or "—")
        response = str(data.get("last_response") or "—")
        error = str(data.get("last_error") or "—")
        if len(response) > 420:
            response = response[:420] + "…"
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
        position_map = self.widget_settings.get("panel_positions", {})
        for name, (x, y) in HUD_TOP_PANEL_BUTTONS.items():
            saved_position = position_map.get(name, {"x": x, "y": y})
            x, y = saved_position.get("x", x), saved_position.get("y", y)
            button = RotatablePanelButton(name, parent)
            button.setObjectName("hudPanelTop")
            button.setProperty("actionKey", action_map.get(name, name))
            button.setProperty("panelName", name)
            button.setProperty("panelTextColor", self.text_color_hex)
            button.set_panel_angle(saved_position.get("angle", 0))
            visual_width = 72 if name != "FUNCTION" else 86
            hit_width, hit_height = visual_width + 18, 44
            button.setProperty("panelAnchorX", x)
            button.setProperty("panelAnchorY", y)
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
                button.setToolTip(f"{name}: перетащите мышью, колесо — наклон текста")
                button.installEventFilter(self)
                button.angleChanged.connect(lambda angle, item=button: self.save_panel_position(item))
            button.clicked.connect(lambda checked=False, item=button: self.handle_hud_panel_action(
                item.property("actionKey"), item.property("panelName")
            ))
            button.show()
            button.raise_()
            buttons.append(button)
            self.hud_panel_button_map[name] = button

        icons_dir = os.path.join(BASE_DIR, "assets", "TECH-A", "panel")
        for name, (x, y) in HUD_BOTTOM_PANEL_BUTTONS.items():
            saved_position = position_map.get(name, {"x": x, "y": y})
            x, y = saved_position.get("x", x), saved_position.get("y", y)
            button = AnimatedPanelIconButton(parent)
            button.setObjectName("hudPanelIcon")
            button.setProperty("actionKey", action_map.get(name, name))
            button.setProperty("panelName", name)
            hit_width, hit_height = 56, 48
            button.setProperty("panelAnchorX", x)
            button.setProperty("panelAnchorY", y)
            button.setGeometry(x - 8, y - 8, hit_width, hit_height)
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

    def ensure_full_ui(self):
        """Restore the normal Jarvis chrome before opening an application page."""
        # Settings and application pages live in the same main window as the
        # HUD.  Leaving widget_mode enabled only hides the chrome and leaves
        # the settings page looking like a transparent, non-navigable overlay.
        # Use the normal mode transition so opacity, styles and hitboxes are
        # restored together instead of duplicating only part of the change.
        if getattr(self, "widget_mode", False):
            self.toggle_widget_mode()
        else:
            self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
            self.apply_styles()

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
            self.menu.setCurrentRow(2)
            self.pages.setCurrentIndex(2)
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
        self.widget_mode = not getattr(self, "widget_mode", False)
        for widget in getattr(self, "widget_chrome_widgets", []):
            widget.setVisible(not self.widget_mode)
        if self.widget_mode:
            self.main_container.setStyleSheet(
                "QFrame#container { background: transparent; border: none; }"
            )
            self.setWindowOpacity(1.0)
            self.pages.setCurrentIndex(0)
        else:
            self.main_container.setStyleSheet("")
            self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
            self.apply_styles()
        self.apply_hud_hitbox_offset()
        self.raise_hud_controls()

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

    def container_visual_stylesheet(self):
        if self.visual_settings["glass_enabled"]:
            background = (
                "qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 rgba(20,20,25,220),stop:0.35 rgba(15,15,20,220),"
                "stop:0.65 rgba(10,10,15,230),stop:1 rgba(30,30,35,220))"
            )
        else:
            background = "rgba(15,15,20,220)"
        return (
            "QFrame#container { border-radius:30px; "
            f"background:{background}; border:1px solid rgba(255,255,255,40); }}"
        )

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
        for key, value in self.visual_settings.items():
            self.ui_settings.setValue(key, value)
        self.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        self.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
        if hasattr(self, "main_container") and not getattr(self, "widget_mode", False):
            self.main_container.setStyleSheet(self.container_visual_stylesheet())
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
    def enumerate_video_sources():
        sources = []
        try:
            import cv2
            for index in range(6):
                capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                opened = capture.isOpened()
                capture.release()
                if opened:
                    sources.append((f"Камера {index}", index))
        except Exception as error:
            print(f"Video device enumeration failed: {error}")
        return sources or [("Камера по умолчанию (0)", 0)]

    def apply_hardware_settings(self):
        self.hardware_settings = {
            "audio_input_device": self.audio_source_combo.currentData(),
            "video_input_device": self.video_source_combo.currentData(),
        }
        for key, value in self.hardware_settings.items():
            self.ui_settings.setValue(key, value)
        try:
            requests.post(
                "http://127.0.0.1:8000/hardware/settings",
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
        model_id = str(self.voice_model_combo.currentData() or "jarvis")
        self.ui_settings.setValue("voice_model_id", model_id)
        self.ui_settings.sync()
        try:
            response = requests.post(
                "http://127.0.0.1:8000/voice/model",
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
            self.ui_settings.value("voice_model_id", "jarvis") or "jarvis"
        ).strip().lower()
        index = self.voice_model_combo.findData(model_id)
        if index >= 0 and index != self.voice_model_combo.currentIndex():
            self.voice_model_combo.blockSignals(True)
            self.voice_model_combo.setCurrentIndex(index)
            self.voice_model_combo.blockSignals(False)
        try:
            response = requests.post(
                "http://127.0.0.1:8000/voice/model",
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
        dialog.setWindowTitle(title)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        dialog.setAttribute(Qt.WA_TranslucentBackground, self.visual_settings["transparent_background"])
        dialog.setWindowOpacity(self.visual_settings["window_opacity"] / 100.0)
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
        return dialog.currentColor() if dialog.exec() == QDialog.Accepted else QColor()

    def choose_accent_color(self):
        color = self.pick_color(self.accent_color, "Выберите акцентный цвет")
        if not color.isValid():
            return

        self.accent_color = color
        self.accent_hex = color.name()
        self.ui_settings.setValue("accent_color", self.accent_hex)
        self.hud.set_accent_color(color)
        self.jarvis_button.set_accent_color(color)
        for toggle in getattr(self, "sidebar_toggles", []):
            toggle.set_accent_color(color)
        self.accent_value_label.setText(
            f"{self.accent_hex.upper()}  RGB {color.red()}, {color.green()}, {color.blue()}"
        )
        self.apply_styles()
        self._refresh_chat_identity()

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
                dragged, _, _ = self._panel_drag
                self._panel_drag = None
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
                self.widget_settings.setdefault("panel_positions", {})[name] = {
                    "x": button.property("panelAnchorX") if button.property("panelAnchorX") is not None else button.x(),
                    "y": button.property("panelAnchorY") if button.property("panelAnchorY") is not None else button.y(),
                    "angle": round(getattr(button, "panel_angle", 0), 1),
                }
                self.ui_settings.setValue(
                    "widget_settings",
                    json.dumps(self.widget_settings, ensure_ascii=False),
                )
                print(f"Panel position saved: {name} -> ({button.x()}, {button.y()})")
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
        archive_action = menu.addAction("Архивировать")
        delete_action = menu.addAction(del_icon,"Удалить")

        action = menu.exec(list_widget.mapToGlobal(pos))

        if action == pin_action:
            self.pin_chat(item)

        elif action == rename_action:
            self.rename_chat(item)

        elif action == archive_action:
            self.archive_chat(item)

        elif action == delete_action:
            self.delete_chat(item)


    # ---------------- PIN CHAT ----------------

    def pin_chat(self, item):

        widget = self.chats_list.itemWidget(item)

        if not widget:
            return

        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        try:
            response = requests.post(f"http://127.0.0.1:8000/chat/sessions/{chat_id}/pin", timeout=4)
            response.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                QMessageBox.information(self, "Закрепленные чаты", "Можно закрепить не более 3 чатов.")
            return
        except requests.RequestException:
            return

        self.load_chat_sessions()


    # ---------------- RENAME CHAT ----------------

    def rename_chat(self, item):

        widget = self.chats_list.itemWidget(item)

        if not widget:
            return

        text, ok = QInputDialog.getText(
            self,
            "Переименовать чат",
            "Новое название:",
            text=widget.label.text()
        )

        if ok and text:
            widget.label.setText(text)
            chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
            try:
                requests.patch(
                    f"http://127.0.0.1:8000/chat/sessions/{chat_id}",
                    json={"title": text},
                    timeout=4,
                ).raise_for_status()
            except requests.RequestException:
                pass


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
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog.setStyleSheet(f"""
            QDialog#deleteChatDialog {{
                background: rgba(18, 21, 28, 245);
                color: {self.text_color_hex};
                border: 1px solid rgba(255,255,255,55);
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
            requests.delete(f"http://127.0.0.1:8000/chat/sessions/{chat_id}", timeout=4).raise_for_status()
        except requests.RequestException:
            return
        list_widget.takeItem(row)

    def archive_chat(self, item):
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        try:
            requests.post(
                f"http://127.0.0.1:8000/chat/sessions/{chat_id}/archive",
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

        widget = ChatItemWidget(text, pinned)

        item.setSizeHint(QSize(max(1, list_widget.viewport().width() - 8), 36))

        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)

        widget.menu_btn.clicked.connect(
            lambda: self.chat_menu(list_widget.visualItemRect(item).center(), list_widget)
        )

    def load_chat_sessions(self):
        try:
            response = requests.get("http://127.0.0.1:8000/chat/sessions", timeout=4)
            response.raise_for_status()
            sessions = response.json().get("sessions", [])
        except (requests.RequestException, ValueError, TypeError):
            sessions = [{"id": "default", "title": "JARVIS CHAT", "pinned": 0}]
        self.pinned_chats_list.clear()
        self.chats_list.clear()
        pinned_sessions = [session for session in sessions if bool(session.get("pinned"))][:3]
        recent_sessions = [session for session in sessions if not bool(session.get("pinned"))]

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
                    break

    def select_chat_item(self, item):
        chat_id = str(item.data(Qt.ItemDataRole.UserRole) or "default")
        self.current_chat_id = chat_id
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
        try:
            response = requests.get(
                "http://127.0.0.1:8000/chat/sessions",
                params={"include_archived": "true"},
                timeout=4,
            )
            response.raise_for_status()
            sessions = response.json().get("sessions", [])
        except (requests.RequestException, ValueError, TypeError):
            sessions = []
        self.history_list.clear()
        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(session.get("id") or "default"))
            item.setSizeHint(QSize(max(1, self.history_list.viewport().width()), 54))
            row = QWidget()
            row.setObjectName("historyRow")
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            row.setAutoFillBackground(False)
            row.setStyleSheet("""
                QWidget#historyRow {
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.16);
                    border-radius: 10px;
                }
                QWidget#historyRow:hover {
                    background: rgba(255,255,255,0.11);
                    border-color: rgba(0,235,245,0.75);
                }
            """)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 6, 12, 6)
            row_layout.setSpacing(1)
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
        self.current_chat_id = chat_id
        self.pages.setCurrentIndex(1)
        self.chat_view.page().runJavaScript(
            "window.setCurrentChatId && window.setCurrentChatId(" + json.dumps(chat_id) + ");"
        )
        self.load_chat_history()

    def create_new_chat(self):
        self.current_chat_id = "draft_" + uuid.uuid4().hex
        self.pages.setCurrentIndex(1)
        self.composer.message_input.clear()
        self.chat_view.page().runJavaScript(
            "window.setCurrentChatId && window.setCurrentChatId(" + json.dumps(self.current_chat_id) + ");"
        )
        self.chat_view.page().runJavaScript("window.loadMessages && window.loadMessages([]);")
        self.chat_view.page().runJavaScript(
            "window.startPolling && window.startPolling(" + json.dumps(self.current_chat_id) + ");"
        )

    def load_chat_model(self):
        """Load the active provider/model instead of showing a placeholder."""
        try:
            settings = requests.get("http://127.0.0.1:8000/settings/llm", timeout=4).json()
            provider = str(settings.get("provider") or "ollama").lower()
            connection = settings.get("llm_connection") or {}
            model = str(connection.get("model") or "phi3:latest")
            config = settings.get("config") or {}
            base_url = str(config.get("HEL_OLLAMA_BASE_URL") or "http://127.0.0.1:11434")
            models = []
            if provider == "ollama":
                catalog = requests.get(
                    "http://127.0.0.1:8000/settings/llm/models",
                    params={"provider": "ollama", "base_url": base_url},
                    timeout=6,
                ).json()
                models = [str(value) for value in catalog.get("models", []) if value]
        except (requests.RequestException, ValueError, TypeError):
            provider, model, base_url, models = "ollama", "phi3:latest", "http://127.0.0.1:11434", []

        if model not in models:
            models.insert(0, model)
        self._chat_provider = provider
        self._chat_ollama_base_url = base_url
        self.chat_model_combo.blockSignals(True)
        self.chat_model_combo.clear()
        self.chat_model_combo.addItems(models or [model])
        self.chat_model_combo.setCurrentText(model)
        self.chat_model_combo.blockSignals(False)
        self.chat_subtitle.setText(f"Провайдер: {provider.title()}  |  Модель: {model}")

    def on_chat_model_changed(self, model):
        model = str(model or "").strip()
        if not model or not hasattr(self, "_chat_provider"):
            return
        self.chat_subtitle.setText(f"Провайдер: {self._chat_provider.title()}  |  Модель: {model}")
        if self._chat_provider != "ollama":
            return
        try:
            requests.post(
                "http://127.0.0.1:8000/settings/llm",
                json={
                    "provider": "ollama",
                    "ollama_base_url": getattr(self, "_chat_ollama_base_url", "http://127.0.0.1:11434"),
                    "ollama_model": model,
                },
                timeout=6,
            ).raise_for_status()
        except requests.RequestException:
            self.chat_subtitle.setText(f"Провайдер: Ollama  |  Модель: {model}  |  не сохранено")

    # ---------------- UI ----------------

    def build_ui(self):

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("container")
        self.main_container = container
        self.widget_chrome_widgets = []

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 20, 30, 20)

        # ---------- HEADER ----------

        header = QHBoxLayout()

        title = QLabel("JARVIS ASSIST")
        title.setObjectName("title")
        self.widget_chrome_widgets.append(title)

        header.addWidget(title)
        header.addStretch()

        btn_min = QPushButton("–")
        btn_close = QPushButton("X")

        btn_min.setFixedSize(32, 32)
        btn_close.setFixedSize(32, 32)

        btn_close.setObjectName("closeBtn")
        self.widget_chrome_widgets.extend([btn_min, btn_close])

        btn_min.clicked.connect(self.showMinimized)
        btn_close.clicked.connect(self.close)

        header.addWidget(btn_min)
        header.addWidget(btn_close)

        container_layout.addLayout(header)

        # ---------- MAIN ----------

        main = QHBoxLayout()
        main.setSpacing(25)

        # ---------- LEFT PANEL ----------

        left = QVBoxLayout()
        left.setSpacing(15)

        self.menu = QListWidget()
        self.menu.setAttribute(Qt.WA_StyledBackground, True)
        self.menu.setObjectName("menu")

        self.menu.addItems([
            "АССИСТЕНТ",
            "НОВЫЙ ЧАТ",
            "ИСТОРИЯ ЧАТОВ",
            "НАСТРОЙКИ"
        ])

        self.menu.setFixedWidth(180)
        self.menu.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.setFixedHeight(200)
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
        self.pinned_chats_list.setFixedHeight(120)
        self.pinned_chats_list.setContentsMargins(0, 0, 0, 0)
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
        self.pinned_chats_list.setSpacing(4)
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
        self.chats_list.setFixedHeight(120)
        self.chats_list.setSpacing(4)
        self.widget_chrome_widgets.append(self.chats_list)
        self.chats_list.viewport().installEventFilter(self)

        self.chats_list.itemClicked.connect(self.select_chat_item)
        QTimer.singleShot(0, self.load_chat_sessions)
        QTimer.singleShot(0, self.load_chat_model)

        left.addWidget(self.chats_list)

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
        profile_button.clicked.connect(self.show_user_profile)
        self.profile_button = profile_button
        self.widget_chrome_widgets.append(profile_button)
        self._refresh_user_profile_card()

        tandem_footer = QLabel(
            '<a href="https://tandemarketing.ru">© Разработано Tandem Marketing 2026</a>'
        )
        tandem_footer.setObjectName("tandemFooter")
        tandem_footer.setOpenExternalLinks(True)
        tandem_footer.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        tandem_footer.setCursor(Qt.CursorShape.PointingHandCursor)
        tandem_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tandem_footer.setFixedWidth(240)
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
        toggle1.toggled.connect(self._assistant_toggle_stub)
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
        chat_frame.setObjectName("chatFrame")

        chat_layout = QVBoxLayout(chat_frame)
        chat_layout.setContentsMargins(20, 20, 20, 20)
        chat_layout.setSpacing(20)

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
        chat_info = QVBoxLayout()
        chat_info.setSpacing(0)
        self.chat_title = QLabel("JARVIS CHAT")
        self.chat_title.setObjectName("chatTitle")
        self.chat_subtitle = QLabel("Провайдер: Ollama  |  Модель: по умолчанию")
        self.chat_subtitle.setObjectName("chatSubtitle")
        for profile_widget in (self.chat_header, self.chat_avatar, self.chat_title, self.chat_subtitle):
            profile_widget.installEventFilter(self)
        chat_info.addWidget(self.chat_title)
        chat_info.addWidget(self.chat_subtitle)
        header_layout.addLayout(chat_info)
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

        # IMPORTED CRAZY TAD CHAT FRONTEND

        self.chat_view = QWebEngineView()
        self.chat_view.setObjectName("jarvisChatWebView")
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
        chat_layout.addWidget(self.chat_view, 1)

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
        chat_layout.addWidget(self.composer)

        # ---------- PAGES ----------

        self.pages = QStackedWidget()

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
        hud_container.setFixedSize(JarvisHUD.HUD_SIZE, JarvisHUD.HUD_SIZE)

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
        QTimer.singleShot(0, self.raise_hud_controls)

        assistant_layout.addWidget(hud_container, alignment=Qt.AlignCenter)

        assistant_layout.addSpacing(20)

        assistant_layout.addWidget(
        self.assistant_label,
        alignment=Qt.AlignHCenter
        )
        self.device_summary_label = QLabel("Возможности устройств: проверка…")
        self.device_summary_label.setObjectName("settingsHint")
        self.device_summary_label.setAlignment(Qt.AlignCenter)
        self.device_summary_label.setFixedWidth(JarvisHUD.HUD_SIZE)
        assistant_layout.addWidget(self.device_summary_label, alignment=Qt.AlignHCenter)
        devices_button = QPushButton("УСТРОЙСТВА И ВОЗМОЖНОСТИ")
        devices_button.setObjectName("settingsTileButton")
        devices_button.setFixedWidth(260)
        devices_button.clicked.connect(lambda: self.open_settings_section(12))
        assistant_layout.addWidget(devices_button, alignment=Qt.AlignHCenter)
        assistant_layout.addStretch()

        QTimer.singleShot(900, self.refresh_device_summary)

        self.jarvis_button.clicked.connect(self._toggle_voice_runtime)

        self.pages.addWidget(assistant_page)
        
        # страница чата
        chat_page = QWidget()
        chat_page_layout = QVBoxLayout(chat_page)
        chat_page_layout.setContentsMargins(0,0,0,0)
        chat_page_layout.addWidget(chat_frame)

        self.pages.addWidget(chat_page)

        # Keep the left navigation indices aligned with the stacked pages.
        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        history_title = QLabel("ИСТОРИЯ ЧАТОВ")
        history_title.setObjectName("settingsTitle")
        history_layout.addWidget(history_title)
        history_toolbar = QHBoxLayout()
        history_hint = QLabel("Выберите чат, чтобы открыть его историю")
        history_hint.setObjectName("settingsHint")
        history_toolbar.addWidget(history_hint)
        history_toolbar.addStretch()
        refresh_history = QPushButton("ОБНОВИТЬ")
        refresh_history.setObjectName("historyRefresh")
        refresh_history.setFixedSize(92, 32)
        refresh_history.clicked.connect(self.load_history_sessions)
        history_toolbar.addWidget(refresh_history)
        history_layout.addLayout(history_toolbar)
        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setFrameShape(QFrame.Shape.NoFrame)
        self.history_list.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.history_list.setAutoFillBackground(False)
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_list.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.history_list.viewport().setAutoFillBackground(False)
        self.history_list.viewport().setStyleSheet("background: transparent; border: none;")
        self.history_list.itemClicked.connect(self.open_history_chat)
        history_layout.addWidget(self.history_list, 1)
        self.pages.addWidget(history_page)

        # страница настроек
        settings_page = QWidget()
        settings_page.setObjectName("settingsPage")
        self.settings_page_widget = settings_page
        settings_layout = QVBoxLayout(settings_page)
        # The three absolute-positioned header labels finish at roughly y=109
        # in the container.  Keep a deliberate 20 px breathing room before
        # the actual settings body instead of letting the first card overlap
        # the explanatory line.
        settings_layout.setContentsMargins(4, 92, 24, 0)
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
            ("УСТРОЙСТВА", "Камера, vision, жесты, CUDA и внешние адаптеры"),
        )
        for label, _hint in settings_sections:
            settings_nav.addItem(label)
        settings_stack = QStackedWidget()
        settings_stack.setObjectName("settingsContent")
        settings_nav.currentRowChanged.connect(settings_stack.setCurrentIndex)
        settings_nav.setCurrentRow(0)
        self.settings_nav = settings_nav
        settings_body.addWidget(settings_nav)
        settings_body.addWidget(settings_stack, 1)
        settings_layout.addLayout(settings_body, 1)

        def section_page(title, hint, callback=None, button_text="ОТКРЫТЬ НАСТРОЙКИ", fields=(), checks=(), extra_builder=None, max_width=620, min_width=0):
            page = QFrame()
            page.setObjectName("settingsCard")
            page.setMaximumWidth(max_width)
            if min_width:
                page.setMinimumWidth(min_width)
            page_layout = QVBoxLayout(page)
            heading = QLabel(title)
            heading.setObjectName("settingsCardTitle")
            page_layout.addWidget(heading)
            description = QLabel(hint)
            description.setObjectName("settingsHint")
            description.setWordWrap(True)
            page_layout.addWidget(description)
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
                page_layout.addWidget(QLabel(label))
                page_layout.addWidget(edit)
            checkboxes = {}
            for key, label, default in checks:
                check = QCheckBox(label)
                check.setChecked(self.ui_settings.value(key, default, type=bool))
                checkboxes[key] = check
                page_layout.addWidget(check)
            if extra_builder:
                extra_builder(page_layout, edits)
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
                page_layout.addWidget(action)
                if callback and not extra_builder:
                    quick = QPushButton(button_text)
                    quick.setObjectName("settingsTileButton")
                    quick.clicked.connect(callback)
                    page_layout.addWidget(quick)
            elif callback and not extra_builder:
                action = QPushButton(button_text)
                action.setObjectName("settingsTileButton")
                action.clicked.connect(callback)
                page_layout.addWidget(action)
            page_layout.addStretch()
            settings_stack.addWidget(page)
            settings_stack.layout().setAlignment(page, Qt.AlignLeft | Qt.AlignTop)
            return page

        general_page = QFrame()
        general_page.setObjectName("settingsCard")
        general_page.setMaximumWidth(780)
        general_layout = QGridLayout(general_page)
        general_layout.setContentsMargins(12, 10, 12, 12)
        general_layout.setHorizontalSpacing(12)
        general_layout.setVerticalSpacing(8)
        general_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        general_heading = QLabel("ОБЩИЕ")
        general_heading.setObjectName("settingsCardTitle")
        general_layout.addWidget(general_heading, 0, 0, 1, 2)
        general_hint = QLabel("Типографика, цвета и визуальные параметры приложения.")
        general_hint.setObjectName("settingsHint")
        general_hint.setContentsMargins(0, 0, 0, 2)
        general_layout.addWidget(general_hint, 1, 0, 1, 2)

        typography_card = QFrame()
        typography_card.setObjectName("settingsCard")
        typography_card.setFixedWidth(350)
        typography_layout = QVBoxLayout(typography_card)
        typography_title = QLabel("ТИПОГРАФИКА")
        typography_title.setObjectName("settingsCardTitle")
        typography_layout.addWidget(typography_title)
        typography_layout.addWidget(QLabel("Шрифт интерфейса IRON"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(list(self.tech_font_families.keys()))
        for index, family in enumerate(self.font_combo.itemText(i) for i in range(self.font_combo.count())):
            if self.tech_font_families.get(family) == self.active_font_family:
                self.font_combo.setCurrentIndex(index)
                break
        self.font_combo.currentTextChanged.connect(self.apply_font_family)
        typography_layout.addWidget(self.font_combo)
        font_hint = QLabel("Шрифт применяется к вкладкам и живому тексту HUD.")
        font_hint.setObjectName("settingsHint")
        typography_layout.addWidget(font_hint)
        general_layout.addWidget(typography_card, 2, 0)

        colors_card = QFrame()
        colors_card.setObjectName("settingsCard")
        colors_card.setFixedWidth(350)
        colors_layout = QVBoxLayout(colors_card)
        colors_title = QLabel("ЦВЕТА")
        colors_title.setObjectName("settingsCardTitle")
        colors_layout.addWidget(colors_title)
        colors_layout.addWidget(QLabel("Акцентный цвет интерфейса и индикаторов"))
        self.accent_value_label = QLabel()
        self.accent_value_label.setText(
            f"{self.accent_hex.upper()}  RGB {self.accent_color.red()}, "
            f"{self.accent_color.green()}, {self.accent_color.blue()}"
        )
        self.accent_button = QPushButton("Изменить акцентный цвет")
        self.accent_button.clicked.connect(self.choose_accent_color)
        colors_layout.addWidget(self.accent_value_label)
        colors_layout.addWidget(self.accent_button)
        colors_layout.addWidget(QLabel("Цвет текста интерфейса и показателей HUD"))
        self.font_color_value_label = QLabel()
        self.font_color_value_label.setText(
            f"{self.text_color_hex.upper()}  RGB {self.text_color.red()}, "
            f"{self.text_color.green()}, {self.text_color.blue()}"
        )
        self.font_color_button = QPushButton("Изменить цвет текста")
        self.font_color_button.clicked.connect(self.choose_text_color)
        colors_layout.addWidget(self.font_color_value_label)
        colors_layout.addWidget(self.font_color_button)
        general_layout.addWidget(colors_card, 2, 1)

        runtime_card = QFrame()
        runtime_card.setObjectName("settingsCard")
        runtime_card.setFixedWidth(712)
        runtime_layout = QFormLayout(runtime_card)
        runtime_title = QLabel("ВИЗУАЛ И ОКНО")
        runtime_title.setObjectName("settingsCardTitle")
        runtime_layout.addRow(runtime_title)

        self.startup_widget_check = QCheckBox("Запускать сразу в прозрачном VID-режиме")
        self.startup_widget_check.setChecked(self.startup_widget_mode)
        self.startup_widget_check.toggled.connect(self.set_startup_widget_mode)
        runtime_layout.addRow(self.startup_widget_check)

        self.windows_autostart_check = QCheckBox("Запускать Jarvis вместе с Windows")
        self.windows_autostart_check.setChecked(windows_autostart_enabled())
        self.windows_autostart_check.toggled.connect(self.set_windows_autostart)
        runtime_layout.addRow(self.windows_autostart_check)

        self.video_source_combo = QComboBox()
        for label, device_id in self.enumerate_video_sources():
            self.video_source_combo.addItem(label, device_id)
        video_index = self.video_source_combo.findData(self.hardware_settings["video_input_device"])
        self.video_source_combo.setCurrentIndex(max(0, video_index))
        self.video_source_combo.currentIndexChanged.connect(self.apply_hardware_settings)
        runtime_layout.addRow(QLabel("Камера / видео"), self.video_source_combo)
        self.transparent_background_check = QCheckBox("Прозрачный фон окна")
        self.transparent_background_check.setChecked(self.visual_settings["transparent_background"])
        self.transparent_background_check.toggled.connect(self.apply_visual_settings)
        runtime_layout.addRow(self.transparent_background_check)

        self.glass_enabled_check = QCheckBox("Glass-градиент интерфейса")
        self.glass_enabled_check.setChecked(self.visual_settings["glass_enabled"])
        self.glass_enabled_check.toggled.connect(self.apply_visual_settings)
        runtime_layout.addRow(self.glass_enabled_check)

        self.acrylic_status = QLabel("Acrylic Windows: не подключён")
        self.acrylic_status.setObjectName("settingsHint")
        runtime_layout.addRow(self.acrylic_status)

        self.window_opacity_spin = QSpinBox()
        self.window_opacity_spin.setRange(20, 100)
        self.window_opacity_spin.setSuffix(" %")
        self.window_opacity_spin.setValue(self.visual_settings["window_opacity"])
        self.window_opacity_spin.valueChanged.connect(self.apply_visual_settings)
        runtime_layout.addRow(QLabel("Прозрачность окна и popup"), self.window_opacity_spin)
        general_layout.addWidget(runtime_card, 3, 0, 1, 2)
        settings_stack.addWidget(general_page)
        settings_stack.layout().setAlignment(general_page, Qt.AlignLeft | Qt.AlignTop)
        section_page("УЧЁТНАЯ ЗАПИСЬ", "Аватар, имя, username, email, возраст и обращение.", self.show_user_profile, "ОТКРЫТЬ ПРОФИЛЬ", fields=(("profile_display_name", "Имя", "Данил"), ("profile_username", "Username", "sheff"), ("profile_email", "Электронная почта", ""), ("profile_age", "Возраст", ""), ("profile_address", "Как обращаться", "Данил")))
        section_page("УВЕДОМЛЕНИЯ", "Поведение стартовой диагностики и уведомлений ответов.", fields=(), checks=(("notify_startup", "Показывать уведомления запуска", True), ("notify_chat", "Уведомления новых ответов", True)))
        def iron_inline(layout, edits):
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
            layout.addWidget(save)
            quick = QPushButton("ОТКРЫТЬ РАСШИРЕННЫЙ РЕДАКТОР IRON")
            quick.clicked.connect(self.open_widget_settings)
            layout.addWidget(quick)
        section_page("IRON", "Слои, метрики, панели, размеры и скорость анимаций.", extra_builder=iron_inline)
        def weather_inline(layout, edits):
            status = QLabel("Ключ проверяется запросом к OpenWeather и не выводится в журнал.")
            status.setObjectName("settingsHint")
            button = QPushButton("ПРОВЕРИТЬ API И СОХРАНИТЬ")
            def save_weather():
                city = edits["weather_city"].text().strip()
                key = edits["weather_api_key"].text().strip()
                try:
                    response = requests.get("https://api.openweathermap.org/data/2.5/weather", params={"q": city, "appid": key, "units": "metric", "lang": "ru"}, timeout=8)
                    response.raise_for_status()
                    self.ui_settings.setValue("weather_city", city)
                    self.ui_settings.setValue("weather_api_key", key)
                    self.ui_settings.sync()
                    self.load_weather()
                    status.setText("Проверка успешна. Погода обновлена.")
                except requests.RequestException:
                    status.setText("Проверка не пройдена: проверь город или API key.")
            button.clicked.connect(save_weather)
            layout.addWidget(button)
            layout.addWidget(status)
        section_page("ПОГОДА", "OpenWeather API, город и визуальная настройка карточки.", self.open_weather_settings, fields=(("weather_city", "Город", "Мурино"), ("weather_api_key", "OpenWeather API key", "")), extra_builder=weather_inline)
        def ai_inline(layout, _edits):
            """Render all provider profiles instead of one overwritten Ollama form."""
            status = QLabel("Профили сохраняются в backend; API keys отображаются только маской.")
            status.setObjectName("settingsHint")
            layout.addWidget(status)

            profiles_list = QListWidget()
            profiles_list.setObjectName("providerProfilesList")
            profiles_list.setFixedHeight(150)
            layout.addWidget(QLabel("Подключённые провайдеры"))
            layout.addWidget(profiles_list)

            provider_labels = {
                "ollama": "Ollama",
                "openai": "OpenAI",
                "openai_compatible": "OpenAI-compatible",
                "codex": "Codex",
                "claude": "Claude",
                "freellmapi": "FreeLLMAPI",
            }
            profiles = {}
            active_provider = "ollama"
            current_id = {"value": "ollama"}
            base_edit = QLineEdit()
            model_edit = QLineEdit()
            key_edit = QLineEdit()
            key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            key_edit.setPlaceholderText("Оставьте пустым, чтобы сохранить текущий ключ")
            form = QFormLayout()
            form.addRow("Провайдер", QLabel("—"))
            provider_value = form.itemAt(form.rowCount() - 1, QFormLayout.ItemRole.FieldRole).widget()
            form.addRow("Base URL", base_edit)
            form.addRow("Модель", model_edit)
            form.addRow("API key", key_edit)
            layout.addLayout(form)

            def profile_value(provider_id):
                return profiles.setdefault(provider_id, {"base_url": "", "model": "", "api_key_masked": "", "active": False})

            def sync_editor_from_current():
                provider_id = current_id["value"]
                value = profile_value(provider_id)
                provider_value.setText(provider_labels.get(provider_id, provider_id))
                base_edit.setText(str(value.get("base_url") or ""))
                model_edit.setText(str(value.get("model") or ""))
                key_edit.clear()
                masked = str(value.get("api_key_masked") or "")
                key_edit.setPlaceholderText(
                    f"Сохранённый ключ: {masked}" if masked else "Ключ не сохранён"
                )

            def store_editor():
                value = profile_value(current_id["value"])
                value["base_url"] = base_edit.text().strip()
                value["model"] = model_edit.text().strip()

            def select_profile(item):
                if item is None:
                    return
                store_editor()
                current_id["value"] = str(item.data(Qt.ItemDataRole.UserRole) or "ollama")
                sync_editor_from_current()

            profiles_list.currentItemChanged.connect(lambda current, _previous: select_profile(current))

            def render_profiles():
                profiles_list.blockSignals(True)
                profiles_list.clear()
                preferred_row = 0
                for row, provider_id in enumerate(profiles):
                    value = profile_value(provider_id)
                    marker = "● " if value.get("active") else "○ "
                    item = QListWidgetItem(marker + provider_labels.get(provider_id, provider_id))
                    item.setData(Qt.ItemDataRole.UserRole, provider_id)
                    profiles_list.addItem(item)
                    if provider_id == current_id["value"]:
                        preferred_row = row
                profiles_list.blockSignals(False)
                if profiles_list.count():
                    profiles_list.setCurrentRow(preferred_row)
                    sync_editor_from_current()

            def load_profiles():
                nonlocal active_provider
                try:
                    data = requests.get("http://127.0.0.1:8000/settings/llm", timeout=5).json()
                    active_provider = str(data.get("provider") or "ollama")
                    current_id["value"] = active_provider
                    profiles.clear()
                    for item in data.get("profiles", []):
                        provider_id = str(item.get("id") or "").strip()
                        if provider_id and provider_id != "stub":
                            profiles[provider_id] = dict(item)
                    if not profiles:
                        profiles["ollama"] = {"base_url": "http://127.0.0.1:11434", "model": "phi3:latest", "active": True}
                    render_profiles()
                    status.setText("Профили загружены. Выберите провайдера слева и настройте его отдельно.")
                except (requests.RequestException, ValueError, TypeError):
                    profiles.clear()
                    profiles["ollama"] = {"base_url": "http://127.0.0.1:11434", "model": "phi3:latest", "active": True}
                    render_profiles()
                    status.setText("Backend недоступен: показан локальный профиль Ollama.")

            def payload_for_current():
                store_editor()
                payload = {"provider": current_id["value"]}
                for provider_id, value in profiles.items():
                    prefix = {
                        "ollama": "ollama", "openai": "openai", "openai_compatible": "openai",
                        "codex": "codex", "claude": "claude", "freellmapi": "freellmapi",
                    }.get(provider_id)
                    if not prefix:
                        continue
                    payload[f"{prefix}_base_url"] = str(value.get("base_url") or "").strip()
                    payload[f"{prefix}_model"] = str(value.get("model") or "").strip()
                secret = key_edit.text().strip()
                if secret and current_id["value"] in {"openai", "openai_compatible", "codex", "claude", "freellmapi"}:
                    payload_key = "openai_api_key" if current_id["value"] in {"openai", "openai_compatible"} else f"{current_id['value']}_api_key"
                    payload[payload_key] = secret
                return payload

            def save_ai():
                try:
                    response = requests.post("http://127.0.0.1:8000/settings/llm", json=payload_for_current(), timeout=10)
                    response.raise_for_status()
                    status.setText(f"Профиль {provider_labels.get(current_id['value'], current_id['value'])} сохранён и выбран активным.")
                    load_profiles()
                except (requests.RequestException, ValueError):
                    status.setText("Не удалось сохранить профиль провайдера.")

            def test_ai():
                try:
                    data = requests.post("http://127.0.0.1:8000/settings/llm/test", json=payload_for_current(), timeout=15).json()
                    status.setText(str(data.get("message") or "Проверка завершена."))
                except (requests.RequestException, ValueError):
                    status.setText("Проверка провайдера не выполнена.")

            def fetch_models():
                try:
                    data = requests.get(
                        "http://127.0.0.1:8000/settings/llm/models",
                        params={"provider": current_id["value"], "base_url": base_edit.text().strip(), "api_key": key_edit.text().strip()},
                        timeout=10,
                    ).json()
                    models = [str(value) for value in data.get("models", []) if value]
                    if models:
                        model_edit.setText(models[0])
                        profile_value(current_id["value"])["model"] = models[0]
                        status.setText("Модели получены: " + ", ".join(models[:5]))
                    else:
                        status.setText(str(data.get("message") or "Каталог моделей не найден."))
                except (requests.RequestException, ValueError):
                    status.setText("Не удалось получить каталог моделей.")

            actions = QHBoxLayout()
            test_button = QPushButton("ПРОВЕРИТЬ")
            models_button = QPushButton("ПОЛУЧИТЬ МОДЕЛИ")
            save_button = QPushButton("СОХРАНИТЬ ПРОФИЛЬ")
            test_button.clicked.connect(test_ai)
            models_button.clicked.connect(fetch_models)
            save_button.clicked.connect(save_ai)
            actions.addWidget(test_button)
            actions.addWidget(models_button)
            actions.addWidget(save_button)
            layout.addLayout(actions)
            QTimer.singleShot(0, load_profiles)

        section_page("AI", "Настройте несколько провайдеров и моделей. Активным становится сохранённый профиль; ключи не показываются.", extra_builder=ai_inline)

        voice_page = QFrame()
        voice_page.setObjectName("settingsCard")
        voice_page.setMaximumWidth(780)
        voice_layout = QFormLayout(voice_page)
        voice_layout.setContentsMargins(14, 12, 14, 14)
        voice_title = QLabel("ГОЛОС AI")
        voice_title.setObjectName("settingsCardTitle")
        voice_layout.addRow(voice_title)
        voice_hint = QLabel(
            "Микрофон, голосовая модель и фраза диагностики. Состояние модели "
            "проверяется фактическим backend-инференсом."
        )
        voice_hint.setObjectName("settingsHint")
        voice_hint.setWordWrap(True)
        voice_layout.addRow(voice_hint)

        self.startup_diagnostic_check = QCheckBox("Говорить диагностику при запуске")
        self.startup_diagnostic_check.setChecked(
            self.ui_settings.value("startup_diagnostic_enabled", True, type=bool)
        )
        self.startup_diagnostic_check.toggled.connect(self.set_startup_diagnostic_enabled)
        voice_layout.addRow(self.startup_diagnostic_check)

        self.audio_source_combo = QComboBox()
        for label, device_id in self.enumerate_audio_sources():
            self.audio_source_combo.addItem(label, device_id)
        audio_index = self.audio_source_combo.findData(self.hardware_settings["audio_input_device"])
        self.audio_source_combo.setCurrentIndex(max(0, audio_index))
        self.audio_source_combo.currentIndexChanged.connect(self.apply_hardware_settings)
        voice_layout.addRow(QLabel("Микрофон"), self.audio_source_combo)

        self.voice_model_combo = QComboBox()
        self.voice_model_combo.addItem(
            "Jarvis — основная модель (в разработке)", "jarvis"
        )
        self.voice_model_combo.addItem(
            "Kesha — Silero ru_v3 / aidar (временный профиль)", "kesha"
        )
        self.voice_model_combo.addItem(
            "Fish Audio — Джарвис (облачный профиль)", "fish_jarvis"
        )
        stored_voice_model = str(
            self.ui_settings.value("voice_model_id", "jarvis") or "jarvis"
        ).strip().lower()
        voice_model_index = self.voice_model_combo.findData(stored_voice_model)
        self.voice_model_combo.setCurrentIndex(max(0, voice_model_index))
        self.voice_model_combo.currentIndexChanged.connect(self.apply_voice_model_setting)
        voice_layout.addRow(QLabel("Голосовая модель"), self.voice_model_combo)
        self.voice_model_status_label = QLabel("Проверка доступности…")
        self.voice_model_status_label.setObjectName("settingsHint")
        self.voice_model_status_label.setWordWrap(True)
        voice_layout.addRow(QLabel("Статус голоса"), self.voice_model_status_label)
        voice_layout.addRow(QLabel("Фактический движок"), QLabel(
            "Jarvis: XTTS v2 fallback; Kesha: Silero ru_v3 / aidar; Fish Audio: S2.1 Pro Free"
        ))
        settings_stack.addWidget(voice_page)
        settings_stack.layout().setAlignment(voice_page, Qt.AlignLeft | Qt.AlignTop)
        QTimer.singleShot(0, self.apply_hardware_settings)

        def commands_inline(layout, edits):
            command_view = QPlainTextEdit()
            command_view.setObjectName("commandsPreview")
            command_view.setReadOnly(True)
            command_view.setFixedSize(560, 300)
            command_path = Path(BASE_DIR).parent / "backend" / "voice_engine" / "commands.yaml"
            try:
                import yaml
                command_data = yaml.safe_load(command_path.read_text(encoding="utf-8")) or {}
                lines = []
                for intent, phrases in command_data.items():
                    lines.append(str(intent).upper())
                    lines.extend(f"  • {phrase}" for phrase in (phrases or []))
                    lines.append("")
                command_view.setPlainText("\n".join(lines).strip())
            except Exception as error:
                command_view.setPlainText(f"Не удалось прочитать commands.yaml: {error}")
            layout.addWidget(command_view)
            edit_button = QPushButton("ОТКРЫТЬ ФАЙЛ КОМАНД")
            edit_button.clicked.connect(lambda: os.startfile(str(command_path)))
            layout.addWidget(edit_button)
            add_button = QPushButton("ДОБАВИТЬ СВОЮ КОМАНДУ")
            add_button.clicked.connect(lambda: self.open_preference_dialog("КОМАНДЫ JARVIS", fields=(("custom_commands", "Дополнительные команды", ""),)))
            layout.addWidget(add_button)
        section_page("КОМАНДЫ JARVIS", "Системные команды загружаются из backend/voice_engine/commands.yaml.", extra_builder=commands_inline)
        section_page("ПЕРСОНАЛИЗАЦИЯ", "Инструкции, предпочтительное обращение и локальная память.", fields=(("custom_instructions", "Ваши инструкции Jarvis", ""), ("preferred_address", "Как обращаться", "Данил")), checks=(("memory_enabled", "Использовать память", True),), max_width=900, min_width=720)
        section_page("КОНФИДЕНЦИАЛЬНОСТЬ", "История чатов и локальная диагностика.", fields=(), checks=(("history_enabled", "Сохранять историю", True), ("analytics_enabled", "Локальная диагностика", True),))
        def data_inline(layout, edits):
            layout.addWidget(QLabel("Папка локальных данных"))
            data_path_edit = QLineEdit(str(self.ui_settings.value("data_path", str(Path(BASE_DIR).parent / "data"))))
            layout.addWidget(data_path_edit)
            backup_status = QLabel("Проверка фоновых резервных копий…")
            backup_status.setObjectName("settingsHint")
            backup_status.setWordWrap(True)
            layout.addWidget(backup_status)

            def refresh_backup_status():
                try:
                    data = requests.get("http://127.0.0.1:8000/backups/status", timeout=3).json()
                    state = "включены" if data.get("enabled") else "не запущены"
                    backup_status.setText(
                        f"Фоновые резервные копии: {state}; интервал: {data.get('interval_hours', '?')} ч. "
                        f"Последняя: {data.get('last_backup') or 'ещё не создавалась'}"
                    )
                except (requests.RequestException, ValueError, TypeError):
                    backup_status.setText("Backend недоступен: статус резервных копий не получен.")

            def run_backup_now():
                try:
                    data = requests.post("http://127.0.0.1:8000/backups/run", timeout=30).json()
                    backup_status.setText(f"Резервная копия создана: {data.get('path', '')}")
                except (requests.RequestException, ValueError, TypeError) as error:
                    backup_status.setText(f"Backup не выполнен: {error}")

            actions = QHBoxLayout()
            save_path = QPushButton("СОХРАНИТЬ ПУТЬ")
            backup_now = QPushButton("СОЗДАТЬ КОПИЮ")
            save_path.setObjectName("settingsTileButton")
            backup_now.setObjectName("settingsTileButton")
            save_path.clicked.connect(lambda: (self.ui_settings.setValue("data_path", data_path_edit.text().strip()), self.ui_settings.sync(), backup_status.setText("Путь данных сохранён.")))
            backup_now.clicked.connect(run_backup_now)
            actions.addWidget(save_path)
            actions.addWidget(backup_now)
            layout.addLayout(actions)
            QTimer.singleShot(0, refresh_backup_status)

        section_page("ДАННЫЕ", "Папка локальных данных и фоновые резервные копии.", extra_builder=data_inline)
        def chat_inline(layout, edits):
            checks = []
            for key, label, fallback in (("chat_incoming_acrylic", "Стеклянные входящие сообщения", True), ("chat_outgoing_acrylic", "Стеклянные исходящие сообщения", False), ("chat_show_avatars", "Показывать аватары", True), ("chat_show_timestamps", "Показывать время сообщений", True), ("chat_compact_mode", "Компактный режим", False), ("chat_media_autoplay", "Автовоспроизведение медиа", False)):
                check = QCheckBox(label)
                check.setChecked(self.ui_settings.value(key, fallback, type=bool))
                checks.append((key, check))
                layout.addWidget(check)
            save = QPushButton("СОХРАНИТЬ НАСТРОЙКИ ЧАТА")
            save.setObjectName("settingsTileButton")
            save.clicked.connect(lambda: ([(self.ui_settings.setValue(key, check.isChecked())) for key, check in checks], self.ui_settings.sync(), self.assistant_label.setText("Настройки чата сохранены")))
            layout.addWidget(save)
        section_page("ЧАТ", "История, вложения, реакции, закрепления и медиаплееры.", extra_builder=chat_inline)

        devices_page = QFrame()
        devices_page.setObjectName("settingsCard")
        devices_page.setMaximumWidth(780)
        devices_layout = QVBoxLayout(devices_page)
        devices_title = QLabel("УСТРОЙСТВА И ВОЗМОЖНОСТИ")
        devices_title.setObjectName("settingsCardTitle")
        devices_layout.addWidget(devices_title)
        devices_hint = QLabel(
            "Функции подключаются лениво. Обычные текстовые и голосовые ответы "
            "не запускают камеру, vision, жесты или CAD."
        )
        devices_hint.setObjectName("settingsHint")
        devices_hint.setWordWrap(True)
        devices_layout.addWidget(devices_hint)
        capability_list = QListWidget()
        capability_list.setObjectName("providerProfilesList")
        capability_list.setMinimumHeight(250)
        devices_layout.addWidget(capability_list)
        devices_status = QLabel("Проверка возможностей…")
        devices_status.setObjectName("settingsHint")
        devices_status.setWordWrap(True)
        devices_layout.addWidget(devices_status)

        def refresh_capabilities(deep=False):
            try:
                data = requests.get(
                    "http://127.0.0.1:8000/devices/capabilities",
                    params={"probe": "true" if deep else "false"},
                    timeout=45 if deep else 6,
                ).json()
                capability_list.clear()
                for capability in data.get("capabilities", []):
                    marker = "●" if capability.get("available") else "○"
                    item = QListWidgetItem(
                        f"{marker}  {capability.get('name', capability.get('id'))} — "
                        f"{capability.get('status', 'нет данных')}"
                    )
                    item.setToolTip(str(capability.get("details") or ""))
                    capability_list.addItem(item)
                devices_status.setText(
                    "Готово. Глубокая проверка необязательных модулей выполняется только по кнопке."
                    if not deep else "Глубокая проверка завершена. Тяжёлые адаптеры запускаются только при вызове."
                )
            except (requests.RequestException, ValueError, TypeError) as error:
                devices_status.setText(f"Backend недоступен: {error}")

        def capture_camera():
            try:
                data = requests.post(
                    "http://127.0.0.1:8000/devices/camera/snapshot",
                    params={"index": int(self.hardware_settings.get("video_input_device", 0))},
                    timeout=10,
                ).json()
                devices_status.setText(f"Кадр сохранён: {data.get('path', 'неизвестный путь')}")
            except (requests.RequestException, ValueError, TypeError) as error:
                devices_status.setText(f"Снимок не выполнен: {error}")

        devices_actions = QHBoxLayout()
        refresh_devices = QPushButton("ОБНОВИТЬ СТАТУСЫ")
        snapshot_button = QPushButton("СДЕЛАТЬ СНИМОК")
        refresh_devices.setObjectName("settingsTileButton")
        snapshot_button.setObjectName("settingsTileButton")
        refresh_devices.clicked.connect(lambda: refresh_capabilities(True))
        snapshot_button.clicked.connect(capture_camera)
        devices_actions.addWidget(refresh_devices)
        devices_actions.addWidget(snapshot_button)
        devices_layout.addLayout(devices_actions)
        settings_stack.addWidget(devices_page)
        settings_stack.layout().setAlignment(devices_page, Qt.AlignLeft | Qt.AlignTop)
        QTimer.singleShot(0, refresh_capabilities)
        self.pages.addWidget(settings_page)
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
        dialog = UserProfileDialog(self.ui_settings, self.accent_hex, self, self.dialog_stylesheet())
        dialog.saved.connect(self._refresh_user_profile_card)
        dialog.exec()

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
        try:
            api_key = str(self.ui_settings.value("weather_api_key", "")).strip() or os.getenv("OPENWEATHER_API_KEY") or self._read_local_env_value(
                "OPENWEATHER_API_KEY"
            )

            if not api_key:
                self.weather_city_label.setText("Мурино")
                self.weather_temp_label.setText("--°C")
                self.weather_desc_label.setText("не настроена")
                return

            configured_city = str(self.ui_settings.value("weather_city", "")).strip() or os.getenv("WEATHER_CITY") or self._read_local_env_value(
                "WEATHER_CITY"
            )
            if configured_city:
                city = configured_city
            else:
                geo_response = requests.get("http://ip-api.com/json", timeout=5)
                geo_response.raise_for_status()
                geo = geo_response.json()
                city = geo.get("city")
                if not city:
                    raise ValueError("Город не найден по IP")

            url = (
                "https://api.openweathermap.org/data/2.5/weather"
                f"?q={city}&appid={api_key}&units=metric&lang=ru"
            )

            weather_response = requests.get(url, timeout=8)
            weather_response.raise_for_status()
            data = weather_response.json()

            temp = round(data["main"]["temp"])
            city_display = str(city).split(",", 1)[0].strip()
            desc = data["weather"][0]["description"]

            weather_entry = data["weather"][0]
            pixmap, _, _ = self._load_tech_weather_icon(
                weather_entry.get("id"), weather_entry.get("icon")
            )

            self.weather_icon.setPixmap(
                pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

            self.weather_city_label.setText(city_display)
            self.weather_temp_label.setText(f"{temp}°C")
            self.weather_desc_label.setText(desc)
            if getattr(self, "detached_weather", None) is not None:
                self.detached_weather.refresh_from_owner()

        except (KeyError, TypeError, ValueError, requests.RequestException, json.JSONDecodeError):
            self.weather_city_label.setText("Мурино")
            self.weather_temp_label.setText("--°C")
            self.weather_desc_label.setText("недоступна")
            if getattr(self, "detached_weather", None) is not None:
                self.detached_weather.refresh_from_owner()

    # ---------------- STYLES ----------------

    def apply_styles(self):

        accent = self.accent_hex
        accent_hover = self.accent_color.lighter(120).name()

        self.setStyleSheet("""

#container{

border-radius:30px;

background:qlineargradient(
x1:0,y1:0,
x2:1,y2:1,
stop:0 rgba(20,20,25,220),
stop:0.35 rgba(15,15,20,220),
stop:0.65 rgba(10,10,15,230),
stop:1 rgba(30,30,35,220)
);

border:1px solid rgba(255,255,255,40);

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
height:50px;
color:white;
padding-left:16px;
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
border:1px solid #00EBF5;
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
color:#111;
background:rgba(255,255,255,220);
}

QComboBox QAbstractItemView{
color:#111;
background:white;
}

#settingsTitle{
font-size:22px;
font-weight:bold;
color:#FFFFFF;
}

#settingsCard{
border:1px solid rgba(255,255,255,45);
border-radius:14px;
background:rgba(255,255,255,0.07);
}

#settingsCardTitle{
font-size:12px;
font-weight:bold;
letter-spacing:1px;
color:#FFFFFF;
}

#settingsHint{
color:rgba(255,255,255,165);
font-size:12px;
}

#historyRefresh{
background:#2E89FF;
border:none;
border-radius:10px;
color:#FFFFFF;
padding:0 10px;
}

#historyRefresh:hover{
background:#4aa0ff;
}

#settingsPage QPushButton{
color:#FFFFFF;
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
background:rgba(255,255,255,200);
border-radius:10px;
padding-left:10px;
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

""".replace("#2E89FF", accent)
        .replace("#4aa0ff", accent_hover)
        .replace("#FFFFFF", self.text_color_hex))

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

        if hasattr(self, "settings_page_widget"):
            self.settings_page_widget.setStyleSheet(f"""
                #settingsPage QLabel, #settingsPage QCheckBox,
                #settingsPage QRadioButton, #settingsPage QGroupBox,
                #settingsPage QFormLabel {{ color: #FFFFFF; }}
                #settingsPage QPushButton {{
                    background: {accent}; color: #FFFFFF; border: none;
                    border-radius: 8px; min-height: 30px; max-width: 260px;
                    padding: 5px 14px;
                }}
                #settingsPage QPushButton:hover {{ background: {accent_hover}; }}
                #settingsPage QPlainTextEdit {{
                    background: rgba(4, 10, 18, 180); color: #FFFFFF;
                    border: 1px solid rgba(255,255,255,55); border-radius: 8px;
                }}
            """)

        if hasattr(self, "main_container") and not getattr(self, "widget_mode", False):
            self.main_container.setStyleSheet(self.container_visual_stylesheet())


    # ---------------- COMMAND ----------------

    def send_command(self, text=None, attachments=None):

        if text is None:
            text = self.composer.message_input.toPlainText().strip()
        attachments = attachments or []
        text = str(text).strip()

        if not text and not attachments:
            return

        if getattr(self, "_chat_request_thread", None) and self._chat_request_thread.isRunning():
            return
        display_text = text or "[Вложение]"
        local_user_id = self.add_message(display_text, True, attachments=attachments)
        self._chat_request_local_id = local_user_id
        self._chat_request_display_text = display_text
        self._chat_request_chat_id = getattr(self, "current_chat_id", "default")
        self._chat_request_turn_id = str(uuid.uuid4())
        self._chat_request_cancelled = False
        self._chat_request_processing_id = self.add_message(
            "[Processing...]", False, status="processing"
        )
        self.composer.set_sending(True)
        self._chat_request_thread = QThread(self)
        self._chat_request_worker = ChatRequestWorker({
            "message": text,
            "attachments": attachments,
            "chat_id": getattr(self, "current_chat_id", "default"),
            "turn_id": self._chat_request_turn_id,
            "custom_instructions": str(self.ui_settings.value("custom_instructions", "") or ""),
            "preferred_address": str(self.ui_settings.value("preferred_address", "") or ""),
            "chat_system_prompt": str(self.ui_settings.value("chat_system_prompt", "") or ""),
        })
        self._chat_request_worker.moveToThread(self._chat_request_thread)
        self._chat_request_thread.started.connect(self._chat_request_worker.run)
        self._chat_request_worker.finished.connect(self._chat_request_finished)
        self._chat_request_worker.failed.connect(self._chat_request_failed)
        self._chat_request_worker.finished.connect(self._chat_request_thread.quit)
        self._chat_request_worker.failed.connect(self._chat_request_thread.quit)
        self._chat_request_thread.finished.connect(self._chat_request_worker.deleteLater)
        self._chat_request_thread.finished.connect(self._chat_request_thread.deleteLater)
        self._chat_request_thread.finished.connect(self._chat_request_done)
        self._chat_request_thread.start()
        self._start_runtime_delta_worker()

    def _start_runtime_delta_worker(self):
        self._stop_runtime_delta_worker()
        turn_id = getattr(self, "_chat_request_turn_id", "")
        if not turn_id:
            return
        self._runtime_delta_thread = QThread(self)
        self._runtime_delta_worker = RuntimeDeltaWorker(turn_id)
        self._runtime_delta_worker.moveToThread(self._runtime_delta_thread)
        self._runtime_delta_thread.started.connect(self._runtime_delta_worker.run)
        self._runtime_delta_worker.delta.connect(self._apply_runtime_delta)
        self._runtime_delta_worker.stage.connect(self._apply_runtime_stage)
        self._runtime_delta_worker.finished.connect(self._runtime_delta_thread.quit)
        self._runtime_delta_worker.finished.connect(self._runtime_delta_worker.deleteLater)
        self._runtime_delta_thread.finished.connect(self._runtime_delta_thread.deleteLater)
        self._runtime_delta_thread.finished.connect(self._runtime_delta_done)
        self._runtime_delta_thread.start()

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

    @Slot()
    def _runtime_delta_done(self):
        self._runtime_delta_thread = None
        self._runtime_delta_worker = None

    @Slot()
    def cancel_chat_request(self):
        turn_id = getattr(self, "_chat_request_turn_id", "")
        thread = getattr(self, "_chat_request_thread", None)
        if not turn_id or not thread or not thread.isRunning():
            return
        self._chat_request_cancelled = True
        self._stop_runtime_delta_worker()
        self.composer.set_sending(False, "Запрос отменён")
        processing_id = getattr(self, "_chat_request_processing_id", None)
        if processing_id:
            self.chat_view.page().runJavaScript(
                "window.removeMessage && window.removeMessage(" + json.dumps(processing_id) + ");"
            )
        try:
            requests.post(
                f"http://127.0.0.1:8000/chat/cancel/{requests.utils.quote(turn_id, safe='')}",
                timeout=2,
            )
        except requests.RequestException:
            pass

    @Slot(object)
    def _chat_request_finished(self, data):
        self._stop_runtime_delta_worker()
        if getattr(self, "_chat_request_cancelled", False):
            return
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
            return
        if self.current_chat_id == getattr(self, "_chat_request_chat_id", "default"):
            processing_id = getattr(self, "_chat_request_processing_id", None)
            if processing_id:
                self.chat_view.page().runJavaScript(
                    "window.removeMessage && window.removeMessage(" + json.dumps(processing_id) + ");"
                )
            self.add_message("Ошибка соединения", False)
        self.composer.set_sending(False, "Не удалось отправить сообщение")

    @Slot()
    def _chat_request_done(self):
        self.composer.set_sending(False)
        self._chat_request_thread = None
        self._chat_request_worker = None

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
            json.dumps("http://127.0.0.1:8000") + ");"
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
            response = requests.get(
                "http://127.0.0.1:8000/chat/history",
                params={
                    "chat_id": getattr(self, "current_chat_id", "default"),
                    "limit": max(10, min(100, page_size)),
                    "latest": "true",
                },
                timeout=5,
            )
            response.raise_for_status()
            messages = response.json().get("messages", [])
        except (requests.RequestException, ValueError, TypeError):
            messages = []
        self.chat_view.page().runJavaScript(
            "window.loadMessages && window.loadMessages(" +
            json.dumps(messages, ensure_ascii=False) + ");"
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

    def closeEvent(self, event):
        """Release the microphone when the Jarvis window is closed."""
        worker = getattr(self, "_dictation_worker", None)
        thread = getattr(self, "_dictation_thread", None)
        if worker and thread and thread.isRunning():
            worker.request_cancel()
            thread.quit()
            thread.wait(1500)
        if hasattr(self, "status_widget"):
            self.status_widget.close()
        try:
            requests.post("http://127.0.0.1:8000/voice/stop", timeout=2)
        except requests.RequestException:
            pass
        super().closeEvent(event)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()

def main() -> int:
    app = QApplication(sys.argv)
    window = JarvisUI()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
