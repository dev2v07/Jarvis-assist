from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str
    smtp_use_ssl: bool
    smtp_use_starttls: bool
    smtp_timeout: float
    email_delivery_enabled: bool
    public_base_url: str
    google_auth_enabled: bool
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    access_ttl_seconds: int
    refresh_ttl_seconds: int
    verification_ttl_seconds: int
    reset_ttl_seconds: int
    environment: str

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("ACCOUNT_DATABASE_URL", "")
        if not database_url:
            raise RuntimeError("ACCOUNT_DATABASE_URL must point to PostgreSQL")
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("Account Server requires a PostgreSQL ACCOUNT_DATABASE_URL")
        def boolean(name: str, default: str = "false") -> bool:
            return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

        settings = cls(
            database_url=database_url,
            smtp_host=os.getenv("ACCOUNT_SMTP_HOST", "127.0.0.1"),
            smtp_port=int(os.getenv("ACCOUNT_SMTP_PORT", "1025")),
            smtp_username=os.getenv("ACCOUNT_SMTP_USERNAME", ""),
            smtp_password=os.getenv("ACCOUNT_SMTP_PASSWORD", ""),
            smtp_from_email=os.getenv("ACCOUNT_SMTP_FROM_EMAIL", os.getenv("ACCOUNT_SMTP_FROM", "no-reply@jarvis.local")),
            smtp_from_name=os.getenv("ACCOUNT_SMTP_FROM_NAME", "JARVIS ASSIST"),
            smtp_use_ssl=boolean("ACCOUNT_SMTP_USE_SSL"),
            smtp_use_starttls=boolean("ACCOUNT_SMTP_USE_STARTTLS"),
            smtp_timeout=float(os.getenv("ACCOUNT_SMTP_TIMEOUT", "10")),
            email_delivery_enabled=boolean("ACCOUNT_EMAIL_DELIVERY_ENABLED", "false"),
            public_base_url=os.getenv("ACCOUNT_PUBLIC_BASE_URL", "").rstrip("/"),
            google_auth_enabled=boolean("GOOGLE_AUTH_ENABLED", "false"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8765/"),
            access_ttl_seconds=int(os.getenv("ACCOUNT_ACCESS_TTL_SECONDS", "900")),
            refresh_ttl_seconds=int(os.getenv("ACCOUNT_REFRESH_TTL_SECONDS", "2592000")),
            verification_ttl_seconds=int(os.getenv("ACCOUNT_VERIFICATION_TTL_SECONDS", "86400")),
            reset_ttl_seconds=int(os.getenv("ACCOUNT_RESET_TTL_SECONDS", "3600")),
            environment=os.getenv("ACCOUNT_ENVIRONMENT", "development"),
        )
        if settings.email_delivery_enabled and settings.smtp_host == "smtp.yandex.ru":
            if not settings.smtp_username or not settings.smtp_password:
                raise RuntimeError("Yandex SMTP delivery requires local ACCOUNT_SMTP_USERNAME and application-password ACCOUNT_SMTP_PASSWORD")
            if not settings.public_base_url or "localhost" in settings.public_base_url or "127.0.0.1" in settings.public_base_url:
                raise RuntimeError("Yandex SMTP delivery requires a non-local ACCOUNT_PUBLIC_BASE_URL")
        if settings.smtp_use_ssl and settings.smtp_use_starttls:
            raise RuntimeError("SMTP SSL and STARTTLS cannot both be enabled")
        if settings.google_auth_enabled and (not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri):
            raise RuntimeError("Google Auth requires server-side GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI")
        return settings

