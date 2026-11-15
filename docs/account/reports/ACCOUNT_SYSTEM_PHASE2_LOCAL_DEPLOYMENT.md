# Phase 2 Local Deployment

## Prerequisites

Docker/Compose and the existing Python environment with FastAPI, SQLAlchemy, Alembic, psycopg and Argon2 are sufficient. No dependency installation was required in the implementation environment.

## Compose

From `C:\projects\Jarvis`:

```powershell
docker compose -f backend/account_server/docker-compose.yml up -d --build
```

Services bind only to loopback: PostgreSQL `5433`, Account API `8080`, SMTP `1025`, Mailpit UI `8025`. The API container applies `alembic upgrade head` before startup. Do not use volume deletion commands for this project.

The current environment already has the PostgreSQL image, and its migration was verified against a separate `jarvis_account_test` database. Mailpit image download was blocked by a Docker registry EOF, so the complete three-service compose startup remains pending registry availability.

For Yandex 360, do not use the Compose Mailpit variables. Put the real application password only in the ignored `backend/account_server/.env`, set `ACCOUNT_SMTP_HOST=smtp.yandex.ru`, port `465`, `ACCOUNT_SMTP_USE_SSL=true`, `ACCOUNT_SMTP_USE_STARTTLS=false`, `ACCOUNT_EMAIL_DELIVERY_ENABLED=true`, and provide an approved non-local `ACCOUNT_PUBLIC_BASE_URL`.

## Windows client

Set `JARVIS_ACCOUNT_API_URL=http://127.0.0.1:8080` only in the launch environment, then start Jarvis. This does not change `.env` or `dev.env`. Without this variable the client remains on the honest unavailable provider.

