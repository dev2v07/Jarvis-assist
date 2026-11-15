from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.storage_migration_harness import run
from services.storage_registry import storage_paths_for_backend


class StorageRegistryTests(unittest.TestCase):
    def test_registry_keeps_bounded_context_paths_explicit(self) -> None:
        registry = storage_paths_for_backend(Path("C:/projects/Jarvis/backend"))
        self.assertEqual(registry.chat_state.name, "jarvis_state.sqlite3")
        self.assertEqual(registry.account_state.name, "account_state.sqlite3")
        self.assertEqual(registry.filesystem_index.name, "filesystem_index.db")
        self.assertNotEqual(registry.chat_state, registry.account_state)

    def test_harness_uses_sqlite_backup_and_verifies_rollback_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "backend"
            db = root / "data" / "jarvis_state.sqlite3"
            db.parent.mkdir(parents=True)
            connection = sqlite3.connect(db)
            try:
                connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
                connection.execute("INSERT INTO sample(value) VALUES('fixture')")
            finally:
                connection.close()
            work = Path(directory) / "work"
            report = run(root, work)
            repeated = run(root, work)
            store = report["stores"]["chat_state"]
            self.assertTrue(store["verified"])
            self.assertEqual(store["snapshot"]["integrity"], "ok")
            self.assertEqual(
                store["snapshot"]["logical_sha256"],
                repeated["stores"]["chat_state"]["snapshot"]["logical_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
