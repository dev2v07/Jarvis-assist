from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from account.domain.enums import AccountLifecycleState, AccountMode, ConnectionState, SessionState, SyncState
from account.domain.models import AccountContext, AccountIdentity, DeviceIdentity, SessionStateModel
from account.ports.identity_store import IdentityStore, InMemoryIdentityStore


class AccountContextProvider(Protocol):
    def get_context(self) -> AccountContext: ...


class LocalOnlyAccountContextProvider:
    """Safe default provider used by current Jarvis Local Mode."""

    def __init__(self, identity_store: IdentityStore | None = None) -> None:
        self.identity_store = identity_store or InMemoryIdentityStore()

    def get_context(self) -> AccountContext:
        return AccountContext(
            lifecycle=AccountLifecycleState.LOCAL_ONLY,
            mode=AccountMode.LOCAL_ONLY,
            connection=ConnectionState.LOCAL,
            account=self.identity_store.get_account(),
            device=self.identity_store.get_device(),
            session=self.identity_store.get_session(),
            permissions=frozenset(),
            sync_state=SyncState.NOT_CONFIGURED,
            local_data_available=True,
        )


class AccountContextService:
    """Small state machine; cloud transitions require real supplied identity."""

    def __init__(self, initial: AccountContext | None = None) -> None:
        self._context = initial or AccountContext()

    def get_context(self) -> AccountContext:
        return self._context

    def begin_connecting(self) -> AccountContext:
        if self._context.lifecycle not in {
            AccountLifecycleState.LOCAL_ONLY,
            AccountLifecycleState.AUTH_REQUIRED,
            AccountLifecycleState.OFFLINE_ACCOUNT,
        }:
            raise ValueError("context cannot begin connecting from its current state")
        self._context = replace(
            self._context,
            lifecycle=AccountLifecycleState.CONNECTING,
            mode=AccountMode.ACCOUNT,
            connection=ConnectionState.CONNECTING,
        )
        return self._context

    def mark_authenticated_device(
        self,
        account: AccountIdentity,
        device: DeviceIdentity,
        session: SessionStateModel,
    ) -> AccountContext:
        if not account.account_id or not device.device_id or session.state is not SessionState.AUTHENTICATED:
            raise ValueError("real account, device and authenticated session are required")
        self._context = replace(
            self._context,
            lifecycle=AccountLifecycleState.AUTHENTICATED_DEVICE,
            mode=AccountMode.ACCOUNT,
            connection=ConnectionState.ONLINE,
            account=account,
            device=device,
            session=session,
            sync_state=SyncState.IDLE,
        )
        return self._context

    def mark_syncing(self) -> AccountContext:
        self._require_account()
        self._context = replace(self._context, lifecycle=AccountLifecycleState.ACCOUNT_SYNCING, sync_state=SyncState.SYNCING)
        return self._context

    def mark_online(self) -> AccountContext:
        self._require_account()
        self._context = replace(self._context, lifecycle=AccountLifecycleState.ACCOUNT_ONLINE, connection=ConnectionState.ONLINE, sync_state=SyncState.IDLE)
        return self._context

    def mark_offline(self) -> AccountContext:
        self._require_account()
        self._context = replace(self._context, lifecycle=AccountLifecycleState.OFFLINE_ACCOUNT, connection=ConnectionState.OFFLINE)
        return self._context

    def require_authentication(self) -> AccountContext:
        self._context = replace(
            self._context,
            lifecycle=AccountLifecycleState.AUTH_REQUIRED,
            mode=AccountMode.ACCOUNT,
            connection=ConnectionState.OFFLINE,
            session=SessionStateModel(state=SessionState.REQUIRED),
            sync_state=SyncState.ERROR,
        )
        return self._context

    def return_to_local(self) -> AccountContext:
        self._context = AccountContext()
        return self._context

    def _require_account(self) -> None:
        if self._context.mode is not AccountMode.ACCOUNT or not self._context.account.account_id:
            raise ValueError("an authenticated account context is required")
