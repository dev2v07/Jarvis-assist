from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AssistantToggleContractTests(unittest.TestCase):
    SOURCE = (
        Path(__file__).resolve().parents[1] / "jarvis_ui.py"
    ).read_text(encoding="utf-8")

    def test_sidebar_assistant_toggle_is_not_a_visual_stub(self) -> None:
        self.assertNotIn("_assistant_toggle_stub", self.SOURCE)
        self.assertIn("toggle1.toggled.connect(self._assistant_toggle)", self.SOURCE)
        self.assertIn('self._toggle_voice_runtime()', self.SOURCE)

    def test_assistant_switch_reflects_actual_runtime_state(self) -> None:
        self.assertIn("self.assistant_toggle.setChecked(self.jarvis_state)", self.SOURCE)
        self.assertNotIn("self.assistant_toggle.setChecked(True)", self.SOURCE)

    def test_toggle_handler_has_state_guard_and_runtime_dispatch(self) -> None:
        tree = ast.parse(self.SOURCE)
        method = next(
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_assistant_toggle"
        )
        calls = [
            node for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_toggle_voice_runtime"
        ]
        self.assertEqual(len(calls), 1)
        self.assertTrue(any(isinstance(node, ast.Return) for node in ast.walk(method)))

    def test_ui_uses_one_configurable_api_root(self) -> None:
        endpoint_literals = [
            line for line in self.SOURCE.splitlines()
            if 'http://127.0.0.1:8000/' in line
        ]
        self.assertEqual(endpoint_literals, [])
        self.assertIn('API_ROOT = os.getenv("JARVIS_API_BASE_URL"', self.SOURCE)

    def test_active_chat_uses_accent_visual_state(self) -> None:
        self.assertIn("def set_active(self, active: bool, accent: str)", self.SOURCE)
        self.assertIn("self._refresh_active_chat_visuals()", self.SOURCE)
        self.assertIn("widget.set_active(", self.SOURCE)

    def test_delete_chat_confirmation_is_opaque(self) -> None:
        self.assertIn("dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)", self.SOURCE)
        self.assertIn("dialog.setAutoFillBackground(True)", self.SOURCE)
        self.assertIn("background: #12151c", self.SOURCE)

    def test_camera_enumeration_does_not_probe_six_devices_during_startup(self) -> None:
        self.assertIn("def enumerate_video_sources(preferred_index=0):", self.SOURCE)
        self.assertIn("проверка по запросу", self.SOURCE)
        method_start = self.SOURCE.index("def enumerate_video_sources(preferred_index=0):")
        method_end = self.SOURCE.index("    def apply_hardware_settings", method_start)
        self.assertNotIn("cv2.VideoCapture", self.SOURCE[method_start:method_end])

    def test_switching_chat_stops_local_voice_session_without_gui_network_wait(self) -> None:
        method_start = self.SOURCE.index("def _stop_voice_chat_before_switch")
        method_end = self.SOURCE.index("    def handle_composer_tool", method_start)
        method = self.SOURCE[method_start:method_end]
        self.assertIn('_stop_voice_mode_for_navigation("смене диалога")', method)
        self.assertNotIn("requests.get(", method)
        self.assertNotIn("requests.post(", method)
        self.assertIn("_dictation_worker", method)
        self.assertIn("request_cancel()", method)
        self.assertIn("Запись остановлена при смене диалога", method)

        helper_start = self.SOURCE.index("def _stop_voice_mode_for_navigation")
        helper_end = self.SOURCE.index("    def _sync_voice_mode_overlay", helper_start)
        helper = self.SOURCE[helper_start:helper_end]
        self.assertIn("_voice_chat_active", helper)
        self.assertIn('"voice-session-stop"', helper)
        self.assertIn("overlay.hide_mode()", helper)

    def test_dictation_stop_marks_the_completed_transcript_for_auto_send(self) -> None:
        self.assertIn("self._dictation_auto_send = True", self.SOURCE)
        recognized_start = self.SOURCE.index("def _dictation_recognized")
        recognized_end = self.SOURCE.index("    def _dictation_failed", recognized_start)
        recognized = self.SOURCE[recognized_start:recognized_end]
        self.assertIn("self.composer.submit()", recognized)
        self.assertIn("_dictation_auto_send", recognized)


if __name__ == "__main__":
    unittest.main()
