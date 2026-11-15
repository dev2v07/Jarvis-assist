from __future__ import annotations

from typing import Protocol

from account.domain.models import AccountIdentity, DeviceIdentity, SessionStateModel


class IdentityStore(Protocol):
    def get_account(self) -> AccountIdentity: ...

    def get_device(self) -> DeviceIdentity: ...

    def get_session(self) -> SessionStateModel: ...


class InMemoryIdentityStore:
    """Test-only identity store; no persistent account identity is invented."""

    def __init__(
        self,
        account: AccountIdentity | None = None,
        device: DeviceIdentity | None = None,
        session: SessionStateModel | None = None,
    ) -> None:
        self._account = account or AccountIdentity()
        self._device = device or DeviceIdentity()
        self._session = session or SessionStateModel()

    def get_account(self) -> AccountIdentity:
        return self._account

    def get_device(self) -> DeviceIdentity:
        return self._device

    def get_session(self) -> SessionStateModel:
        return self._session
