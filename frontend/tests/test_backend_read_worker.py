"""Exercise the real Qt worker bridge without a backend or user database."""

import time
import unittest
import threading
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QListWidget, QPushButton, QWidget

from frontend.jarvis_ui import (
    AIProviderDialog,
    ChatItemWidget,
    JarvisUI,
    NetworkOperationWorker,
    VoiceStatusClient,
)


class _Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"sessions": []}


class _WeatherResponse(_Response):
    def json(self):
        return {"main": {"temp": 4.4}, "weather": [{"id": 804, "icon": "04d", "description": "пасмурно"}]}


class _SettingsResponse(_Response):
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _ReadProbe(QWidget):
    _run_network_operation = JarvisUI._run_network_operation
    _network_operation_finished = JarvisUI._network_operation_finished

    def __init__(self):
        super().__init__()
        self._network_jobs = []
        self._closing_after_jobs = False


class _ProviderDialogOwner(QWidget):
    def __init__(self):
        super().__init__()
        self.visual_settings = {"transparent_background": False, "window_opacity": 100}

    def dialog_stylesheet(self):
        return ""


class _ModelProbe(QWidget):
    on_chat_model_changed = JarvisUI.on_chat_model_changed
    _apply_chat_model_settings = JarvisUI._apply_chat_model_settings
    _set_chat_model = JarvisUI._set_chat_model

    def __init__(self):
        super().__init__()
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.addItems(["old:model", "new:model"])
        self.chat_subtitle = QLabel()
        self._chat_provider = "ollama"
        self._chat_model_confirmed = "old:model"
        self._chat_model_generation = 0
        self._chat_ollama_base_url = "http://127.0.0.1:11434"
        self.requests = []

    def _run_network_operation(self, operation, callback, error_callback, **kwargs):
        self.requests.append((operation, callback, error_callback, kwargs))


class _WeatherSettings:
    def __init__(self):
        self.values = {}

    def setValue(self, key, value):
        self.values[key] = value

    def sync(self):
        pass


class _WeatherProbe(QWidget):
    _validate_and_save_weather = JarvisUI._validate_and_save_weather

    def __init__(self):
        super().__init__()
        self.ui_settings = _WeatherSettings()
        self._weather_generation = 0
        self.jobs = []
        self.applied = []

    def _run_network_operation(self, operation, callback, error_callback, **kwargs):
        self.jobs.append((operation, callback, error_callback, kwargs))

    def _apply_weather_result(self, data, generation):
        self.applied.append((data, generation))


class _Page:
    def __init__(self):
        self.scripts = []

    def runJavaScript(self, script):
        self.scripts.append(script)


class _ChatView:
    def __init__(self):
        self._page = _Page()

    def page(self):
        return self._page


class _HistoryProbe(QWidget):
    load_chat_history = JarvisUI.load_chat_history
    _apply_chat_history = JarvisUI._apply_chat_history
    _chat_history_failed = JarvisUI._chat_history_failed
    load_history_sessions = JarvisUI.load_history_sessions
    _history_sessions_failed = JarvisUI._history_sessions_failed
    _apply_history_sessions = JarvisUI._apply_history_sessions

    def __init__(self):
        super().__init__()
        self.ui_settings = type("Settings", (), {"value": lambda _self, _key, default: default})()
        self.current_chat_id = "chat-a"
        self._chat_history_generation = 0
        self._history_sessions_generation = 0
        self._displayed_chat_id = None
        self.chat_view = _ChatView()
        self.history_list = QListWidget()
        self.history_hint = QLabel()
        self.refresh_history_button = QPushButton()
        self.jobs = []
        self.status_overrides = []

    def _run_network_operation(self, operation, callback, error_callback, **kwargs):
        self.jobs.append((operation, callback, error_callback, kwargs))

    def _set_chat_status_override(self, *args):
        self.status_overrides.append(args)


class _SessionListProbe(QWidget):
    add_chat_item = JarvisUI.add_chat_item
    _apply_chat_sessions = JarvisUI._apply_chat_sessions

    def __init__(self):
        super().__init__()
        self.pinned_chats_list = QListWidget()
        self.chats_list = QListWidget()
        self.current_chat_id = "chat-current"
        self.accent_hex = "#00AAFF"
        self._fullscreen_mode = False
        self._sessions_read_pending = True
        self._sessions_reload_requested = False
        self._unread_chat_ids = {"chat-unread"}
        self._recent_chat_activity = {"chat-written": 1}

    def _refresh_sidebar_layout(self):
        pass

    def load_chat_sessions(self):
        raise AssertionError("unexpected reload")

    def chat_menu(self, *_args):
        pass


class BackendReadWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_slow_backend_read_does_not_hold_gui_event_loop(self):
        probe = _ReadProbe()
        events = []
        def slow_get(_url, timeout):
            time.sleep(0.2)
            return _Response()

        with patch("frontend.jarvis_ui.requests.get", side_effect=slow_get):
            QTimer.singleShot(0, lambda: events.append("gui-tick"))
            started = time.monotonic()
            probe._run_network_operation(
                "sessions",
                lambda data: events.append(("result", data, QThread.currentThread() == self.app.thread())),
                lambda error: events.append(("error", error)),
            )
            self.assertLess(time.monotonic() - started, 0.1)
            deadline = time.monotonic() + 3
            while (not any(isinstance(item, tuple) for item in events) or probe._network_jobs) and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)

        self.assertEqual(events[0], "gui-tick")
        self.assertEqual(events[1], ("result", {"sessions": []}, True))
        self.assertEqual(probe._network_jobs, [])
        probe.deleteLater()

    def test_chat_send_uses_shared_network_bridge(self):
        probe = _ReadProbe()
        events = []

        def fake_post(url, json, timeout):
            self.assertTrue(url.endswith("/chat"))
            self.assertEqual(json["chat_id"], "temporary-test-chat")
            self.assertEqual(timeout, 60)
            return _SettingsResponse({"response": "готово", "message_id": "assistant-1"})

        with patch("frontend.jarvis_ui.requests.post", side_effect=fake_post):
            probe._run_network_operation(
                "chat-send",
                events.append,
                lambda error: events.append({"error": error}),
                payload={"message": "проверка", "chat_id": "temporary-test-chat"},
            )
            deadline = time.monotonic() + 3
            while (not events or probe._network_jobs) and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)

        self.assertEqual(events, [{"response": "готово", "message_id": "assistant-1"}])
        self.assertEqual(probe._network_jobs, [])
        probe.deleteLater()

    def test_recent_chat_activity_and_background_unread_marker(self):
        probe = _SessionListProbe()
        probe._apply_chat_sessions({"sessions": [
            {"id": "chat-unread", "title": "Unread", "pinned": False},
            {"id": "chat-written", "title": "Written", "pinned": False},
        ]})

        first = probe.chats_list.item(0)
        self.assertEqual(first.data(Qt.ItemDataRole.UserRole), "chat-written")
        unread_item = probe.chats_list.item(1)
        unread_widget = probe.chats_list.itemWidget(unread_item)
        self.assertIsInstance(unread_widget, ChatItemWidget)
        self.assertTrue(unread_widget._unread)
        self.assertFalse(unread_widget.unread_dot.isHidden())

        unread_widget.set_active(True, probe.accent_hex)
        unread_widget.set_unread(True, probe.accent_hex)
        self.assertTrue(unread_widget._unread)
        self.assertTrue(unread_widget.unread_dot.isHidden())
        probe.deleteLater()

    def test_model_selection_rolls_back_on_backend_error(self):
        probe = _ModelProbe()
        probe.chat_model_combo.setCurrentText("new:model")
        probe.on_chat_model_changed("new:model")
        self.assertFalse(probe.chat_model_combo.isEnabled())
        operation, _success, failure, kwargs = probe.requests.pop()
        self.assertEqual(operation, "save")
        self.assertEqual(kwargs["payload"]["ollama_model"], "new:model")
        failure("network timeout")
        self.assertTrue(probe.chat_model_combo.isEnabled())
        self.assertEqual(probe.chat_model_combo.currentText(), "old:model")
        self.assertIn("network timeout", probe.chat_subtitle.text())
        probe.deleteLater()

    def test_provider_dialog_save_uses_selected_read_only_model(self):
        owner = _ProviderDialogOwner()
        dialog = AIProviderDialog(owner, "ollama")
        dialog._set_model_choices(["qwen3:8b", "qwen3:27b"], "qwen3:8b")
        self.assertEqual(dialog.model.currentText(), "qwen3:8b")
        dialog.model.setCurrentText("qwen3:27b")
        self.assertEqual(dialog.model.currentText(), "qwen3:27b")
        with patch("frontend.jarvis_ui.start_network_operation") as start_operation:
            dialog.save_provider()

        args, kwargs = start_operation.call_args
        self.assertIs(args[0], dialog)
        self.assertEqual(args[1], "save")
        self.assertEqual(kwargs["payload"]["provider"], "ollama")
        self.assertEqual(kwargs["payload"]["ollama_model"], "qwen3:27b")
        self.assertFalse(dialog.model.isEditable())
        dialog._apply_saved_provider({
            "provider": "ollama",
            "config": {
                "HEL_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "HEL_OLLAMA_MODEL": "qwen3:27b",
            },
        })
        self.assertEqual(dialog.model.currentText(), "qwen3:27b")
        dialog.deleteLater()
        owner.deleteLater()

    def test_voice_status_poll_keeps_gui_responsive_and_coalesces_requests(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.get_count += 1
                time.sleep(0.25)
                body = json.dumps({"enabled": False, "conversation_worker": False}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.server.post_count += 1
                self.server.last_payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                time.sleep(0.1)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.get_count = 0
        server.post_count = 0
        server.last_payload = None
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = VoiceStatusClient(f"http://127.0.0.1:{server.server_port}")
        received = []
        gui_ticks = []
        client.status_received.connect(received.append)
        ticker = QTimer()
        ticker.timeout.connect(lambda: gui_ticks.append(time.monotonic()))
        ticker.start(20)
        try:
            client.poll()
            client.poll()
            deadline = time.monotonic() + 3
            while not received and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            self.assertEqual(received, [{"enabled": False, "conversation_worker": False}])
            self.assertGreaterEqual(len(gui_ticks), 4)
            self.assertEqual(server.get_count, 1)

            client.ensure_worker({"microphone_index": -1, "microphone_enabled": True})
            client.ensure_worker({"microphone_index": -1, "microphone_enabled": True})
            while (server.post_count < 1 or client._start_reply is not None) and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            self.assertEqual(server.post_count, 1)
            self.assertEqual(server.last_payload["microphone_enabled"], True)
        finally:
            ticker.stop()
            client.shutdown()
            client.deleteLater()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

    def test_weather_fetch_uses_worker_and_returns_render_data(self):
        probe = _ReadProbe()
        events = []

        def slow_get(url, params, timeout):
            self.assertIn("openweathermap.org", url)
            self.assertEqual(params["q"], "Мурино")
            time.sleep(0.2)
            return _WeatherResponse()

        with patch("frontend.jarvis_ui.requests.get", side_effect=slow_get):
            QTimer.singleShot(0, lambda: events.append("gui-tick"))
            probe._run_network_operation(
                "weather", lambda data: events.append(data),
                lambda error: events.append(("error", error)),
                payload={"city": "Мурино", "api_key": "test-only"},
            )
            deadline = time.monotonic() + 3
            while (len(events) < 2 or probe._network_jobs) and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)

        self.assertEqual(events[0], "gui-tick")
        self.assertEqual(events[1]["temp"], 4)
        self.assertEqual(events[1]["description"], "пасмурно")
        self.assertEqual(probe._network_jobs, [])
        probe.deleteLater()

    def test_weather_settings_commit_only_after_successful_validation(self):
        probe = _WeatherProbe()
        status = QLabel()
        button = QWidget()
        probe._validate_and_save_weather("Мурино", "test-only", status, button)
        self.assertFalse(button.isEnabled())
        operation, success, failure, _kwargs = probe.jobs.pop()
        self.assertEqual(operation, "weather-validate")
        failure("Timeout")
        self.assertTrue(button.isEnabled())
        self.assertEqual(probe.ui_settings.values, {})

        probe._validate_and_save_weather("Мурино", "test-only", status, button)
        _operation, success, _failure, _kwargs = probe.jobs.pop()
        success({"city": "Мурино", "temp": 4, "description": "пасмурно"})
        self.assertEqual(probe.ui_settings.values["weather_city"], "Мурино")
        self.assertEqual(probe.ui_settings.values["weather_api_key"], "test-only")
        self.assertEqual(probe.applied[0][1], 1)
        self.assertTrue(button.isEnabled())
        probe.deleteLater()

    def test_settings_startup_reads_do_not_wait_in_gui_thread(self):
        probe = _ReadProbe()
        events = []

        def slow_get(url, **_kwargs):
            time.sleep(0.2)
            if url.endswith("/backups/status"):
                return _SettingsResponse({"enabled": True, "interval_hours": 24})
            if url.endswith("/devices/capabilities"):
                return _SettingsResponse({"capabilities": []})
            raise AssertionError(url)

        with patch("frontend.jarvis_ui.requests.get", side_effect=slow_get):
            QTimer.singleShot(0, lambda: events.append("gui-tick"))
            probe._run_network_operation("backup-status", lambda data: events.append(("backup", data)), events.append)
            probe._run_network_operation("capabilities", lambda data: events.append(("devices", data)), events.append)
            deadline = time.monotonic() + 3
            while (len(events) < 3 or probe._network_jobs) and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)

        self.assertEqual(events[0], "gui-tick")
        self.assertEqual({item[0] for item in events[1:]}, {"backup", "devices"})
        self.assertEqual(probe._network_jobs, [])
        probe.deleteLater()

    def test_explicit_settings_actions_keep_existing_api_contracts(self):
        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, kwargs))
            return _SettingsResponse({"path": "test-output"})

        with patch("frontend.jarvis_ui.requests.post", side_effect=fake_post):
            backup = NetworkOperationWorker("backup-run")
            camera = NetworkOperationWorker("camera-snapshot", params={"index": 2})
            results = []
            backup.finished.connect(results.append)
            camera.finished.connect(results.append)
            backup.run()
            camera.run()

        self.assertEqual([result["path"] for result in results], ["test-output", "test-output"])
        self.assertTrue(calls[0][0].endswith("/backups/run"))
        self.assertTrue(calls[1][0].endswith("/devices/camera/snapshot"))
        self.assertEqual(calls[1][1]["params"], {"index": 2})

    def test_chat_history_ignores_stale_result_after_chat_switch(self):
        probe = _HistoryProbe()
        probe.load_chat_history()
        operation, first_success, _first_error, kwargs = probe.jobs.pop()
        self.assertEqual(operation, "chat-history")
        self.assertEqual(kwargs["params"]["chat_id"], "chat-a")
        probe.current_chat_id = "chat-b"
        probe.load_chat_history()
        _operation, second_success, second_error, _kwargs = probe.jobs.pop()
        first_success({"messages": [{"content": "stale-a"}]})
        second_success({"messages": [{"content": "current-b"}]})
        scripts = probe.chat_view.page().scripts
        self.assertFalse(any("stale-a" in script for script in scripts))
        self.assertTrue(any("current-b" in script for script in scripts))
        second_error("Timeout")
        self.assertTrue(any("showNotification" in script for script in scripts))
        self.assertTrue(probe.status_overrides)
        probe.deleteLater()

    def test_history_sessions_error_preserves_existing_rows(self):
        probe = _HistoryProbe()
        probe.history_list.addItem("saved chat")
        probe.load_history_sessions()
        operation, _success, failure, _kwargs = probe.jobs.pop()
        self.assertEqual(operation, "history-sessions")
        self.assertFalse(probe.refresh_history_button.isEnabled())
        failure("Timeout")
        self.assertTrue(probe.refresh_history_button.isEnabled())
        self.assertEqual(probe.history_list.item(0).text(), "saved chat")
        self.assertIn("Не удалось", probe.history_hint.text())
        probe.deleteLater()


if __name__ == "__main__":
    unittest.main()
