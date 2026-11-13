from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from services.chat_store import ChatStore


class ChatStoreTests(unittest.TestCase):
    def test_latest_page_is_chronological_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            store = ChatStore(Path(temp_dir) / "state.db")
            for index in range(5):
                store.add_message(chat_id="chat-1", role="user", content=f"msg-{index}")

            page = store.list_messages("chat-1", limit=2, latest=True)

            self.assertEqual([item["content"] for item in page], ["msg-3", "msg-4"])

    def test_repairs_missing_inline_emote_markers_without_touching_text(self) -> None:
        attachments = [
            {"emote": {"pack_id": "mailru_agent", "item_id": "koloboks/air_kiss"}},
            {"emote": {"pack_id": "mailru_agent", "item_id": "koloboks/bad"}},
        ]

        value = ChatStore._content_with_emote_markers("привет", attachments)

        self.assertEqual(value, "привет\ufffc\ufffc")

    def test_does_not_duplicate_existing_inline_emote_markers(self) -> None:
        attachments = [{"emote": {"pack_id": "telegram_retro", "item_id": "001"}}]

        value = ChatStore._content_with_emote_markers("до\ufffcпосле", attachments)

        self.assertEqual(value, "до\ufffcпосле")


if __name__ == "__main__":
    unittest.main()
