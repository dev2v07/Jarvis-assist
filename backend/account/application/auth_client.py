from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Protocol

import requests


@dataclass(frozen=True)
class AuthError:
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: AuthError | None = None


class AuthProvider(Protocol):
    def register(self, email: str, password: str) -> AuthResult: ...

    def verify_email(self, email: str, code: str) -> AuthResult: ...

    def login(self, email: str, password: str) -> AuthResult: ...

    def refresh_session(self) -> AuthResult: ...

    def logout(self) -> AuthResult: ...

    def request_password_reset(self, email: str) -> AuthResult: ...

    def confirm_password_reset(self, email: str, code: str, password: str) -> AuthResult: ...

    def get_account_profile(self) -> AuthResult: ...

    def list_devices(self) -> AuthResult: ...

    def revoke_device(self, device_id: str) -> AuthResult: ...

    def login_with_google(self, authorization) -> AuthResult: ...


class UnavailableAuthProvider:
    """Explicit no-server provider; never reports a fake success."""

    ERROR = AuthError(
        code="account_server_unavailable",
        message="Сервер аккаунтов пока не подключён. Jarvis продолжает работать локально.",
        retryable=True,
    )

    def _unavailable(self) -> AuthResult:
        return AuthResult(ok=False, error=self.ERROR)

    def register(self, email: str, password: str) -> AuthResult:
        return self._unavailable()

    def verify_email(self, email: str, code: str) -> AuthResult:
        return self._unavailable()

    def login(self, email: str, password: str) -> AuthResult:
        return self._unavailable()

    def refresh_session(self) -> AuthResult:
        return self._unavailable()

    def logout(self) -> AuthResult:
        return AuthResult(ok=True, data={"logged_out": True})

    def request_password_reset(self, email: str) -> AuthResult:
        return self._unavailable()

    def confirm_password_reset(self, email: str, code: str, password: str) -> AuthResult:
        return self._unavailable()

    def get_account_profile(self) -> AuthResult:
        return self._unavailable()

    def list_devices(self) -> AuthResult:
        return self._unavailable()

    def revoke_device(self, device_id: str) -> AuthResult:
        return self._unavailable()

    def login_with_google(self, authorization) -> AuthResult:
        return self._unavailable()


class HttpAuthProvider:
    """HTTP adapter for the local/future Account Server.

    It is opt-in through ``JARVIS_ACCOUNT_API_URL`` and never falls back to a
    fake success. Tokens are delegated to the supplied CredentialStore.
    """

    def __init__(self, base_url: str, credential_store, timeout: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.credential_store = credential_store
        self.timeout = timeout
        self.session = requests.Session()

    @classmethod
    def from_environment(cls, credential_store) -> "HttpAuthProvider | None":
        base_url = os.getenv("JARVIS_ACCOUNT_API_URL", "").strip()
        if not base_url:
            # Account UI can be imported before the legacy backend config
            # module. Read this non-secret client setting without loading
            # server credentials from the rest of dev.env.
            env_path = Path(__file__).resolve().parents[2] / "dev.env"
            try:
                for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if line.startswith("JARVIS_ACCOUNT_API_URL="):
                        base_url = line.split("=", 1)[1].strip().strip("\"'")
                        break
            except (OSError, UnicodeError):
                pass
        return cls(base_url, credential_store) if base_url else None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, *, auth: bool = False) -> AuthResult:
        headers = {"Accept": "application/json"}
        if auth:
            token = self.credential_store.read_access_token()
            if not token:
                return AuthResult(ok=False, error=AuthError("auth_required", "Требуется повторный вход."))
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self.session.request(method, f"{self.base_url}{path}", json=payload, headers=headers, timeout=self.timeout)
            body = response.json() if response.content else {}
        except (requests.RequestException, ValueError) as exc:
            return AuthResult(ok=False, error=AuthError("offline", "Сервер аккаунтов недоступен.", retryable=True, details={"type": type(exc).__name__}))
        if 200 <= response.status_code < 300:
            return AuthResult(ok=True, data=body if isinstance(body, dict) else {})
        detail = body.get("detail", {}) if isinstance(body, dict) else {}
        error = detail.get("error", detail) if isinstance(detail, dict) else {}
        return AuthResult(ok=False, error=AuthError(str(error.get("code", "server_error")), str(error.get("message", "Операция не выполнена.")), response.status_code >= 500, {"status": response.status_code}))

    def register(self, email: str, password: str) -> AuthResult:
        return self._request("POST", "/api/v1/auth/register", {"email": email, "password": password})

    def verify_email(self, email: str, code: str) -> AuthResult:
        del email
        return self._request("POST", "/api/v1/auth/verify-email", {"token": code})

    def login(self, email: str, password: str) -> AuthResult:
        result = self._request("POST", "/api/v1/auth/login", {"email": email, "password": password, "platform": "windows", "device_name": "Jarvis Windows"})
        if result.ok:
            try:
                self.credential_store.write_tokens(result.data["access_token"], result.data["refresh_token"])
            except Exception as exc:
                return AuthResult(ok=False, error=AuthError("credential_store_unavailable", "Не удалось сохранить защищённую сессию.", details={"type": type(exc).__name__}))
        return result

    def refresh_session(self) -> AuthResult:
        refresh = self.credential_store.read_refresh_token()
        if not refresh:
            return AuthResult(ok=False, error=AuthError("auth_required", "Требуется повторный вход."))
        result = self._request("POST", "/api/v1/auth/refresh", {"refresh_token": refresh})
        if result.ok:
            self.credential_store.write_tokens(result.data["access_token"], result.data["refresh_token"])
        return result

    def logout(self) -> AuthResult:
        result = self._request("POST", "/api/v1/auth/logout", auth=True)
        try:
            self.credential_store.clear()
        except Exception:
            if result.ok:
                return AuthResult(ok=False, error=AuthError("credential_store_unavailable", "Не удалось очистить защищённую сессию."))
        return result

    def request_password_reset(self, email: str) -> AuthResult:
        return self._request("POST", "/api/v1/auth/password-reset/request", {"email": email})

    def confirm_password_reset(self, email: str, code: str, password: str) -> AuthResult:
        del email
        return self._request("POST", "/api/v1/auth/password-reset/confirm", {"token": code, "password": password})

    def get_account_profile(self) -> AuthResult:
        return self._request("GET", "/api/v1/account/profile", auth=True)

    def list_devices(self) -> AuthResult:
        return self._request("GET", "/api/v1/account/devices", auth=True)

    def revoke_device(self, device_id: str) -> AuthResult:
        return self._request("POST", f"/api/v1/account/devices/{device_id}/revoke", auth=True)

    def login_with_google(self, authorization) -> AuthResult:
        result = self._request("POST", "/api/v1/auth/google/exchange", {"code": authorization.code, "code_verifier": authorization.code_verifier, "redirect_uri": authorization.redirect_uri, "platform": "windows", "device_name": "Jarvis Windows"})
        if result.ok:
            try:
                self.credential_store.write_tokens(result.data["access_token"], result.data["refresh_token"])
            except Exception as exc:
                return AuthResult(ok=False, error=AuthError("credential_store_unavailable", "Не удалось сохранить защищённую сессию.", details={"type": type(exc).__name__}))
        return result
