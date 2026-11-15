"""Canonical local storage contract for Jarvis.

This module describes storage ownership without forcing unrelated databases into
one file.  Application services can depend on this registry while local and
cloud adapters continue to implement their own bounded contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoragePaths:
    """Explicit paths for the currently supported local stores."""

    backend_root: Path
    chat_state: Path
    request_history: Path
    account_state: Path
    filesystem_index: Path

    @classmethod
    def from_backend_root(cls, backend_root: str | Path) -> "StoragePaths":
        root = Path(backend_root).resolve()
        return cls(
            backend_root=root,
            chat_state=root / "data" / "jarvis_state.sqlite3",
            request_history=root / "data" / "jarvis.sqlite3",
            account_state=root / "data" / "account_system" / "account_state.sqlite3",
            filesystem_index=root.parent / "data" / "filesystem_index.db",
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "chat_state": str(self.chat_state),
            "request_history": str(self.request_history),
            "account_state": str(self.account_state),
            "filesystem_index": str(self.filesystem_index),
        }

    def existing(self) -> dict[str, Path]:
        return {name: path for name, path in self.as_paths().items() if path.is_file()}

    def as_paths(self) -> dict[str, Path]:
        return {
            "chat_state": self.chat_state,
            "request_history": self.request_history,
            "account_state": self.account_state,
            "filesystem_index": self.filesystem_index,
        }


def storage_paths_for_backend(backend_root: str | Path) -> StoragePaths:
    """Return the canonical registry for a backend checkout or test fixture."""

    return StoragePaths.from_backend_root(backend_root)
