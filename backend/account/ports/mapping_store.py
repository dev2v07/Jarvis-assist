from __future__ import annotations

from typing import Any, Protocol


class MappingStore(Protocol):
    def get(self, source_namespace: str, source_local_id: str) -> dict[str, Any] | None: ...

    def put(self, source_namespace: str, source_local_id: str, mapping: dict[str, Any]) -> None: ...


class InMemoryMappingStore:
    """Non-persistent adapter for Phase 1B tests and previews."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, source_namespace: str, source_local_id: str) -> dict[str, Any] | None:
        value = self._items.get((source_namespace, source_local_id))
        return dict(value) if value is not None else None

    def put(self, source_namespace: str, source_local_id: str, mapping: dict[str, Any]) -> None:
        self._items[(source_namespace, source_local_id)] = dict(mapping)
