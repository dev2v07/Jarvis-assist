from __future__ import annotations

import unittest
from pathlib import Path


class ChatComposerContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]
    SOURCE = (ROOT / "chat_composer.py").read_text(encoding="utf-8")

    def test_voice_chat_uses_supplied_headphones_asset(self) -> None:
        icon = self.ROOT / "assets" / "CHAT" / "icons" / "headphones.svg"
        self.assertTrue(icon.is_file())
        self.assertIn('"icons" / "headphones.svg"', self.SOURCE)
        self.assertIn("self.voice_chat_button.setIcon(self._voice_chat_icon)", self.SOURCE)

    def test_active_voice_chat_keeps_stop_state_and_restores_icon(self) -> None:
        stop_icon = self.ROOT / "assets" / "CHAT" / "icons" / "stop.svg"
        self.assertTrue(stop_icon.is_file())
        self.assertIn('"icons" / "stop.svg"', self.SOURCE)
        self.assertIn("self.voice_button.setIcon(self._voice_stop_icon)", self.SOURCE)
        self.assertIn("self.voice_chat_button.setIcon(self._voice_stop_icon)", self.SOURCE)
        self.assertIn('self.voice_chat_button.setText("")', self.SOURCE)
        self.assertIn("self.voice_chat_button.setIcon(self._voice_chat_icon)", self.SOURCE)


if __name__ == "__main__":
    unittest.main()
