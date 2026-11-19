from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from services.voice_runtime import VoiceRuntime

BACKEND = Path(__file__).resolve().parents[1]


class _FakeTTSQueue:
    def __init__(self):
        self.spoken = []
        self.waited = threading.Event()

    def put_latest(self, text):
        self.spoken.append(text)

    def wait_idle(self, timeout=30.0):
        self.waited.set()
        return True


class VoiceSleepWakeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = VoiceRuntime(BACKEND)
        self.runtime._say_wav = Mock()
        self.runtime._extract_command = Mock(side_effect=AssertionError("wake phrase must not route"))

    def test_wake_phrase_detection(self):
        for phrase in ("Jarvis", "джарвис", "обвес", "Jarvis, включись", "Jarvis, привет", "Джарвис привет"):
            with self.subTest(phrase=phrase):
                self.assertTrue(self.runtime._is_wake_phrase(phrase))
        for phrase in ("Джарвис, как дела", "привет", "включись", "Спокойной ночи"):
            with self.subTest(phrase=phrase):
                self.assertFalse(self.runtime._is_wake_phrase(phrase))

    def test_active_runtime_always_acknowledges_repeated_wake_word(self):
        runtime = VoiceRuntime(BACKEND)
        runtime._say_wav = Mock()
        runtime._follow_up_until = float("inf")

        runtime._handle_transcript("джарвис")
        runtime._handle_transcript("обвес")

        self.assertEqual(runtime._mode, "ACTIVE")
        self.assertEqual(runtime._say_wav.call_count, 2)
        runtime._say_wav.assert_called_with("Да сэр.wav")

    def test_sleep_ignores_normal_speech_and_wakes_once(self):
        self.runtime._conversation_history = [{"role": "user", "content": "старый диалог"}]
        self.runtime._follow_up_until = 123.0
        self.runtime._enter_sleep("test")
        self.assertEqual(self.runtime._mode, "SLEEP")
        self.assertEqual(self.runtime._conversation_history, [])
        self.assertEqual(self.runtime._follow_up_until, 0.0)

        self.runtime._handle_transcript("как дела")
        self.assertEqual(self.runtime._mode, "SLEEP")
        self.runtime._extract_command.assert_not_called()

        self.runtime._handle_transcript("Jarvis, привет")
        self.assertEqual(self.runtime._mode, "ACTIVE")
        self.runtime._say_wav.assert_called_once()
        self.runtime._extract_command.assert_not_called()
        self.assertGreater(self.runtime._follow_up_until, 0.0)

    def test_sleep_after_farewell_waits_for_tts(self):
        queue = _FakeTTSQueue()
        self.runtime._tts_queue = queue
        self.runtime._sleep_after_speech()
        self.assertTrue(queue.waited.is_set())
        self.assertEqual(self.runtime._mode, "SLEEP")

    def test_farewell_answer_schedules_sleep(self):
        self.runtime._extract_command = lambda text: text
        self.runtime._knowledge_search_service.context_bundle = lambda text, limit: {}
        self.runtime._knowledge_search_service.answer = lambda text, history=None: {
            "id": "farewell_004", "answer": "Спокойной ночи, сэр. Хорошо отдохните.", "source": "conversational",
        }
        self.runtime._persist_voice_assistant = Mock()
        self.runtime._remember_conversation_turn = Mock()
        queue = _FakeTTSQueue()
        self.runtime._tts_queue = queue
        self.runtime._respond_conversationally("спокойной ночи")
        queue.waited.wait(2.0)
        self.assertEqual(self.runtime._mode, "SLEEP")
        self.assertTrue(queue.spoken)

    def test_off_command_sleeps_without_stopping_runtime(self):
        self.runtime._extract_command = lambda text: text
        route = Mock()
        route.kind = "command"
        route.intent = "off"
        self.runtime._response_router.route = Mock(return_value=route)
        self.runtime._handle_transcript("выключись")
        self.assertEqual(self.runtime._mode, "SLEEP")
        self.assertFalse(self.runtime.enabled)  # not started; sleep must not call stop()
        self.runtime._say_wav.assert_called_once()


if __name__ == "__main__":
    unittest.main()
