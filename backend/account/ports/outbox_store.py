from __future__ import annotations

from typing import Any, Protocol


class OutboxStore(Protocol):
    def enqueue(self, operation: dict[str, Any]) -> None: ...

    def pending(self) -> list[dict[str, Any]]: ...

    def record_result(self, operation_id: str, result: dict[str, Any]) -> None: ...


class InMemoryOutboxStore:
    """Interface proof only; deliberately not durable or encrypted."""

    def __init__(self) -> None:
        self._pending: dict[str, dict[str, Any]] = {}
        self._results: dict[str, dict[str, Any]] = {}

    def enqueue(self, operation: dict[str, Any]) -> None:
        operation_id = str(operation.get("operation_id") or "")
        if not operation_id:
            raise ValueError("operation_id is required")
        self._pending.setdefault(operation_id, dict(operation))

    def pending(self) -> list[dict[str, Any]]:
        return [dict(value) for value in self._pending.values()]

    def record_result(self, operation_id: str, result: dict[str, Any]) -> None:
        self._results[str(operation_id)] = dict(result)
        self._pending.pop(str(operation_id), None)
