# Account System Phase 2 — Server Architecture

Status: local implementation; no VPS or public deployment.

`backend/account_server/` is a standalone FastAPI modular monolith. It has independent configuration, SQLAlchemy models, Alembic migrations, auth/application services, SMTP adapter and REST API. It does not import ChatStore, `/chat`, `/app-server`, Voice Engine, Knowledge Library or MemoryAgent.

Runtime topology:

```text
Windows Jarvis -> HTTP Auth Provider -> Account API :8080
                                      |-> PostgreSQL :5433
                                      |-> local SMTP sink :1025 (Mailpit :8025)
```

The database is PostgreSQL-only. A separate local Docker volume is used for Account Server. The local client only selects the HTTP provider when `JARVIS_ACCOUNT_API_URL` is explicitly present; otherwise it keeps `UnavailableAuthProvider` and `LOCAL_ONLY`.

Implemented modules include settings, PostgreSQL session factory, domain models, auth service, security helpers, SMTP provider, API routes and migration `0001_initial`.

