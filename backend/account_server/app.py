from __future__ import annotations

from fastapi import FastAPI

from .api import build_router
from .config import Settings
from .database import build_session_factory, dispose_session_factory
from .email_provider import EmailProvider, SMTPEmailProvider
from .google_identity import GoogleIdentityValidator
from .service import AuthService


def create_app(settings: Settings | None = None, *, email_provider: EmailProvider | None = None, google_validator: GoogleIdentityValidator | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    factory = build_session_factory(settings.database_url)
    provider = email_provider or SMTPEmailProvider(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_username,
        settings.smtp_password,
        settings.smtp_from_email,
        settings.smtp_from_name,
        settings.smtp_use_ssl,
        settings.smtp_use_starttls,
        settings.smtp_timeout,
        settings.email_delivery_enabled,
        settings.public_base_url,
    )
    app = FastAPI(title="Jarvis Account Server", version="1.0.0")
    app.include_router(build_router(AuthService(settings, provider, google_validator), factory))
    app.state.account_session_factory = factory

    @app.on_event("shutdown")
    def dispose_database() -> None:
        dispose_session_factory(factory)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "account-server"}

    return app

