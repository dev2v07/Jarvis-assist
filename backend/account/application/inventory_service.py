from __future__ import annotations

from account.application.local_data_adapter import LocalDataAdapter
from account.domain.contracts import LocalInventory


class InventoryService:
    def __init__(self, adapter: LocalDataAdapter) -> None:
        self.adapter = adapter

    def get_inventory(self, *, compute_attachment_hashes: bool = False) -> LocalInventory:
        return self.adapter.get_inventory(compute_attachment_hashes=compute_attachment_hashes)
