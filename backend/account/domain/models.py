from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import AccountLifecycleState, AccountMode, ConnectionState, SessionState, SyncState


@dataclass(frozen=True)
class AccountIdentity:
    """An account identity only becomes populated after real authentication."""

    account_id: str | None = None
    email: str | None = None
    email_verified: bool = False


@dataclass(frozen=True)
class DeviceIdentity:
    """A registered device identity; Phase 1B does not persist one."""

    device_id: str | None = None
    platform: str = "windows"
    client_version: str | None = None


@dataclass(frozen=True)
class SessionStateModel:
    state: SessionState = SessionState.LOCAL
    session_id: str | None = None
    expires_at: str | None = None


@dataclass(frozen=True)
class AccountContext:
    lifecycle: AccountLifecycleState = AccountLifecycleState.LOCAL_ONLY
    mode: AccountMode = AccountMode.LOCAL_ONLY
    connection: ConnectionState = ConnectionState.LOCAL
    account: AccountIdentity = field(default_factory=AccountIdentity)
    device: DeviceIdentity = field(default_factory=DeviceIdentity)
    session: SessionStateModel = field(default_factory=SessionStateModel)
    permissions: frozenset[str] = field(default_factory=frozenset)
    sync_state: SyncState = SyncState.NOT_CONFIGURED
    local_data_available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_local_only(self) -> bool:
        return self.mode is AccountMode.LOCAL_ONLY

    def to_dict(self) -> dict[str, Any]:
        return {
            "lifecycle": self.lifecycle.value,
            "mode": self.mode.value,
            "connection": self.connection.value,
            "account_id": self.account.account_id,
            "email": self.account.email,
            "email_verified": self.account.email_verified,
            "device_id": self.device.device_id,
            "platform": self.device.platform,
            "session_state": self.session.state.value,
            "session_id": self.session.session_id,
            "permissions": sorted(self.permissions),
            "sync_state": self.sync_state.value,
            "local_data_available": self.local_data_available,
            "metadata": dict(self.metadata),
        }
