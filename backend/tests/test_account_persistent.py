from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from account.application.auth_client import UnavailableAuthProvider
from account.domain.ids import new_uuid7
from account.infrastructure.dpapi_credentials import WindowsDPAPICredentialStore
from account.infrastructure.persistent_store import PersistentAccountStore


class PersistentAccountTests(unittest.TestCase):
    def test_account_store_persists_separate_identity_mapping_and_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "account_state.sqlite3"
            store = PersistentAccountStore(path)
            device_id = new_uuid7()
            account_id = new_uuid7()
            operation_id = new_uuid7()
            store.save_device(device_id, "windows", "test")
            store.save_account(account_id, "user@example.com", False)
            store.put_mapping({
                "source_namespace": "fixture",
                "source_local_id": "chat-1",
                "canonical_id": new_uuid7(),
                "entity_type": "conversation",
                "account_id": account_id,
                "import_id": new_uuid7(),
                "content_hash": "sha256:test",
                "status": "pending",
            })
            operation = {
                "operation_id": operation_id,
                "account_id": account_id,
                "device_id": device_id,
                "entity_type": "conversation",
                "entity_id": "local-chat",
                "payload_hash": "sha256:test",
                "base_revision": 0,
                "payload": {"title": "Fixture"},
            }
            store.enqueue(operation)
            store.enqueue(operation)
            store.set_metadata("cursor", "0")
            reopened = PersistentAccountStore(path)
            self.assertEqual(reopened.get_device()["device_id"], device_id)
            self.assertEqual(reopened.get_account()["account_id"], account_id)
            self.assertEqual(reopened.get_metadata("cursor"), "0")
            self.assertEqual(len(reopened.pending_operations()), 1)
            self.assertEqual(reopened.pending_operations()[0]["operation_id"], operation_id)
            self.assertIsNotNone(reopened.get_mapping("fixture", "chat-1", "conversation", account_id))

            with closing(sqlite3.connect(path)) as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("account_identity", tables)
                self.assertIn("device_identity", tables)
                self.assertIn("entity_mapping", tables)
                self.assertIn("account_outbox", tables)
                self.assertNotIn("access_token", " ".join(tables))

    def test_outbox_result_is_replay_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = PersistentAccountStore(Path(directory) / "account.sqlite3")
            operation_id = new_uuid7()
            operation = {
                "operation_id": operation_id,
                "entity_type": "message",
                "payload_hash": "hash",
                "payload": {"content": "x"},
            }
            store.enqueue(operation)
            store.record_outbox_result(operation_id, status="retry", error="offline")
            self.assertEqual(store.pending_operations()[0]["retry_count"], 1)
            store.record_outbox_result(operation_id, status="sent")
            self.assertEqual(store.pending_operations(), [])

    def test_unavailable_auth_provider_never_fakes_success(self) -> None:
        result = UnavailableAuthProvider().login("user@example.com", "password")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "account_server_unavailable")
        self.assertTrue(UnavailableAuthProvider().logout().ok)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows DPAPI is Windows-only")
    def test_dpapi_credentials_are_not_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.dpapi"
            store = WindowsDPAPICredentialStore(path)
            store.write_tokens("access-secret", "refresh-secret")
            raw = path.read_bytes()
            self.assertNotIn(b"access-secret", raw)
            self.assertNotIn(b"refresh-secret", raw)
            self.assertEqual(store.read_access_token(), "access-secret")
            self.assertEqual(store.read_refresh_token(), "refresh-secret")
            store.clear()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
