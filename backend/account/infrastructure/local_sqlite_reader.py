from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from account.domain.contracts import (
    ExcludedItemDTO,
    LocalAttachmentDTO,
    LocalConversationDTO,
    LocalInventory,
    LocalMessageDTO,
)
from account.domain.enums import DataClass, EntityType, InventoryItemStatus


class LocalDatabaseReadError(RuntimeError):
    """The local database could not be inspected without changing it."""


class ReadOnlySQLiteReader:
    """Read the current Jarvis database through SQLite's `mode=ro` URI.

    This class never imports ChatStore and never executes DDL, DML or a
    persistent-state PRAGMA. Absolute paths are used internally only to check
    selected attachment metadata; they are never returned in DTOs.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path, *, source_namespace: str = "jarvis-local") -> None:
        self.db_path = Path(db_path)
        self.source_namespace = str(source_namespace)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise LocalDatabaseReadError(f"local database does not exist: {self.db_path.name}")
        uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            return connection
        except (sqlite3.DatabaseError, OSError) as exc:
            raise LocalDatabaseReadError("local database is unavailable or corrupt") from exc

    @staticmethod
    def _rows(connection: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        try:
            return connection.execute(query, tuple(params)).fetchall()
        except sqlite3.DatabaseError as exc:
            raise LocalDatabaseReadError("local database query failed") from exc

    def _table_names(self, connection: sqlite3.Connection) -> set[str]:
        rows = self._rows(
            connection,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        )
        return {str(row["name"]) for row in rows}

    def list_conversations(self) -> tuple[LocalConversationDTO, ...]:
        with closing(self._connect()) as connection:
            tables = self._table_names(connection)
            if "chat_sessions" not in tables:
                raise LocalDatabaseReadError("chat_sessions table is missing")
            rows = self._rows(connection, "SELECT * FROM chat_sessions ORDER BY created_at, id")
        return tuple(
            LocalConversationDTO(
                source_local_id=str(row["id"]),
                title=str(row["title"] or "Новый чат"),
                archived=bool(row["archived"]) if "archived" in row.keys() else False,
                favorite=None,
                created_at=str(row["created_at"]) if row["created_at"] is not None else None,
                updated_at=str(row["updated_at"]) if row["updated_at"] is not None else None,
                source_namespace=self.source_namespace,
            )
            for row in rows
        )

    def list_messages(self, conversation_id: str | None = None) -> tuple[LocalMessageDTO, ...]:
        with closing(self._connect()) as connection:
            tables = self._table_names(connection)
            if "chat_messages" not in tables:
                raise LocalDatabaseReadError("chat_messages table is missing")
            query = "SELECT * FROM chat_messages"
            params: tuple[Any, ...] = ()
            if conversation_id is not None:
                query += " WHERE chat_id=?"
                params = (str(conversation_id),)
            query += " ORDER BY created_at, rowid"
            rows = self._rows(connection, query, params)
            sessions = {
                str(row["id"])
                for row in self._rows(connection, "SELECT id FROM chat_sessions")
            } if "chat_sessions" in tables else set()
        result: list[LocalMessageDTO] = []
        for row in rows:
            chat_id = str(row["chat_id"] or "default")
            orphan = chat_id not in sessions
            result.append(
                LocalMessageDTO(
                    source_local_id=str(row["id"]),
                    source_conversation_id=chat_id,
                    client_message_id=str(row["id"]),
                    role=str(row["role"]),
                    content=str(row["content"] or ""),
                    reply_to=str(row["reply_to"]) if row["reply_to"] is not None else None,
                    created_at=str(row["created_at"]) if row["created_at"] is not None else None,
                    source_namespace=self.source_namespace,
                    data_class=DataClass.EXCLUDED if orphan else DataClass.CLOUD_SYNCED,
                )
            )
        return tuple(result)

    def list_attachments(
        self,
        message_id: str | None = None,
        *,
        compute_hashes: bool = False,
    ) -> tuple[LocalAttachmentDTO, ...]:
        with closing(self._connect()) as connection:
            tables = self._table_names(connection)
            if "chat_attachments" not in tables:
                return ()
            query = "SELECT * FROM chat_attachments"
            params: tuple[Any, ...] = ()
            if message_id is not None:
                query += " WHERE message_id=?"
                params = (str(message_id),)
            query += " ORDER BY created_at, attachment_id"
            rows = self._rows(connection, query, params)
            message_ids = {
                str(row["id"])
                for row in self._rows(connection, "SELECT id FROM chat_messages")
            } if "chat_messages" in tables else set()
        return tuple(self._attachment(row, message_ids, compute_hashes) for row in rows)

    def _attachment(
        self,
        row: sqlite3.Row,
        message_ids: set[str],
        compute_hashes: bool,
    ) -> LocalAttachmentDTO:
        attachment_id = str(row["attachment_id"])
        message_id = str(row["message_id"])
        size = int(row["size"] or 0)
        path_value = str(row["stored_path"] or "")
        path = Path(path_value)
        status = InventoryItemStatus.AVAILABLE
        sha256: str | None = None
        reason: str | None = None
        if message_id not in message_ids:
            status = InventoryItemStatus.ORPHAN
            reason = "attachment references a missing message"
        elif not path.is_file():
            status = InventoryItemStatus.MISSING
            reason = "attachment file is missing"
        else:
            try:
                if path.stat().st_size != size:
                    status = InventoryItemStatus.CORRUPT
                    reason = "stored size differs from attachment metadata"
                if compute_hashes:
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    sha256 = digest.hexdigest()
            except (OSError, ValueError) as exc:
                status = InventoryItemStatus.CORRUPT
                reason = f"attachment could not be read: {type(exc).__name__}"
        return LocalAttachmentDTO(
            source_local_id=attachment_id,
            source_message_id=message_id,
            original_name=str(row["original_name"] or attachment_id),
            media_type=str(row["media_type"] or "application/octet-stream"),
            size=size,
            sha256=sha256,
            status=status,
            unsupported_reason=reason,
        )

    def list_reactions(self, message_id: str | None = None) -> tuple[dict[str, Any], ...]:
        with closing(self._connect()) as connection:
            if "chat_reactions" not in self._table_names(connection):
                return ()
            query = "SELECT message_id, reaction, actor, created_at FROM chat_reactions"
            params: tuple[Any, ...] = ()
            if message_id is not None:
                query += " WHERE message_id=?"
                params = (str(message_id),)
            query += " ORDER BY created_at, message_id, reaction"
            return tuple(dict(row) for row in self._rows(connection, query, params))

    def list_pins(self) -> tuple[dict[str, Any], ...]:
        with closing(self._connect()) as connection:
            if "chat_pins" not in self._table_names(connection):
                return ()
            return tuple(
                dict(row)
                for row in self._rows(
                    connection,
                    "SELECT message_id, actor, created_at FROM chat_pins ORDER BY created_at, message_id",
                )
            )

    def get_excluded_items(self) -> tuple[ExcludedItemDTO, ...]:
        return (
            ExcludedItemDTO(EntityType.REQUEST, "requests", "execution history is not conversation history"),
            ExcludedItemDTO(EntityType.MEMORY, "backend/data/facts/facts.json", "personal memory needs separate consent and preview"),
            ExcludedItemDTO(EntityType.KNOWLEDGE, "data/offline_knowledge and shared libraries", "shared Knowledge Library is not account data"),
            ExcludedItemDTO(EntityType.KNOWLEDGE, "data/filesystem_index.db", "filesystem index is excluded"),
            ExcludedItemDTO(EntityType.KNOWLEDGE, "local models and voice/WAV cache", "device-only runtime data"),
        )

    def get_inventory(self, *, compute_attachment_hashes: bool = False) -> LocalInventory:
        try:
            conversations = self.list_conversations()
            messages = self.list_messages()
            attachments = self.list_attachments(compute_hashes=compute_attachment_hashes)
            reactions = self.list_reactions()
            pins = self.list_pins()
        except LocalDatabaseReadError:
            raise
        errors = tuple(
            f"attachment {item.source_local_id}: {item.unsupported_reason}"
            for item in attachments
            if item.status is not InventoryItemStatus.AVAILABLE
            and item.unsupported_reason
        )
        return LocalInventory(
            schema_version=self.SCHEMA_VERSION,
            source_namespace=self.source_namespace,
            conversations=conversations,
            messages=messages,
            attachments=attachments,
            reactions_count=len(reactions),
            pins_count=len(pins),
            archive_count=sum(item.archived for item in conversations),
            excluded_items=self.get_excluded_items(),
            errors=errors,
        )
