from __future__ import annotations

from account.application.account_context import AccountContextProvider
from account.domain.models import AccountContext


class ModeCoordinator:
    """Read-only facade for consumers that need current mode/policy context."""

    def __init__(self, provider: AccountContextProvider) -> None:
        self.provider = provider

    def snapshot(self) -> AccountContext:
        return self.provider.get_context()

    def local_runtime_allowed(self) -> bool:
        return self.snapshot().local_data_available

    def cloud_sync_allowed(self) -> bool:
        context = self.snapshot()
        return context.mode.value == "account" and bool(context.account.account_id)
