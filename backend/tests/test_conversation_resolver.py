from __future__ import annotations

import unittest

from services.conversation_resolver import ConversationResolver


class ConversationResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = ConversationResolver()

    def test_sleep_question_is_deterministic_and_local(self) -> None:
        result = self.resolver.resolve("Хочешь спать?")
        self.assertEqual(result["id"], "sleep_jarvis_ready")
        self.assertEqual(result["answer"], "Я не сплю и готов к работе.")
        self.assertIsNone(result["audio_path"])

    def test_sleep_followup_uses_previous_turn(self) -> None:
        result = self.resolver.resolve(
            "Точно не хочешь спать?",
            [{"role": "user", "content": "Хочешь спать?"}],
        )
        self.assertEqual(result["id"], "sleep_followup_confirmed")
        self.assertIn("готов продолжать разговор", result["answer"])
        self.assertTrue(result["context_used"])

    def test_sleep_why_followup_stays_on_topic(self) -> None:
        result = self.resolver.resolve(
            "Почему ты не спишь?",
            [{"role": "user", "content": "Хочешь спать?"}],
        )
        self.assertEqual(result["id"], "sleep_followup_explanation")
        self.assertIn("всегда готов продолжить разговор", result["answer"])
        self.assertTrue(result["context_used"])

    def test_user_tired_message_is_supportive(self) -> None:
        result = self.resolver.resolve(
            "А я вот хочу спать",
            [{"role": "assistant", "content": "Я не сплю и готов к работе."}],
        )
        self.assertEqual(result["id"], "sleep_user_tired")
        self.assertIn("отдохните", result["answer"])

    def test_unrelated_request_is_deferred(self) -> None:
        self.assertIsNone(self.resolver.resolve("Расскажи про Intel 8086"))

    def test_good_assistant_question_has_one_local_answer(self) -> None:
        result = self.resolver.resolve("Ты хороший?")
        self.assertEqual(result["id"], "jarvis_good_assistant")
        self.assertIn("хорошим помощником", result["answer"])


if __name__ == "__main__":
    unittest.main()
