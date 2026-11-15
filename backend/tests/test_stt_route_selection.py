from __future__ import annotations

import unittest
from pathlib import Path

from services.voice_runtime import VoiceRuntime


class STTRouteSelectionTests(unittest.TestCase):
    def test_vosk_route_preserves_pre_roll_before_vad_segment(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "services" / "voice_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("pre_roll: deque[bytes] = deque(maxlen=6)", source)
        self.assertIn("speech.extend(pre_roll)", source)

    def test_default_live_route_is_stable_vosk(self) -> None:
        self.assertEqual(VoiceRuntime._stt_engine_name(), "vosk-silero")

    def test_status_exposes_selected_stt_engine(self) -> None:
        runtime = VoiceRuntime.__new__(VoiceRuntime)
        runtime._enabled = False
        runtime._thread = None
        runtime._microphone_enabled = True
        runtime._device_index = -1
        runtime._last_transcript = ""
        runtime._last_response = ""
        runtime._last_error = ""
        runtime._tts_available = False
        runtime._phase = "выключен"
        runtime._conversation_thread = None
        runtime._conversation_queue = __import__("queue").Queue(maxsize=1)
        runtime._local_response_service = type("Library", (), {"summary": lambda self: {}})()
        self.assertEqual(runtime.status()["stt_engine"], "vosk-silero")


if __name__ == "__main__":
    unittest.main()
