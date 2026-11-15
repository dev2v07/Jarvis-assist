from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from services.chat_store import ChatStore
from services.voice_runtime import VoiceRuntime
from services.voice_session_manager import VoiceSessionManager


class IsolatedVoiceRuntimeTests(unittest.TestCase):
    def test_existing_smalltalk_uses_instant_cached_wav(self) -> None:
        runtime = VoiceRuntime(Path(__file__).resolve().parents[1])

        selected = runtime._smalltalk_wav_for("как дела")
        self.assertIsNotNone(selected)
        self.assertIn(selected.name, runtime.SMALLTALK_WAVS)
        self.assertIsNone(runtime._smalltalk_wav_for("что нового"))
        self.assertIsNone(runtime._smalltalk_wav_for("объясни квантовую запутанность"))

    def test_news_phrases_are_separate_from_how_are_you(self) -> None:
        runtime = VoiceRuntime(Path(__file__).resolve().parents[1])
        self.assertEqual(len(runtime.NEWS_WAVS), 10)
        self.assertEqual(len({text for _filename, text in runtime.NEWS_WAVS}), 10)
        self.assertIsNone(runtime._news_wav_for("как дела"))
        selected = runtime._news_wav_for("что нового?")
        self.assertIsNotNone(selected)
        self.assertIn(selected[0].name, {filename for filename, _text in runtime.NEWS_WAVS})

    def test_news_turn_uses_cached_fish_wav_without_router_or_model(self) -> None:
        runtime = VoiceRuntime(Path(__file__).resolve().parents[1])
        runtime._extract_command = lambda text: text
        runtime._say_wav = Mock()
        runtime._response_router.route = Mock(side_effect=AssertionError("news must use cached WAV"))

        runtime._handle_transcript("что нового")

        runtime._say_wav.assert_called_once()
        self.assertTrue(runtime._last_response.startswith("wav:news_"))

    def test_active_widget_session_routes_transcript_without_repeated_wake_word(self) -> None:
        sessions = VoiceSessionManager()
        runtime = VoiceRuntime(Path(__file__).resolve().parents[1], voice_sessions=sessions)
        sessions.start(source="widget", chat_id="widget-chat")

        self.assertEqual(runtime._extract_command("обвес открой браузер"), "обвес открой браузер")
        self.assertEqual(runtime._extract_command("джарвис"), "")
        self.assertEqual(runtime._extract_command("джарвис привет"), "")

        sessions.stop()

    def test_voice_turns_are_persisted_in_the_active_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatStore(Path(temp_dir) / "state.db")
            sessions = VoiceSessionManager()
            runtime = VoiceRuntime(Path(__file__).resolve().parents[1], store, sessions)
            session = sessions.start(source="chat", chat_id="test-chat")

            runtime._persist_voice_user("Хочешь спать?")
            runtime._persist_voice_assistant("Я не сплю и готов к работе.")

            messages = store.list_messages("test-chat")
            self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
            self.assertEqual(messages[0]["content"], "Хочешь спать?")
            self.assertEqual(messages[1]["content"], "Я не сплю и готов к работе.")
            self.assertEqual(sessions.active["session_id"], session["session_id"])
            sessions.stop(session_id=session["session_id"])
            self.assertFalse(sessions.status()["active"])

    def test_same_transcript_is_persisted_when_chat_id_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatStore(Path(temp_dir) / "state.db")
            sessions = VoiceSessionManager()
            runtime = VoiceRuntime(Path(__file__).resolve().parents[1], store, sessions)

            first = sessions.start(source="chat", chat_id="chat-one")
            runtime._persist_voice_user("Проверка")
            sessions.stop(session_id=first["session_id"])
            second = sessions.start(source="chat", chat_id="chat-two")
            runtime._persist_voice_user("Проверка")

            self.assertEqual(len(store.list_messages("chat-one")), 1)
            self.assertEqual(len(store.list_messages("chat-two")), 1)
            sessions.stop(session_id=second["session_id"])

    def test_voice_context_is_restored_from_selected_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatStore(Path(temp_dir) / "state.db")
            store.create_session("Контекст", chat_id="chat-one")
            store.add_message(chat_id="chat-one", role="user", content="Я проверяю голосовой режим")
            store.add_message(chat_id="chat-one", role="assistant", content="Понял, проверяем голосовой режим")
            sessions = VoiceSessionManager()
            runtime = VoiceRuntime(Path(__file__).resolve().parents[1], store, sessions)

            session = sessions.start(source="chat", chat_id="chat-one")
            runtime.start()
            try:
                self.assertEqual(
                    runtime._conversation_history,
                    [
                        {"role": "user", "content": "Я проверяю голосовой режим"},
                        {"role": "assistant", "content": "Понял, проверяем голосовой режим"},
                    ],
                )
            finally:
                runtime.stop()
                sessions.stop(session_id=session["session_id"])

    def test_voice_context_does_not_leak_when_chat_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatStore(Path(temp_dir) / "state.db")
            store.create_session("Первый", chat_id="chat-one")
            store.create_session("Второй", chat_id="chat-two")
            store.add_message(chat_id="chat-one", role="user", content="Тема первого чата")
            store.add_message(chat_id="chat-one", role="assistant", content="Ответ первого чата")
            store.add_message(chat_id="chat-two", role="user", content="Тема второго чата")
            sessions = VoiceSessionManager()
            runtime = VoiceRuntime(Path(__file__).resolve().parents[1], store, sessions)

            first = sessions.start(source="chat", chat_id="chat-one")
            runtime.start()
            runtime.stop()
            sessions.stop(session_id=first["session_id"])
            second = sessions.start(source="chat", chat_id="chat-two")
            runtime.start()
            try:
                contents = [item["content"] for item in runtime._conversation_history]
                self.assertEqual(contents, ["Тема второго чата"])
                self.assertNotIn("Тема первого чата", contents)
                self.assertNotIn("Ответ первого чата", contents)
            finally:
                runtime.stop()
                sessions.stop(session_id=second["session_id"])

    def test_second_voice_owner_is_rejected_without_replacing_first(self) -> None:
        sessions = VoiceSessionManager()
        first = sessions.start(source="widget", chat_id="widget-chat")
        with self.assertRaises(RuntimeError):
            sessions.start(source="chat", chat_id="chat-chat")
        self.assertEqual(sessions.active["session_id"], first["session_id"])
        sessions.stop(session_id=first["session_id"])

    def test_command_route_does_not_play_ack_before_command_wav(self) -> None:
        runtime = VoiceRuntime(Path(__file__).resolve().parents[1])
        runtime._extract_command = lambda text: text
        runtime._say_wav = Mock()
        runtime._local_response_service.match = Mock(
            side_effect=AssertionError("command route must not use a second ack route")
        )
        with patch("computer_control.find_intent", return_value="open_browser"), \
             patch("computer_control.run_command", return_value=True), \
             patch("computer_control.get_last_command_feedback", return_value=None):
            runtime._handle_transcript("открой браузер")

        runtime._say_wav.assert_called_once_with(runtime.COMMAND_WAVS["open_browser"])


if __name__ == "__main__":
    unittest.main()
