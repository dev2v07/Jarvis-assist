from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from .models import Account, Device, Session as DbSession
from .schemas import GoogleExchangeRequest, LoginRequest, PasswordChangeRequest, PasswordResetConfirmRequest, PasswordResetRequest, RefreshRequest, RegisterRequest, VerifyEmailRequest
from .service import AuthService, AuthServiceError, SessionTokens, iso
from .security import RateLimiter


bearer = HTTPBearer(auto_error=False)


def _error(error: AuthServiceError, request_id: str) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"error": {"code": error.code, "message": error.message, "request_id": request_id}})


def _tokens(tokens: SessionTokens) -> dict:
    return {
        "schema_version": 1,
        "account": {"id": tokens.account.id, "email": tokens.account.email, "email_verified": bool(tokens.account.email_verified_at), "status": tokens.account.status},
        "device": {"id": tokens.device.id, "name": tokens.device.device_name, "platform": tokens.device.platform},
        "session": {"id": tokens.session.id, "expires_at": iso(tokens.session.expires_at)},
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "Bearer",
    }


def build_router(service: AuthService, factory: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    limiter = RateLimiter()

    def db_dep():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    def current_session(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(db_dep)) -> str:
        request_id = str(uuid.uuid4())
        if not credentials or credentials.scheme.lower() != "bearer":
            raise _error(AuthServiceError("unauthorized", "Требуется авторизация.", 401), request_id)
        try:
            return service.authenticate_access(db, credentials.credentials).id
        except AuthServiceError as error:
            raise _error(error, request_id) from error

    def request_id() -> str:
        return str(uuid.uuid4())

    @router.post("/auth/register", status_code=202)
    def register(payload: RegisterRequest, db: Session = Depends(db_dep), x_forwarded_for: str | None = Header(default=None)):
        if not limiter.allow(f"register:{x_forwarded_for or 'local'}"):
            raise _error(AuthServiceError("rate_limited", "Слишком много запросов. Повторите позже.", 429), request_id())
        try:
            service.register(db, payload.email, payload.password)
        except AuthServiceError as error:
            raise _error(error, request_id()) from error
        return {"schema_version": 1, "message": "Если email допустим, письмо подтверждения отправлено."}

    @router.post("/auth/verify-email")
    def verify_email(payload: VerifyEmailRequest, db: Session = Depends(db_dep)):
        try:
            account = service.verify_email(db, payload.token)
        except AuthServiceError as error:
            raise _error(error, request_id()) from error
        return {"schema_version": 1, "account_id": account.id, "email_verified": True}

    @router.post("/auth/login")
    def login(payload: LoginRequest, db: Session = Depends(db_dep), x_forwarded_for: str | None = Header(default=None)):
        if not limiter.allow(f"login:{x_forwarded_for or 'local'}"):
            raise _error(AuthServiceError("rate_limited", "Слишком много попыток входа.", 429), request_id())
        try:
            return _tokens(service.login(db, payload))
        except AuthServiceError as error:
            raise _error(error, request_id()) from error

    @router.post("/auth/google/exchange")
    def google_exchange(payload: GoogleExchangeRequest, db: Session = Depends(db_dep)):
        try:
            if payload.code:
                if not payload.code_verifier or not payload.redirect_uri:
                    raise AuthServiceError("invalid_request", "Google authorization data is incomplete.")
                return _tokens(service.google_code_login(db, payload.code, payload.code_verifier, payload.redirect_uri, payload))
            if payload.id_token:
                return _tokens(service.google_login(db, payload.id_token, payload))
            raise AuthServiceError("invalid_request", "Google authorization data is missing.")
        except AuthServiceError as error:
            raise _error(error, request_id()) from error

    @router.post("/auth/refresh")
    def refresh(payload: RefreshRequest, db: Session = Depends(db_dep)):
        try:
            return _tokens(service.refresh(db, payload.refresh_token))
        except AuthServiceError as error:
            raise _error(error, request_id()) from error

    @router.post("/auth/logout")
    def logout(session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        service.logout(db, session)
        return {"schema_version": 1, "logged_out": True}

    @router.post("/auth/password-reset/request", status_code=202)
    def request_reset(payload: PasswordResetRequest, db: Session = Depends(db_dep)):
        try:
            service.request_reset(db, payload.email)
        except AuthServiceError as error:
            raise _error(error, request_id()) from error
        return {"schema_version": 1, "message": "Если email существует, письмо восстановления отправлено."}

    @router.post("/auth/password-reset/confirm")
    def confirm_reset(payload: PasswordResetConfirmRequest, db: Session = Depends(db_dep)):
        try:
            service.confirm_reset(db, payload.token, payload.password)
        except AuthServiceError as error:
            raise _error(error, request_id()) from error
        return {"schema_version": 1, "password_reset": True}

    @router.post("/auth/password-change")
    def change_password(payload: PasswordChangeRequest, session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        try:
            service.change_password(db, session, payload.current_password, payload.new_password)
        except AuthServiceError as error:
            raise _error(error, request_id()) from error
        return {"schema_version": 1, "password_changed": True}

    @router.get("/account/profile")
    def profile(session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        account = db.get(Account, session.account_id)
        return {"schema_version": 1, "id": account.id, "email": account.email, "email_verified": bool(account.email_verified_at), "status": account.status, "created_at": iso(account.created_at), "last_login_at": iso(account.last_login_at)}

    @router.get("/account/devices")
    def devices(session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        rows = db.scalars(select(Device).where(Device.account_id == session.account_id).order_by(Device.created_at)).all()
        return {"schema_version": 1, "devices": [{"id": x.id, "device_name": x.device_name, "platform": x.platform, "client_version": x.client_version, "created_at": iso(x.created_at), "last_seen_at": iso(x.last_seen_at), "revoked_at": iso(x.revoked_at)} for x in rows]}

    @router.get("/account/sessions")
    def sessions(session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        rows = db.scalars(select(DbSession).where(DbSession.account_id == session.account_id).order_by(DbSession.created_at.desc())).all()
        return {"schema_version": 1, "sessions": [{"id": x.id, "device_id": x.device_id, "created_at": iso(x.created_at), "expires_at": iso(x.expires_at), "last_used_at": iso(x.last_used_at), "revoked_at": iso(x.revoked_at)} for x in rows]}

    @router.post("/account/devices/{device_id}/revoke")
    def revoke_device(device_id: str, session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        device = db.scalar(select(Device).where(Device.id == device_id, Device.account_id == session.account_id))
        if not device:
            raise _error(AuthServiceError("not_found", "Устройство не найдено.", 404), request_id())
        device.revoked_at = datetime.now(timezone.utc)
        db.execute(update(DbSession).where(DbSession.device_id == device.id, DbSession.revoked_at.is_(None)).values(revoked_at=device.revoked_at))
        db.commit()
        return {"schema_version": 1, "revoked": True}

    @router.post("/account/sessions/{target_id}/revoke")
    def revoke_session(target_id: str, session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        target = db.scalar(select(DbSession).where(DbSession.id == target_id, DbSession.account_id == session.account_id))
        if not target:
            raise _error(AuthServiceError("not_found", "Сессия не найдена.", 404), request_id())
        target.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return {"schema_version": 1, "revoked": True}

    @router.post("/account/sessions/revoke-all")
    def revoke_all(session_id: str = Depends(current_session), db: Session = Depends(db_dep)):
        session = db.get(DbSession, session_id)
        if not session:
            raise _error(AuthServiceError("unauthorized", "Сессия недействительна.", 401), request_id())
        db.execute(update(DbSession).where(DbSession.account_id == session.account_id, DbSession.id != session.id, DbSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
        db.commit()
        return {"schema_version": 1, "revoked": True}

    return router

