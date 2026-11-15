from __future__ import annotations

from typing import Protocol


class CredentialStore(Protocol):
    """Future OS-protected credential boundary; no token storage in Phase 1B."""

    def read_access_token(self) -> str | None: ...

    def write_refresh_token(self, token: str) -> None: ...

    def clear(self) -> None: ...
