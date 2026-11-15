# Jarvis Account System — итоговый отчет Phase 0

Дата: 2026-11-14  
Режим: READ ONLY

## Итог

Jarvis уже имеет полезные кирпичики будущей экосистемы: локальный FastAPI boundary, UUID-like chat/message identifiers, SQLite WAL, chat CRUD, JSON-compatible runtime contracts и разделение desktop UI/backend/core. Но текущая система является single-installation/local-first, а не многопользовательской: ownership, authentication, device identity, cloud sync, idempotency и account-scoped memory отсутствуют.

Рекомендуется сохранить текущий execution engine и добавить отдельный account/sync plane через adapter. Сначала — canonical data/identity contract и Local-to-Account import, затем auth, затем cursor-based synchronization. REST должен быть источником истины, WebSocket/SSE — только каналом уведомления о наличии изменений.

## Что проверено

- `README.md`, `ROADMAP.md`, `docs/ARCHITECTURE_BASELINE.md`, `docs/APP_SERVER.md`, packaging specs/scripts.
- `backend/main.py`, `backend/config.py`, `backend/core/*`, `backend/agents/*`, `backend/services/*`.
- `frontend/launch_jarvis.py`, `frontend/jarvis_ui.py`, `frontend/profile_dialog.py`, voice input/composer files.
- `backend/voice_engine/*` — только архитектурно, без изменений.
- `backend/data/jarvis_state.sqlite3` в read-only режиме: schema/counts.
- `data/filesystem_index.db` в read-only режиме: schema/count.
- JSON/env/requirements metadata; secret values не включались в отчет.

## Ключевые обнаружения

1. Основной стек: Python + PySide6 + FastAPI/Uvicorn, локальный backend на `127.0.0.1:8000`, запуск через `frontend/launch_jarvis.py`.
2. `ChatStore` уже хранит sessions/messages/attachments/reactions/pins, поддерживает archive/rename/delete и paging, но не хранит `user_id`, `device_id`, `revision`, sync tombstone или operation ID.
3. Текущий контекст AI — последние 12 сообщений локального chat; remote continuation отсутствует.
4. Профиль — Qt `QSettings` с фиксированным `user:danil`; это UI profile, не account/auth.
5. MemoryAgent сохраняет regex facts в общий `backend/data/facts/facts.json`; user scope and consent отсутствуют.
6. `backend/data/jarvis_state.sqlite3` — текущая chat/request DB; `data/filesystem_index.db` — отдельный filesystem index.
7. BackupAgent архивирует локальные facts/documents/uploads/state DB; remote encrypted backup and account restore отсутствуют.
8. Ollama/local providers, voice/STT/TTS and filesystem/application tools are device-bound and should remain behind capability policy.
9. Current endpoints trust caller-provided chat IDs and have no auth middleware. They are safe only within intended loopback boundary.
10. Runtime events are in-memory, bounded and not durable sync history.

## Предлагаемое решение

### Identity

Account + credentials + devices + sessions. Passwords: Argon2id. Access token short-lived; refresh token rotated/revocable and stored hashed server-side. Email verification/reset/rate limits required.

### Data

Server canonical objects: conversations/messages/attachments/preferences/memory/favorites. Every object is account-scoped; messages additionally contain device and client idempotency identity. Shared Jarvis knowledge remains an application dataset, not a per-user copy.

### Sync

Local encrypted cache + durable outbox. Push operations carry `operation_id` and `base_revision`; pull uses a durable cursor. Reconnect always pulls from cursor. Message append is UUID/idempotent; title/settings use optimistic concurrency; delete uses tombstones. WebSocket/SSE only wakes the client to pull.

### Modes

Local Mode stays fully functional offline and without registration. Account Mode is opt-in. Existing local history is imported by explicit preview/confirmation, with stable source IDs and idempotent import job; local copy is retained until confirmation.

### Server

Portable modular monolith: TLS reverse proxy, API/auth/sync, PostgreSQL, S3-compatible object storage, background worker, monitoring and encrypted backups. This can move from VPS to own server without provider-specific data model.

## Риски

- Blindly exposing current local API would expose all local chats.
- Copying the SQLite file server-side would preserve missing ownership and conflict semantics.
- Syncing `facts.json` without provenance/consent could leak or merge private memory.
- Sending local provider keys, paths, voice recordings or full knowledge catalog to cloud expands privacy and attack surface.
- E2EE changes search, recovery, server-side AI and backup semantics; it must be a separately approved track.
- Existing dirty worktree includes parallel Knowledge/Voice work; future implementation must avoid shared-file collisions.

## Вопросы перед Phase 1

1. Account is strictly personal or future household/team sharing is required?
2. Which data is opt-in for sync: history, settings, attachments, memory?
3. Should cloud AI be enabled by default, device-only by default, or per conversation?
4. Retention period for deleted data, backups, audit logs and attachments?
5. Email provider and data residency requirements?
6. Required import matching and conflict UX?
7. Is E2EE a near-term requirement or a later privacy mode?
8. Which current local APIs remain internal adapter-only when remote API appears?

## Ограничения и next gate

Phase 0 не менял production code, existing DB/schema, configs, API behavior, files of Knowledge/Voice Library, WAVs or running processes. Перед Phase 1 нужны: approval of the proposed identity/data model, written threat model, migration/import strategy, API versioning decision, backup/restore policy and explicit permission to implement. До этого реализацию системы аккаунтов начинать нельзя.
