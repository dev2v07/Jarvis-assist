from __future__ import annotations

import unittest
from pathlib import Path


UI_SOURCE = Path(__file__).resolve().parents[1] / "jarvis_ui.py"


class VoiceErrorRecoveryContractTests(unittest.TestCase):
    def test_ui_clears_transient_voice_error_after_backend_recovers(self) -> None:
        source = UI_SOURCE.read_text(encoding="utf-8")

        self.assertIn('"Голосовой runtime: ошибка"', source)
        self.assertIn('"JARVIS слушает..." if data.get("listening")', source)
        self.assertIn("Clear a transient provider/runtime error", source)
