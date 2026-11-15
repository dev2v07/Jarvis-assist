from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .enums import DataClass, EntityType, InventoryItemStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class LocalConversationDTO:
    source_local_id: str
    title: str
    archived: bool
    favorite: bool | None
    created_at: str | None
    updated_at: str | None
    source_namespace: str
    data_class: DataClass = DataClass.CLOUD_SYNCED


@dataclass(frozen=True)
class LocalMessageDTO:
    source_local_id: str
    source_conversation_id: str
    client_message_id: str
    role: str
    content: str
    reply_to: str | None
    created_at: str | None
    source_namespace: str
    data_class: DataClass = DataClass.CLOUD_SYNCED


@dataclass(frozen=True)
class LocalAttachmentDTO:
    source_local_id: str
    source_message_id: str
    original_name: str
    media_type: str
    size: int
    sha256: str | None
    status: InventoryItemStatus
    data_class: DataClass = DataClass.CLOUD_SYNCED
    unsupported_reason: str | None = None


@dataclass(frozen=True)
class ExcludedItemDTO:
    entity_type: EntityType
    source: str
    reason: str
    data_class: DataClass = DataClass.EXCLUDED


@dataclass(frozen=True)
class LocalInventory:
    schema_version: int
    source_namespace: str
    conversations: tuple[LocalConversationDTO, ...]
    messages: tuple[LocalMessageDTO, ...]
    attachments: tuple[LocalAttachmentDTO, ...]
    reactions_count: int
    pins_count: int
    archive_count: int
    excluded_items: tuple[ExcludedItemDTO, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def conversation_count(self) -> int:
        return len(self.conversations)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def attachment_count(self) -> int:
        return len(self.attachments)

    @property
    def orphan_message_count(self) -> int:
        return sum(message.data_class == DataClass.EXCLUDED for message in self.messages)


@dataclass(frozen=True)
class ManifestItemDTO:
    schema_version: int
    import_id: str
    source_namespace: str
    source_local_id: str
    entity_type: EntityType
    content_hash: str | None
    source_created_at: str | None
    source_updated_at: str | None
    status: InventoryItemStatus
    unsupported_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportManifestDTO:
    schema_version: int
    import_id: str
    source_namespace: str
    created_at: str
    items: tuple[ManifestItemDTO, ...]


@dataclass(frozen=True)
class ImportPreviewDTO:
    schema_version: int
    import_id: str
    source_namespace: str
    inventory: LocalInventory
    manifest: ImportManifestDTO
    cloud_synced: tuple[str, ...]
    device_only: tuple[str, ...]
    excluded: tuple[str, ...]
    cancelled: bool = False

