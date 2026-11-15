from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import requests

from .config import Settings
from .email_provider import EmailProvider
from .ids import new_secret, new_uuid7
from .google_identity import GoogleIdentityError, GoogleIdentityValidator, VerifiedGoogleIdentity
from .models import Account, Device, EmailVerificationToken, ExternalIdentity, PasswordResetToken, SecurityEvent, Session as DbSession, utcnow
from .security import expires_after, hash_password, normalize_email, token_digest, validate_password, verify_password


class AuthServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SessionTokens:
    account: Account
    device: Device
    session: DbSession
    access_token: str
    refresh_token: str


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class AuthService:
    def __init__(self, settings: Settings, email_provider: EmailProvider, google_validator: GoogleIdentityValidator | None = None) -> None:
        self.settings = settings
        self.email_provider = email_provider
        self.google_validator = google_validator or (GoogleIdentityValidator(settings.google_client_id) if settings.google_client_id else None)

    def _event(self, db: Session, event_type: str, account_id: str | None = None, metadata: dict | None = None) -> None:
        db.add(SecurityEvent(id=new_uuid7(), account_id=account_id, event_type=event_type, safe_metadata=json.dumps(metadata or {}, sort_keys=True)))

    def register(self, db: Session, email: str, password: str) -> None:
        normalized = normalize_email(email)
        if "@" not in normalized or len(normalized) > 320:
            raise AuthServiceError("invalid_request", "Введите корректный email.")
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            raise AuthServiceError("invalid_request", str(exc)) from exc
        existing = db.scalar(select(Account).where(Account.email_normalized == normalized))
        if existing:
            # Generic response behavior prevents account enumeration.
            return
        account = Account(id=new_uuid7(), email=email.strip(), email_normalized=normalized, password_hash=password_hash, status="pending")
        db.add(account)
        token = new_secret()
        db.add(EmailVerificationToken(id=new_uuid7(), account_id=account.id, token_hash=token_digest(token), expires_at=expires_after(self.settings.verification_ttl_seconds)))
        self._event(db, "registration_requested", account.id)
        try:
            db.flush()
            self.email_provider.send_verification(account.email, token)
        except Exception as exc:
            db.rollback()
            raise AuthServiceError("email_delivery_failed", "Не удалось передать письмо локальному SMTP.", 503) from exc
        db.commit()

    def verify_email(self, db: Session, token: str) -> Account:
        item = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_digest(token)))
        if not item or item.consumed_at or item.expires_at <= utcnow():
            raise AuthServiceError("invalid_token", "Токен подтверждения недействителен или истёк.")
        account = db.get(Account, item.account_id)
        if not account:
            raise AuthServiceError("invalid_token", "Токен подтверждения недействителен.")
        item.consumed_at = utcnow()
        account.email_verified_at = utcnow()
        account.status = "active"
        self._event(db, "email_verified", account.id)
        db.commit()
        return account

    def _get_or_create_device(self, db: Session, account: Account, request) -> Device:
        device = db.get(Device, request.device_id) if request.device_id else None
        if device and (device.account_id != account.id or device.revoked_at):
            raise AuthServiceError("device_revoked", "Устройство отозвано или не принадлежит аккаунту.", 403)
        if device:
            device.last_seen_at = utcnow()
            return device
        device = Device(id=new_uuid7(), account_id=account.id, device_name=request.device_name[:120], platform=request.platform[:32], client_version=request.client_version)
        db.add(device)
        return device

    def _issue_session(self, db: Session, account: Account, request, event_type: str) -> SessionTokens:
        device = self._get_or_create_device(db, account, request)
        access = new_secret()
        refresh = new_secret()
        session = DbSession(id=new_uuid7(), account_id=account.id, device_id=device.id, access_token_hash=token_digest(access), refresh_token_hash=token_digest(refresh), token_family_id=new_uuid7(), expires_at=expires_after(self.settings.refresh_ttl_seconds), access_expires_at=expires_after(self.settings.access_ttl_seconds))
        account.last_login_at = utcnow()
        self._event(db, event_type, account.id, {"device_id": device.id})
        db.add(session)
        db.commit()
        return SessionTokens(account, device, session, access, refresh)

    def login(self, db: Session, request) -> SessionTokens:
        account = db.scalar(select(Account).where(Account.email_normalized == normalize_email(request.email)))
        if not account or not verify_password(account.password_hash, request.password):
            self._event(db, "login_failed")
            db.commit()
            raise AuthServiceError("invalid_credentials", "Неверный email или пароль.", 401)
        if account.status != "active" or not account.email_verified_at:
            raise AuthServiceError("email_unverified", "Сначала подтвердите email.", 403)
        return self._issue_session(db, account, request, "login_succeeded")

    def google_login(self, db: Session, raw_id_token: str, request) -> SessionTokens:
        if not self.settings.google_auth_enabled or not self.google_validator:
            raise AuthServiceError("provider_disabled", "Вход через Google пока не подключён.", 503)
        try:
            identity = self.google_validator.validate(raw_id_token)
        except GoogleIdentityError as exc:
            self._event(db, "google_login_failed")
            db.commit()
            raise AuthServiceError("invalid_google_identity", str(exc), 401) from exc

        external = db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == "google", ExternalIdentity.provider_subject == identity.subject))
        if external:
            account = db.get(Account, external.account_id)
            if not account or account.status != "active":
                raise AuthServiceError("account_unavailable", "Аккаунт недоступен.", 403)
            external.last_login_at = utcnow()
            return self._issue_session(db, account, request, "google_login_succeeded")

        existing_account = db.scalar(select(Account).where(Account.email_normalized == identity.email))
        if existing_account:
            raise AuthServiceError("google_email_conflict", "Этот email уже связан с существующим Jarvis Account. Выполните отдельную привязку.", 409)

        account = Account(id=new_uuid7(), email=identity.email, email_normalized=identity.email, password_hash=hash_password("J-" + new_secret() + "Aa1"), email_verified_at=utcnow(), status="active")
        external = ExternalIdentity(id=new_uuid7(), account=account, provider="google", provider_subject=identity.subject, email_at_link=identity.email)
        db.add(account)
        db.add(external)
        self._event(db, "google_account_created", account.id, {"provider": "google"})
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            concurrent_identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == "google", ExternalIdentity.provider_subject == identity.subject))
            if concurrent_identity:
                concurrent_account = db.get(Account, concurrent_identity.account_id)
                if concurrent_account and concurrent_account.status == "active":
                    concurrent_identity.last_login_at = utcnow()
                    return self._issue_session(db, concurrent_account, request, "google_login_succeeded")
            raise AuthServiceError("google_identity_conflict", "Google identity уже создаётся или email занят.", 409) from exc
        return self._issue_session(db, account, request, "google_login_succeeded")

    def google_code_login(self, db: Session, code: str, code_verifier: str, redirect_uri: str, request) -> SessionTokens:
        if not self.settings.google_auth_enabled or not self.google_validator or not self.settings.google_client_secret:
            raise AuthServiceError("provider_disabled", "Вход через Google пока не подключён.", 503)
        parsed = urllib.parse.urlparse(redirect_uri)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path not in {"", "/", "/oauth/callback"} or not parsed.port:
            raise AuthServiceError("invalid_request", "Недопустимый Google loopback redirect.")
        try:
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
                timeout=15,
            )
            payload = response.json() if response.content else {}
        except (requests.RequestException, ValueError) as exc:
            detail = str(exc).replace("\n", " ").strip()[:180]
            raise AuthServiceError("google_provider_unavailable", f"Google token service недоступен: {type(exc).__name__}{(': ' + detail) if detail else ''}", 503) from exc
        if response.status_code >= 400 or not payload.get("id_token"):
            raise AuthServiceError("google_code_exchange_failed", "Google не принял authorization code.", 401)
        return self.google_login(db, str(payload["id_token"]), request)

    def authenticate_access(self, db: Session, access_token: str) -> DbSession:
        session = db.scalar(select(DbSession).where(DbSession.access_token_hash == token_digest(access_token)))
        if not session or session.revoked_at or session.access_expires_at <= utcnow():
            raise AuthServiceError("unauthorized", "Сессия недействительна.", 401)
        device = db.get(Device, session.device_id)
        if not device or device.revoked_at:
            raise AuthServiceError("device_revoked", "Устройство отозвано.", 401)
        session.last_used_at = utcnow()
        db.commit()
        return session

    def refresh(self, db: Session, refresh_token: str) -> SessionTokens:
        old = db.scalar(select(DbSession).where(DbSession.refresh_token_hash == token_digest(refresh_token)))
        if not old:
            raise AuthServiceError("unauthorized", "Сессия недействительна.", 401)
        if old.revoked_at:
            db.execute(update(DbSession).where(DbSession.token_family_id == old.token_family_id).values(revoked_at=utcnow()))
            self._event(db, "refresh_token_reuse", old.account_id)
            db.commit()
            raise AuthServiceError("token_reuse", "Сессия отозвана, требуется повторный вход.", 401)
        account = db.get(Account, old.account_id)
        device = db.get(Device, old.device_id)
        if not account or not device or device.revoked_at or old.expires_at <= utcnow():
            raise AuthServiceError("unauthorized", "Сессия недействительна.", 401)
        access, refresh = new_secret(), new_secret()
        replacement = DbSession(id=new_uuid7(), account_id=account.id, device_id=device.id, access_token_hash=token_digest(access), refresh_token_hash=token_digest(refresh), token_family_id=old.token_family_id, expires_at=expires_after(self.settings.refresh_ttl_seconds), access_expires_at=expires_after(self.settings.access_ttl_seconds))
        old.revoked_at = utcnow()
        old.replaced_by_session_id = replacement.id
        db.add(replacement)
        db.commit()
        return SessionTokens(account, device, replacement, access, refresh)

    def logout(self, db: Session, session: DbSession) -> None:
        session.revoked_at = utcnow()
        self._event(db, "logout", session.account_id)
        db.commit()

    def request_reset(self, db: Session, email: str) -> str | None:
        account = db.scalar(select(Account).where(Account.email_normalized == normalize_email(email)))
        if not account or account.status != "active":
            return None
        token = new_secret()
        db.add(PasswordResetToken(id=new_uuid7(), account_id=account.id, token_hash=token_digest(token), expires_at=expires_after(self.settings.reset_ttl_seconds)))
        self._event(db, "password_reset_requested", account.id)
        try:
            db.flush()
            self.email_provider.send_password_reset(account.email, token)
        except Exception as exc:
            db.rollback()
            raise AuthServiceError("email_delivery_failed", "Не удалось передать письмо локальному SMTP.", 503) from exc
        db.commit()
        return token

    def confirm_reset(self, db: Session, token: str, password: str) -> None:
        item = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_digest(token)))
        if not item or item.consumed_at or item.expires_at <= utcnow():
            raise AuthServiceError("invalid_token", "Токен восстановления недействителен или истёк.")
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            raise AuthServiceError("invalid_request", str(exc)) from exc
        account = db.get(Account, item.account_id)
        if not account:
            raise AuthServiceError("invalid_token", "Токен восстановления недействителен.")
        item.consumed_at = utcnow()
        account.password_hash = password_hash
        db.execute(update(DbSession).where(DbSession.account_id == account.id, DbSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
        self._event(db, "password_reset_completed", account.id)
        db.commit()

    def change_password(self, db: Session, session: DbSession, current_password: str, new_password: str) -> None:
        account = db.get(Account, session.account_id)
        if not account or not verify_password(account.password_hash, current_password):
            raise AuthServiceError("invalid_credentials", "Текущий пароль неверен.", 401)
        try:
            account.password_hash = hash_password(new_password)
        except ValueError as exc:
            raise AuthServiceError("invalid_request", str(exc)) from exc
        db.execute(update(DbSession).where(DbSession.account_id == account.id, DbSession.id != session.id, DbSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
        self._event(db, "password_changed", account.id)
        db.commit()

