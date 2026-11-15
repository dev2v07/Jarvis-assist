from __future__ import annotations

import unittest
from unittest.mock import patch

from services.voice_runtime import VoiceRuntime


class VoiceStatusFreshTurnTests(unittest.TestCase):
    def test_new_transcript_clears_previous_response_and_error(self) -> None:
        runtime = VoiceRuntime.__new__(VoiceRuntime)
        runtime._last_transcript = "old request"
        runtime._last_response = "old response"
        runtime._last_error = "old error"
        runtime._enabled = False
        runtime._follow_up_until = 0.0
        runtime._conversation_queue = __import__("queue").Queue(maxsize=1)
        runtime._response_router = type("Router", (), {"route": lambda self, text: type("Route", (), {"kind": "conversation", "intent": None})()})()
        runtime._voice_sessions = type("Sessions", (), {"active": {"source": "chat"}})()
        runtime._persist_voice_user = lambda text: None
        with patch("computer_control.get_last_command_feedback", return_value=None), patch("computer_control.has_pending_confirmation", return_value=False):
            runtime._handle_transcript("new question")
        self.assertEqual(runtime._last_transcript, "new question")
        self.assertEqual(runtime._last_response, "")
        self.assertEqual(runtime._last_error, "")
        self.assertEqual(runtime._phase, "уточняю информацию")
        self.assertEqual(runtime._conversation_queue.get_nowait(), "new question")


if __name__ == "__main__":
    unittest.main()
