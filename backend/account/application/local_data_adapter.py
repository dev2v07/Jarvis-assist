from __future__ import annotations

from pathlib import Path

from account.domain.contracts import LocalAttachmentDTO, LocalConversationDTO, LocalInventory, LocalMessageDTO
from account.infrastructure.local_sqlite_reader import ReadOnlySQLiteReader


class LocalDataAdapter:
    """Application boundary around the non-mutating SQLite reader."""

    def __init__(self, db_path: str | Path, *, source_namespace: str = "jarvis-local") -> None:
        self.reader = ReadOnlySQLiteReader(db_path, source_namespace=source_namespace)

    def get_inventory(self, *, compute_attachment_hashes: bool = False) -> LocalInventory:
        return self.reader.get_inventory(compute_attachment_hashes=compute_attachment_hashes)

    def list_conversations(self) -> tuple[LocalConversationDTO, ...]:
        return self.reader.list_conversations()

    def list_messages(self, conversation_id: str | None = None) -> tuple[LocalMessageDTO, ...]:
        return self.reader.list_messages(conversation_id)

    def list_attachments(self, message_id: str | None = None, *, compute_hashes: bool = False) -> tuple[LocalAttachmentDTO, ...]:
        return self.reader.list_attachments(message_id, compute_hashes=compute_hashes)

    def list_reactions(self, message_id: str | None = None) -> tuple[dict, ...]:
        return self.reader.list_reactions(message_id)

    def list_pins(self) -> tuple[dict, ...]:
        return self.reader.list_pins()

    def get_excluded_items(self):
        return self.reader.get_excluded_items()
