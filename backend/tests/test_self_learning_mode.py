import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.chat_store import ChatStore
from services.self_learning_service import SelfLearningService


class _FakeLLM:
    async def chat(self, messages, system_prompt=None):
        return (
            '{"title":"Изолированная тема","category":"test",'
            '"summary":"Краткое резюме","content":"Структурированное содержание",'
            '"facts":["Факт"],"steps":[],'
            '"sources":[{"type":"user_provided","label":"Тест"}],'
            '"uncertainties":[]}'
        )


class SelfLearningModeTests(unittest.TestCase):
    def test_mode_is_bound_by_id_and_survives_rename_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite3"
            store = ChatStore(path)
            session = store.create_session("Самообучение")
            store.add_message(chat_id=session["id"], role="user", content="материал")
            bound = store.bind_session_mode_by_title("Самообучение", "SELF_LEARNING")
            self.assertEqual(bound["id"], session["id"])
            self.assertEqual(bound["mode"], "SELF_LEARNING")
            store.rename_session(session["id"], "Переименованное обучение")
            reopened = ChatStore(path)
            self.assertEqual(reopened.get_session(session["id"])["mode"], "SELF_LEARNING")
            self.assertIsNone(reopened.get_session("default")["mode"])

    def test_writer_deduplicates_and_refreshes_shared_index(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SelfLearningService(Path(directory), _FakeLLM())
            with patch("knowledge.build_bible_catalog.main") as rebuild:
                first = asyncio.run(service.process("Материал для теста"))
                second = asyncio.run(service.process("Материал для теста"))
            self.assertEqual(first["created"], 1)
            self.assertEqual(second["created"], 0)
            self.assertEqual(second["duplicates"], 1)
            self.assertTrue(first["indexed"])
            self.assertEqual(rebuild.call_count, 2)
            self.assertTrue(Path(first["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
