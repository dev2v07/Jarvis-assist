from __future__ import annotations

import unittest
import os
from pathlib import Path


class VoiceModeOverlayContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]
    SOURCE = (ROOT / "voice_mode_overlay.py").read_text(encoding="utf-8")

    def test_all_orb_frames_are_present(self) -> None:
        orb = self.ROOT / "assets" / "CHAT" / "orb"
        files = list(orb.glob("*.png"))
        self.assertEqual(len(files), 10)
        self.assertTrue((orb / "01 - ждет.png").is_file())
        self.assertEqual(len(list(orb.glob("02 - обработка (*.png"))), 5)
        self.assertEqual(len(list(orb.glob("03 - говорит (*.png"))), 4)

    def test_overlay_has_three_states_and_crossfade(self) -> None:
        self.assertIn('"waiting":', self.SOURCE)
        self.assertIn('"processing":', self.SOURCE)
        self.assertIn('"speaking":', self.SOURCE)
        self.assertIn("QParallelAnimationGroup", self.SOURCE)
        self.assertIn("class _OrbRings", self.SOURCE)
        self.assertIn("class _VoiceWaveform", self.SOURCE)
        self.assertIn("setFixedSize(170, 56)", self.SOURCE)
        self.assertIn("set_active", self.SOURCE)
        self.assertIn("drawEllipse", self.SOURCE)
        self.assertIn("stop_requested = Signal()", self.SOURCE)

    def test_chat_starts_overlay_and_runtime_phase_drives_state(self) -> None:
        ui = (self.ROOT / "jarvis_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.voice_mode_overlay.show_mode()", ui)
        self.assertIn("overlay.hide_mode()", ui)
        self.assertIn("_sync_voice_mode_overlay", ui)

    def test_orb_animation_and_calibration_are_wired(self) -> None:
        self.assertIn("_ORB_DISPLAY_SCALE = 0.30", self.SOURCE)
        self.assertIn("_ANIMATION_ENABLED = True", self.SOURCE)
        self.assertIn("_MOTION_ENABLED = True", self.SOURCE)
        self.assertIn('"processing": [0, 1, 2, 3, 4, 3, 2, 1]', self.SOURCE)
        self.assertIn('"speaking": [1]', self.SOURCE)
        self.assertIn("def _update_hover_rotation", self.SOURCE)
        self.assertIn("delta * 0.125", self.SOURCE)
        self.assertIn('"speaking": 2880', self.SOURCE)
        self.assertIn("def set_fullscreen_centered", self.SOURCE)
        self.assertIn("interval = {\"waiting\": 3000, \"processing\": 480, \"speaking\": 420}", self.SOURCE)
        self.assertIn("def _animate_hover", self.SOURCE)
        self.assertIn("def set_orb_host", self.SOURCE)
        self.assertIn("self.orb_canvas.hide()", self.SOURCE)
        self.assertIn("def set_calibration_mode", self.SOURCE)
        self.assertIn("def save_calibration", self.SOURCE)
        self.assertIn("voice_orb_size", self.SOURCE)
        self.assertIn("_calibration_mouse_move", self.SOURCE)
        ui = (self.ROOT / "jarvis_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.voice_mode_overlay.set_orb_host(self, self.chat_frame)", ui)
        self.assertIn('"--calibrate-voice-orb" in sys.argv', ui)
        self.assertIn("self.chat_status_dot", ui)
        self.assertIn("#00aaff", ui)
        self.assertIn("#ff3b4d", ui)
        self.assertIn("last_speaking_finished_at", ui)
        self.assertIn("_available_screen_geometry", ui)
        self.assertIn("self.chat_title.setSizePolicy", ui)

    def test_windowed_orb_is_bounded_and_fullscreen_scale_is_preserved(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QFrame, QWidget
        from voice_mode_overlay import VoiceModeOverlay

        app = QApplication.instance() or QApplication([])
        host = QWidget()
        host.resize(1280, 850)
        bounds = QFrame(host)
        bounds.setGeometry(220, 80, 1000, 720)
        overlay = VoiceModeOverlay(self.ROOT / "assets" / "CHAT", bounds)
        overlay.set_orb_host(host, bounds)
        overlay.set_fullscreen_centered(False)
        overlay._layout_orb()
        self.assertLessEqual(overlay.orb_canvas.width(), 320)
        self.assertLessEqual(overlay._orb_rings.width(), round(overlay.orb_canvas.width() * 1.72) + 2)
        bounds_origin = bounds.mapTo(host, bounds.rect().topLeft())
        expected_center = bounds_origin.x() + bounds.width() // 2
        self.assertLessEqual(abs(overlay.orb_canvas.geometry().center().x() - expected_center), 12)

        overlay.set_fullscreen_centered(True)
        overlay._layout_orb()
        self.assertGreater(overlay._orb_rings.width(), overlay.orb_canvas.width() * 2)
        overlay.hide_mode()
        host.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
