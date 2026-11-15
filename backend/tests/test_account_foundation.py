from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from account.application.account_context import AccountContextService, LocalOnlyAccountContextProvider
from account.application.canonical_mapper import CanonicalMapper
from account.application.import_preview_service import ImportPreviewService
from account.application.inventory_service import InventoryService
from account.application.local_data_adapter import LocalDataAdapter
from account.domain.enums import AccountLifecycleState, DataClass, InventoryItemStatus
from account.domain.ids import is_uuid7, new_uuid7
from account.infrastructure.local_sqlite_reader import ReadOnlySQLiteReader
from account.ports.identity_store import InMemoryIdentityStore


class AccountFoundationTests(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        db_path = root / "jarvis_state.sqlite3"
        attachment = root / "present.bin"
        attachment.write_bytes(b"fixture attachment")
        connection = sqlite3.connect(db_path)
        connection.executescript(
            """
            CREATE TABLE chat_sessions (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE chat_messages (
                id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, attachments_json TEXT NOT NULL DEFAULT '[]',
                reply_to TEXT, created_at TEXT
            );
            CREATE TABLE chat_reactions (
                message_id TEXT, reaction TEXT, actor TEXT, created_at TEXT,
                PRIMARY KEY(message_id, reaction, actor)
            );
            CREATE TABLE chat_pins (
                message_id TEXT PRIMARY KEY, actor TEXT, created_at TEXT
            );
            CREATE TABLE chat_attachments (
                attachment_id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
                original_name TEXT NOT NULL, stored_path TEXT NOT NULL,
                media_type TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT
            );
            CREATE TABLE requests (request_id TEXT PRIMARY KEY, status TEXT);
            INSERT INTO chat_sessions VALUES ('local-chat', 'Fixture', 0, 1, '2026-01-01', '2026-01-02');
            INSERT INTO chat_messages VALUES ('msg_local', 'local-chat', 'user', 'hello', '[]', NULL, '2026-01-01');
            INSERT INTO chat_messages VALUES ('msg_orphan', 'missing-chat', 'assistant', 'orphan', '[]', NULL, '2026-01-01');
            INSERT INTO chat_reactions VALUES ('msg_local', '👍', 'user', '2026-01-01');
            INSERT INTO chat_pins VALUES ('msg_local', 'user', '2026-01-01');
            """
        )
        connection.execute(
            "INSERT INTO chat_attachments VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("att_present", "msg_local", "present.bin", str(attachment), "application/octet-stream", attachment.stat().st_size, "2026-01-01"),
        )
        connection.execute(
            "INSERT INTO chat_attachments VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("att_missing", "msg_local", "missing.bin", str(root / "missing.bin"), "application/octet-stream", 4, "2026-01-01"),
        )
        connection.commit()
        connection.close()
        return temporary, db_path

    def test_uuid7_helper_is_lowercase_and_versioned(self) -> None:
        value = new_uuid7()
        self.assertTrue(is_uuid7(value))
        self.assertEqual(value, value.lower())

    def test_local_context_is_explicitly_local_only(self) -> None:
        context = LocalOnlyAccountContextProvider().get_context()
        self.assertEqual(context.lifecycle, AccountLifecycleState.LOCAL_ONLY)
        self.assertTrue(context.is_local_only)
        self.assertIsNone(context.account.account_id)
        self.assertIsNone(context.device.device_id)

    def test_context_service_rejects_fake_account_transition(self) -> None:
        service = AccountContextService()
        service.begin_connecting()
        with self.assertRaises(ValueError):
            service.mark_authenticated_device(
                account=InMemoryIdentityStore().get_account(),
                device=InMemoryIdentityStore().get_device(),
                session=InMemoryIdentityStore().get_session(),
            )

    def test_reader_is_read_only_and_inventory_is_complete(self) -> None:
        temporary, db_path = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        before = db_path.read_bytes()
        reader = ReadOnlySQLiteReader(db_path, source_namespace="fixture-device")
        inventory = reader.get_inventory(compute_attachment_hashes=True)
        self.assertEqual(inventory.conversation_count, 1)
        self.assertEqual(inventory.message_count, 2)
        self.assertEqual(inventory.attachment_count, 2)
        self.assertEqual(inventory.reactions_count, 1)
        self.assertEqual(inventory.pins_count, 1)
        self.assertEqual(inventory.archive_count, 1)
        self.assertEqual(len(inventory.errors), 1)
        self.assertEqual(db_path.read_bytes(), before)
        self.assertEqual(inventory.messages[1].data_class, DataClass.EXCLUDED)
        statuses = {item.source_local_id: item.status for item in inventory.attachments}
        self.assertEqual(statuses["att_present"], InventoryItemStatus.AVAILABLE)
        self.assertEqual(statuses["att_missing"], InventoryItemStatus.MISSING)
        with closing(sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE forbidden_write(id TEXT)")

    def test_preview_and_manifest_have_no_absolute_paths_or_duplicate_items(self) -> None:
        temporary, db_path = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        adapter = LocalDataAdapter(db_path, source_namespace="fixture-device")
        preview = ImportPreviewService(InventoryService(adapter), CanonicalMapper()).preview(
            compute_attachment_hashes=True,
            import_id=new_uuid7(),
        )
        self.assertTrue(is_uuid7(preview.import_id))
        source_ids = [item.source_local_id for item in preview.manifest.items]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        serialized = repr(preview)
        self.assertNotIn(str(db_path), serialized)
        self.assertTrue(preview.excluded)
        self.assertTrue(any(item.status is InventoryItemStatus.ORPHAN for item in preview.manifest.items))


if __name__ == "__main__":
    unittest.main()
