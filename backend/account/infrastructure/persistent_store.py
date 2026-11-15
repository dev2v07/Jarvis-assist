from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class AccountStoreError(RuntimeError):
    pass


class AccountStoreCorruptError(AccountStoreError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class PersistentAccountStore:
    """Separate, versioned local store for Account System metadata.

    This database is intentionally not `jarvis_state.sqlite3`. It contains no
    passwords or tokens; those belong to CredentialStore. Schema creation is
    atomic and only targets the explicitly supplied Account System path.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS account_schema (
                            id INTEGER PRIMARY KEY CHECK(id = 1),
                            version INTEGER NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS account_identity (
                            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                            account_id TEXT,
                            email TEXT,
                            email_verified INTEGER NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS device_identity (
                            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                            device_id TEXT NOT NULL,
                            platform TEXT NOT NULL,
                            client_version TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            revoked_at TEXT
                        );
                        CREATE TABLE IF NOT EXISTS entity_mapping (
                            source_namespace TEXT NOT NULL,
                            source_local_id TEXT NOT NULL,
                            canonical_id TEXT NOT NULL,
                            entity_type TEXT NOT NULL,
                            account_id TEXT,
                            import_id TEXT,
                            content_hash TEXT,
                            status TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            PRIMARY KEY(source_namespace, source_local_id, entity_type, account_id)
                        );
                        CREATE TABLE IF NOT EXISTS sync_metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS account_outbox (
                            operation_id TEXT PRIMARY KEY,
                            account_id TEXT,
                            device_id TEXT,
                            entity_type TEXT NOT NULL,
                            entity_id TEXT,
                            payload_hash TEXT NOT NULL,
                            base_revision INTEGER,
                            status TEXT NOT NULL,
                            retry_count INTEGER NOT NULL DEFAULT 0,
                            next_attempt_at TEXT,
                            last_error TEXT,
                            payload_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        """
                    )
                    row = connection.execute("SELECT version FROM account_schema WHERE id=1").fetchone()
                    if row is None:
                        connection.execute(
                            "INSERT INTO account_schema(id, version, updated_at) VALUES(1, ?, ?)",
                            (self.SCHEMA_VERSION, _now()),
                        )
                    elif int(row["version"]) > self.SCHEMA_VERSION:
                        raise AccountStoreCorruptError("account store schema is newer than this client")
        except AccountStoreError:
            raise
        except (sqlite3.DatabaseError, OSError) as exc:
            raise AccountStoreCorruptError("account store is unavailable or corrupt") from exc

    def save_device(self, device_id: str, platform: str = "windows", client_version: str | None = None) -> None:
        device_id = str(device_id).strip()
        if not device_id:
            raise ValueError("device_id is required")
        now = _now()
        with closing(self._connect()) as connection, connection:
            existing = connection.execute("SELECT created_at FROM device_identity WHERE singleton=1").fetchone()
            created = str(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO device_identity(singleton, device_id, platform, client_version, created_at, updated_at, revoked_at)
                VALUES(1, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(singleton) DO UPDATE SET device_id=excluded.device_id,
                    platform=excluded.platform, client_version=excluded.client_version,
                    updated_at=excluded.updated_at, revoked_at=NULL
                """,
                (device_id, str(platform), client_version, created, now),
            )

    def get_device(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM device_identity WHERE singleton=1").fetchone()
        return dict(row) if row else None

    def revoke_device(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("UPDATE device_identity SET revoked_at=?, updated_at=? WHERE singleton=1", (_now(), _now()))

    def save_account(self, account_id: str, email: str, email_verified: bool = False) -> None:
        if not str(account_id).strip() or not str(email).strip():
            raise ValueError("account_id and email are required")
        now = _now()
        with closing(self._connect()) as connection, connection:
            existing = connection.execute("SELECT created_at FROM account_identity WHERE singleton=1").fetchone()
            created = str(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO account_identity(singleton, account_id, email, email_verified, created_at, updated_at)
                VALUES(1, ?, ?, ?, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET account_id=excluded.account_id,
                    email=excluded.email, email_verified=excluded.email_verified,
                    updated_at=excluded.updated_at
                """,
                (str(account_id), str(email).strip().lower(), int(bool(email_verified)), created, now),
            )

    def get_account(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM account_identity WHERE singleton=1").fetchone()
        return dict(row) if row else None

    def save_session(self, session_id: str, expires_at: str | None = None) -> None:
        self.set_metadata("active_session", json.dumps({"session_id": str(session_id), "expires_at": expires_at}, ensure_ascii=False))

    def get_session(self) -> dict[str, Any] | None:
        raw = self.get_metadata("active_session")
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) and value.get("session_id") else None

    def clear_session(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM sync_metadata WHERE key=?", ("active_session",))

    def put_mapping(self, mapping: dict[str, Any]) -> None:
        required = ("source_namespace", "source_local_id", "canonical_id", "entity_type", "status")
        if any(not str(mapping.get(key) or "").strip() for key in required):
            raise ValueError("mapping is missing required fields")
        now = _now()
        account_id = mapping.get("account_id")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO entity_mapping(
                    source_namespace, source_local_id, canonical_id, entity_type,
                    account_id, import_id, content_hash, status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_namespace, source_local_id, entity_type, account_id)
                DO UPDATE SET canonical_id=excluded.canonical_id, import_id=excluded.import_id,
                    content_hash=excluded.content_hash, status=excluded.status, updated_at=excluded.updated_at
                """,
                (
                    str(mapping["source_namespace"]), str(mapping["source_local_id"]),
                    str(mapping["canonical_id"]), str(mapping["entity_type"]),
                    str(account_id) if account_id else None, mapping.get("import_id"),
                    mapping.get("content_hash"), str(mapping["status"]), now, now,
                ),
            )

    def get_mapping(self, source_namespace: str, source_local_id: str, entity_type: str, account_id: str | None = None) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM entity_mapping WHERE source_namespace=? AND source_local_id=? AND entity_type=? AND account_id IS ?",
                (str(source_namespace), str(source_local_id), str(entity_type), account_id),
            ).fetchone()
        return dict(row) if row else None

    def enqueue(self, operation: dict[str, Any]) -> None:
        operation_id = str(operation.get("operation_id") or "").strip()
        if not operation_id:
            raise ValueError("operation_id is required")
        now = _now()
        payload_json = json.dumps(operation.get("payload") or {}, ensure_ascii=False, sort_keys=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO account_outbox(
                    operation_id, account_id, device_id, entity_type, entity_id,
                    payload_hash, base_revision, status, retry_count, next_attempt_at,
                    last_error, payload_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, NULL, ?, ?, ?)
                """,
                (
                    operation_id, operation.get("account_id"), operation.get("device_id"),
                    str(operation.get("entity_type") or ""), operation.get("entity_id"),
                    str(operation.get("payload_hash") or ""), operation.get("base_revision"),
                    operation.get("next_attempt_at"), payload_json, now, now,
                ),
            )

    def pending_operations(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM account_outbox WHERE status IN ('pending', 'retry') ORDER BY created_at LIMIT ?",
                (safe_limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json"))
            except (TypeError, ValueError):
                item["payload"] = {}
            result.append(item)
        return result

    def record_outbox_result(self, operation_id: str, *, status: str, error: str | None = None) -> None:
        if status not in {"pending", "retry", "sent", "rejected", "conflict"}:
            raise ValueError("invalid outbox status")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE account_outbox SET status=?, last_error=?, retry_count=retry_count+?, updated_at=? WHERE operation_id=?",
                (status, error, int(status == "retry"), _now(), str(operation_id)),
            )

    def set_metadata(self, key: str, value: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO sync_metadata(key, value, updated_at) VALUES(?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (str(key), str(value), _now()),
            )

    def get_metadata(self, key: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT value FROM sync_metadata WHERE key=?", (str(key),)).fetchone()
        return str(row["value"]) if row else None
