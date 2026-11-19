from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from services.conversation_resolver import ConversationResolver
from services.local_response_service import LocalResponseService

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data" / "Bible" / ".internal" / "sources" / "voice_responses" / "questions.json"

GROUPS = {
    "greetings_001": "greeting",
    "greetings_how_are_you": "greeting_how_are_you",
    "greetings_002": "good_morning",
    "mood_002": "how_are_you",
    "mood_010": "whats_new",
    "farewell_004": "good_night",
}

TEMPLATES = (
    "хороший повод разложить",
    "сначала отвечу коротко",
    "у меня есть план",
    "готовлю для вас разбор",
    "подбираю содержательный ответ",
    "сейчас проведу небольшой разбор",
)


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().replace("ё", "е").split())


class ConversationalGroupsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(QUESTIONS.read_text(encoding="utf-8"))
        cls.intents = {item["id"]: item for item in payload["intents"]}

    def test_six_groups_have_ten_unique_non_template_answers(self):
        for intent_id, group in GROUPS.items():
            with self.subTest(group=group):
                intent = self.intents[intent_id]
                responses = intent.get("responses", [])
                self.assertEqual(len(responses), 10)
                texts = [_norm(item.get("text", "")) for item in responses]
                self.assertEqual(len(set(texts)), 10, "answers must be unique")
                for text in texts:
                    self.assertFalse(
                        any(template in text for template in TEMPLATES),
                        "template boilerplate leaked into group %s" % group,
                    )
                self.assertEqual(intent.get("class"), "instant")
                self.assertTrue(intent.get("trigger_phrases"), "group has no recognition phrases")

    def test_good_morning_group_matches_with_regenerated_audio(self):
        service = LocalResponseService(ROOT / "backend")
        match = service.match("Доброе утро")
        self.assertIsNotNone(match)
        self.assertEqual(match.intent_id, "greetings_002")
        self.assertTrue(match.text)
        self.assertIsNotNone(match.audio_path)
        self.assertTrue(match.audio_path.is_file())

    def test_pending_good_morning_yes_and_no(self):
        yes = ConversationResolver.resolve(
            "Да, выспался",
            [{"role": "assistant", "content": "Доброе утро, сэр, вы выспались?"}],
        )
        self.assertIsNotNone(yes)
        self.assertIn("Отлично", yes["answer"])
        self.assertIn("планы", yes["answer"])
        no = ConversationResolver.resolve(
            "Не очень, плохо спал",
            [{"role": "assistant", "content": "Доброе утро, сэр, вы выспались?"}],
        )
        self.assertIn("восстановиться", no["answer"])

    def test_pending_how_are_you_positive_and_negative(self):
        positive = ConversationResolver.resolve(
            "Всё хорошо",
            [{"role": "assistant", "content": "У меня всё хорошо, сэр. А как ваши дела?"}],
        )
        self.assertIn("Рад слышать", positive["answer"])
        negative = ConversationResolver.resolve(
            "Плохо, устал",
            [{"role": "assistant", "content": "А как ваши дела?"}],
        )
        self.assertIn("Сочувствую", negative["answer"])

    def test_pending_whats_new_does_not_repeat_greeting(self):
        reply = ConversationResolver.resolve(
            "Пока не знаю",
            [{"role": "assistant", "content": "У меня всё спокойно, сэр. А у вас что нового?"}],
        )
        self.assertIn("Если появится задача", reply["answer"])

    def test_pending_whats_new_reacts_to_purchase(self):
        reply = ConversationResolver.resolve(
            "Купил новую гитару",
            [{"role": "assistant", "content": "У меня всё спокойно, сэр. А у вас что нового?"}],
        )
        self.assertIn("Поздравляю", reply["answer"])

    def test_pending_plans_switches_to_task_discussion(self):
        reply = ConversationResolver.resolve(
            "Давай поработаем над проектом",
            [{"role": "assistant", "content": "Какие планы на сегодня?"}],
        )
        self.assertIn("Принято", reply["answer"])
        self.assertIn("по шагам", reply["answer"])
        self.assertNotIn("Какие планы", reply["answer"])

    def test_two_step_chain_does_not_repeat_the_question(self):
        first = ConversationResolver.resolve(
            "Да, выспался",
            [{"role": "assistant", "content": "Доброе утро, сэр, вы выспались?"}],
        )
        history = [
            {"role": "assistant", "content": "Доброе утро, сэр, вы выспались?"},
            {"role": "user", "content": "Да, выспался"},
            {"role": "assistant", "content": first["answer"]},
        ]
        second = ConversationResolver.resolve("Нужно доделать проект", history)
        self.assertIn("Принято", second["answer"])
        self.assertIn("по шагам", second["answer"])
        self.assertNotIn("Какие планы", second["answer"])
        history.extend([
            {"role": "user", "content": "Нужно доделать проект"},
            {"role": "assistant", "content": second["answer"]},
        ])
        third = ConversationResolver.resolve("Нужно доделать отчёт", history)
        self.assertIn("Зафиксировал", third["answer"])

    def test_no_pending_question_leaves_normal_route(self):
        self.assertIsNone(
            ConversationResolver.resolve(
                "Что такое Intel 8086?",
                [{"role": "assistant", "content": "Intel 8086 — 16-разрядный процессор."}],
            )
        )


if __name__ == "__main__":
    unittest.main()
