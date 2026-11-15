"""UI-independent local foundation for Jarvis Account System.

Phase 1B deliberately contains no cloud transport, authentication or database
migrations.  The package is safe to import without starting the Jarvis runtime.
"""

from .application.account_context import LocalOnlyAccountContextProvider
from .domain.enums import AccountLifecycleState, AccountMode, ConnectionState, SessionState, SyncState
from .domain.models import AccountContext

__all__ = [
    "AccountContext",
    "AccountLifecycleState",
    "AccountMode",
    "ConnectionState",
    "LocalOnlyAccountContextProvider",
    "SessionState",
    "SyncState",
]
