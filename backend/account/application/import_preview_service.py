from __future__ import annotations

from account.application.canonical_mapper import CanonicalMapper
from account.application.inventory_service import InventoryService
from account.domain.contracts import ImportPreviewDTO
from account.domain.enums import DataClass, InventoryItemStatus
from account.domain.ids import new_uuid7


class ImportPreviewService:
    def __init__(self, inventory_service: InventoryService, mapper: CanonicalMapper | None = None) -> None:
        self.inventory_service = inventory_service
        self.mapper = mapper or CanonicalMapper()

    def preview(self, *, compute_attachment_hashes: bool = False, import_id: str | None = None) -> ImportPreviewDTO:
        inventory = self.inventory_service.get_inventory(compute_attachment_hashes=compute_attachment_hashes)
        manifest = self.mapper.create_manifest(inventory, import_id=import_id or new_uuid7())
        cloud_synced = tuple(
            [item.source_local_id for item in inventory.conversations]
            + [item.source_local_id for item in inventory.messages if item.data_class is DataClass.CLOUD_SYNCED]
            + [item.source_local_id for item in inventory.attachments if item.status is InventoryItemStatus.AVAILABLE]
        )
        device_only = ("local models", "voice models and WAV cache", "local provider keys", "local runtime files")
        excluded = tuple(f"{item.entity_type.value}:{item.source}" for item in inventory.excluded_items)
        return ImportPreviewDTO(
            schema_version=1,
            import_id=manifest.import_id,
            source_namespace=inventory.source_namespace,
            inventory=inventory,
            manifest=manifest,
            cloud_synced=cloud_synced,
            device_only=device_only,
            excluded=excluded,
        )
