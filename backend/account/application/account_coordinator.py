from __future__ import annotations

from pathlib import Path

from account.application.account_context import AccountContextService, LocalOnlyAccountContextProvider
from account.application.auth_client import AuthError, AuthProvider, HttpAuthProvider, UnavailableAuthProvider, AuthResult
from account.application.google_oauth import GoogleLoopbackOAuthClient, GoogleOAuthConfig, GoogleOAuthError
from account.domain.models import AccountContext, AccountIdentity, DeviceIdentity, SessionStateModel
from account.domain.enums import SessionState
from account.infrastructure.persistent_store import PersistentAccountStore
from account.infrastructure.dpapi_credentials import CredentialStoreError, WindowsDPAPICredentialStore
from account.domain.ids import new_uuid7


class AccountCoordinator:
    """Application boundary joining local state, auth provider and storage."""

    def __init__(
        self,
        store: PersistentAccountStore,
        auth_provider: AuthProvider | None = None,
        credential_store: WindowsDPAPICredentialStore | None = None,
    ) -> None:
        self.store = store
        self.auth_provider = auth_provider or UnavailableAuthProvider()
        self.credential_store = credential_store
        google_config = GoogleOAuthConfig.from_environment()
        self.google_oauth = GoogleLoopbackOAuthClient(google_config) if google_config else None
        self.context_service = AccountContextService(LocalOnlyAccountContextProvider().get_context())

    @classmethod
    def local_default(cls, root: str | Path) -> "AccountCoordinator":
        base = Path(root)
        store = PersistentAccountStore(base / "account_state.sqlite3")
        # Device identity is local metadata, not an account identity. It is
        # created once and remains stable across restarts; no network call or
        # fake account is involved.
        if store.get_device() is None:
            store.save_device(new_uuid7(), "windows", None)
        credentials = WindowsDPAPICredentialStore(base / "credentials.dpapi")
        http_provider = HttpAuthProvider.from_environment(credentials)
        coordinator = cls(store, http_provider or UnavailableAuthProvider(), credentials)
        account = store.get_account()
        device = store.get_device()
        session = store.get_session()
        try:
            if account and device and session and credentials.read_access_token() and not device.get("revoked_at"):
                coordinator.context_service.mark_authenticated_device(
                    AccountIdentity(account_id=account.get("account_id"), email=account.get("email"), email_verified=bool(account.get("email_verified"))),
                    DeviceIdentity(device_id=device.get("device_id"), platform=device.get("platform", "windows"), client_version=device.get("client_version")),
                    SessionStateModel(state=SessionState.AUTHENTICATED, session_id=session.get("session_id"), expires_at=session.get("expires_at")),
                )
        except (CredentialStoreError, ValueError, TypeError):
            # Corrupt/expired local session metadata must never block Local Mode.
            coordinator.context_service.return_to_local()
        return coordinator

    def context(self) -> AccountContext:
        return self.context_service.get_context()

    def accept_auth_result(self, result: AuthResult) -> AccountContext:
        """Promote context only from a real provider response."""
        if not result.ok:
            return self.context()
        account = result.data.get("account") or {}
        device = result.data.get("device") or {}
        session = result.data.get("session") or {}
        account_id = account.get("id")
        device_id = device.get("id")
        session_id = session.get("id")
        if not account_id or not device_id or not session_id:
            raise ValueError("auth response does not contain verified account, device and session identities")
        self.store.save_account(account_id, account.get("email", ""), bool(account.get("email_verified")))
        self.store.save_device(device_id, device.get("platform", "windows"), None)
        self.store.save_session(session_id, session.get("expires_at"))
        return self.context_service.mark_authenticated_device(
            AccountIdentity(account_id=account_id, email=account.get("email"), email_verified=bool(account.get("email_verified"))),
            DeviceIdentity(device_id=device_id, platform=device.get("platform", "windows")),
            SessionStateModel(state=SessionState.AUTHENTICATED, session_id=session_id, expires_at=session.get("expires_at")),
        )

    def login_with_google(self) -> AuthResult:
        if not self.google_oauth or not isinstance(self.auth_provider, HttpAuthProvider):
            return AuthResult(ok=False, error=AuthError("google_not_configured", "Вход через Google пока не настроен."))
        try:
            result = self.auth_provider.login_with_google(self.google_oauth.authenticate())
        except GoogleOAuthError as error:
            return AuthResult(ok=False, error=AuthError("google_oauth_error", str(error), retryable=True, details={"type": type(error).__name__}))
        if result.ok:
            self.accept_auth_result(result)
        return result

    def logout_local(self) -> AccountContext:
        if self.credential_store:
            try:
                self.credential_store.clear()
            except CredentialStoreError:
                # Local Mode must remain usable even when the OS credential
                # vault is unavailable. The caller can surface the issue when
                # a real authenticated session exists; no local history is
                # touched here.
                pass
        self.store.clear_session()
        return self.context_service.return_to_local()
