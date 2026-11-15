from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from services.voice_runtime import VoiceRuntime


class VoiceKnowledgeTTSTests(unittest.TestCase):
    def test_conversational_knowledge_does_not_replace_selected_voice_with_wav(self) -> None:
        runtime = VoiceRuntime.__new__(VoiceRuntime)
        runtime.base_dir = Path(__file__).resolve().parents[1]
        runtime._conversation_history = []
        runtime._conversation_chat_id = None
        runtime._last_response = ""
        runtime._last_error = ""
        runtime._enabled = False
        runtime._follow_up_until = 0.0
        runtime._tts_available = True
        runtime._tts_queue = None
        runtime._voice_sessions = None
        runtime._chat_store = None
        runtime._knowledge_search_service = type(
            "Search",
            (),
            {"context_bundle": lambda self, text, limit: {}, "answer": lambda self, text, history: {"answer": "Ответ из Bible", "audio_path": "legacy.wav"}},
        )()
        runtime._local_response_service = None
        runtime._speak_tts = lambda text: None
        runtime._on_tts_error = lambda error: None
        try:
            with patch.object(runtime, "_say_wav", side_effect=AssertionError("conversation must not play linked WAV")):
                runtime._respond_conversationally("вопрос")
        finally:
            if runtime._tts_queue is not None:
                runtime._tts_queue.close()
        self.assertEqual(runtime._last_response, "Ответ из Bible")
        self.assertEqual(runtime._conversation_history[-1]["role"], "assistant")

    def test_model_route_receives_global_chat_context_anchor(self) -> None:
        runtime = VoiceRuntime.__new__(VoiceRuntime)
        runtime.base_dir = Path(__file__).resolve().parents[1]
        runtime._conversation_history = [
            {"role": "user", "content": "Я сейчас проверяю голосовой режим"},
            {"role": "assistant", "content": "Понял, проверяем голосовой режим"},
        ]
        runtime._conversation_chat_id = "chat-one"
        runtime._last_response = ""
        runtime._last_error = ""
        runtime._enabled = False
        runtime._follow_up_until = 0.0
        runtime._tts_available = True
        runtime._tts_queue = None
        runtime._voice_sessions = None
        runtime._chat_store = None
        runtime._last_model_ack = None
        runtime._knowledge_search_service = type(
            "Search",
            (),
            {"context_bundle": lambda self, text, limit: {}, "answer": lambda self, text, history: None},
        )()
        runtime._local_response_service = None
        runtime._speak_tts = lambda text: None
        runtime._on_tts_error = lambda error: None
        runtime._say_wav = lambda filename, wait_done=True: None
        captured: list[dict[str, str]] = []

        async def fake_stream(service, messages):
            captured.extend(messages)
            return "Ответ по текущей теме"

        try:
            with patch.object(runtime, "_stream_response", new=AsyncMock(side_effect=fake_stream)):
                runtime._respond_conversationally("Что именно мы сейчас проверяем?")
        finally:
            if runtime._tts_queue is not None:
                runtime._tts_queue.close()

        self.assertTrue(captured, runtime._last_error)
        self.assertEqual(captured[-1]["content"], "Что именно мы сейчас проверяем?")
        self.assertIn("Я сейчас проверяю голосовой режим", captured[0]["content"])
        self.assertIn("продолжай именно эту тему", captured[0]["content"])
        self.assertIn("короткий естественный уточняющий вопрос", captured[0]["content"])
        self.assertEqual(captured[1]["content"], "Я сейчас проверяю голосовой режим")


if __name__ == "__main__":
    unittest.main()
