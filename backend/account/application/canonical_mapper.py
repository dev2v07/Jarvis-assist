from __future__ import annotations

import hashlib
import json
from typing import Iterable

from account.domain.contracts import ImportManifestDTO, LocalInventory, ManifestItemDTO, utc_now
from account.domain.enums import EntityType, InventoryItemStatus
from account.domain.ids import new_uuid7


def _hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class CanonicalMapper:
    """Map local identity to import provenance without inventing cloud IDs."""

    SCHEMA_VERSION = 1

    def create_manifest(self, inventory: LocalInventory, *, import_id: str | None = None) -> ImportManifestDTO:
        job_id = str(import_id or new_uuid7()).lower()
        items: list[ManifestItemDTO] = []
        for conversation in inventory.conversations:
            items.append(ManifestItemDTO(
                schema_version=self.SCHEMA_VERSION,
                import_id=job_id,
                source_namespace=inventory.source_namespace,
                source_local_id=conversation.source_local_id,
                entity_type=EntityType.CONVERSATION,
                content_hash=_hash({"title": conversation.title, "archived": conversation.archived, "created_at": conversation.created_at}),
                source_created_at=conversation.created_at,
                source_updated_at=conversation.updated_at,
                status=InventoryItemStatus.AVAILABLE,
                metadata={"archived": conversation.archived, "favorite": conversation.favorite},
            ))
        conversation_ids = {item.source_local_id for item in inventory.conversations}
        for message in inventory.messages:
            orphan = message.source_conversation_id not in conversation_ids
            items.append(ManifestItemDTO(
                schema_version=self.SCHEMA_VERSION,
                import_id=job_id,
                source_namespace=inventory.source_namespace,
                source_local_id=message.source_local_id,
                entity_type=EntityType.MESSAGE,
                content_hash=_hash({"conversation": message.source_conversation_id, "role": message.role, "content": message.content, "reply_to": message.reply_to}),
                source_created_at=message.created_at,
                source_updated_at=None,
                status=InventoryItemStatus.ORPHAN if orphan else InventoryItemStatus.AVAILABLE,
                unsupported_reason="conversation mapping is missing" if orphan else None,
                metadata={"client_message_id": message.client_message_id, "source_conversation_id": message.source_conversation_id},
            ))
        for attachment in inventory.attachments:
            items.append(ManifestItemDTO(
                schema_version=self.SCHEMA_VERSION,
                import_id=job_id,
                source_namespace=inventory.source_namespace,
                source_local_id=attachment.source_local_id,
                entity_type=EntityType.ATTACHMENT,
                content_hash=attachment.sha256,
                source_created_at=None,
                source_updated_at=None,
                status=attachment.status,
                unsupported_reason=attachment.unsupported_reason,
                metadata={"message_id": attachment.source_message_id, "name": attachment.original_name, "media_type": attachment.media_type, "size": attachment.size},
            ))
        for index, kind in enumerate((EntityType.REACTION, EntityType.PIN)):
            count = inventory.reactions_count if kind is EntityType.REACTION else inventory.pins_count
            for item_index in range(count):
                items.append(ManifestItemDTO(
                    schema_version=self.SCHEMA_VERSION,
                    import_id=job_id,
                    source_namespace=inventory.source_namespace,
                    source_local_id=f"{kind.value}:{item_index}",
                    entity_type=kind,
                    content_hash=None,
                    source_created_at=None,
                    source_updated_at=None,
                    status=InventoryItemStatus.UNSUPPORTED,
                    unsupported_reason="canonical reaction/pin contract is not approved",
                ))
        return ImportManifestDTO(
            schema_version=self.SCHEMA_VERSION,
            import_id=job_id,
            source_namespace=inventory.source_namespace,
            created_at=utc_now(),
            items=tuple(items),
        )
