# Jarvis Account System — Phase 1A technical design

Статус: техническая спецификация, не реализация. Исходный код, SQLite, API и конфигурация в Phase 1A не изменяются.

## 1. Current-to-target integration

Фактические reusable boundaries:

- `frontend/launch_jarvis.py` запускает локальный backend и desktop UI и использует loopback `127.0.0.1:8000`.
- `backend/main.py` является FastAPI composition root: создает `ChatStore`, `AppServer`, `VoiceRuntime`, agents и backup agent; регистрирует текущие `/chat`, `/settings`, `/voice`, `/runtime`, `/app-server` routes.
- `backend/services/chat_store.py` — текущий local conversation CRUD/storage boundary.
- `backend/core/contracts.py` — UI-independent JSON-compatible `RequestContext`, `AgentResult`, `RuntimeEvent`, `ProviderStatus`.
- `backend/services/app_server.py` — local JSON-RPC/WebSocket lifecycle adapter поверх существующего chat pipeline.
- `backend/config.py` — local paths, env/runtime settings and provider configuration; importing it can create directories, поэтому будущий read-only inventory не должен импортировать production composition root.
- `frontend/jarvis_ui.py`/`profile_dialog.py` — PySide6 UI/QSettings local profile and chat client; UI is not an account boundary.

Компоненты, которых фактически нет: account client, token store, device registry, cloud API client, durable outbox, sync cursor store, import job, server auth/sync backend and account-scoped memory store.

## 2. Target boundary

```text
Jarvis UI / voice adapter / future mobile adapter
              |
       Account Client Layer (UI-independent)
              |
       Mode + Policy Coordinator
          /                 \
  Local Runtime Adapter     Sync Coordinator
          |                  /       \
    current ChatStore   Local Store  Outbox
                                  |
                             HTTPS Sync API
                                  |
                   cloud auth/account/sync modular monolith
                         PostgreSQL + S3-compatible storage
```

Account Client must not import Qt, agent internals or provider SDKs. It exposes typed DTOs and events. Local Runtime remains responsible for voice, Windows tools, Ollama, offline knowledge and device capabilities. Cloud API handles account-owned data and never executes arbitrary Windows commands.

## 3. Mode transitions

State machine: `LOCAL_ONLY -> CONNECTING -> AUTHENTICATED_DEVICE -> ACCOUNT_SYNCING -> ACCOUNT_ONLINE`, with recoverable `OFFLINE_ACCOUNT` and `AUTH_REQUIRED` states. Local Mode remains usable from every failure state. Logout revokes/clears account session tokens and stops sync; it does not delete local history. Re-login resumes using device identity and cursor.

Account Mode must not replace current `/chat` behavior in the first integration. A future adapter can mirror committed local messages into outbox after local transaction success. If sync is unavailable, message remains local and pending; the local response pipeline is not blocked by cloud availability.

## 4. Required invariants

1. No cloud request without validated access token and device session.
2. No account ID from body/query is trusted for ownership.
3. No absolute local path, filesystem index, secret, model, WAV cache, raw microphone audio or system data enters sync payload by default.
4. Local SQLite remains authoritative for Local Mode until an explicit migration/import design is approved.
5. Every remote mutation has `operation_id`; message append additionally has `client_message_id`.
6. Cursor advances only after durable local apply.
7. Account memory requires separate consent and preview.
8. Cloud AI requires policy gate and visible “leaving device” notice.

## 5. Implementation seams

Recommended future modules, initially behind interfaces:

- `AccountContext`: mode, account/device/session status and policy snapshot;
- `SecureCredentialStore`: OS-protected token material;
- `LocalDataAdapter`: read-only inventory/export DTOs from current stores;
- `LocalEntityMap`: mapping kept outside current SQLite until a storage decision;
- `OutboxStore`: durable operations and retry state;
- `SyncCoordinator`: push/pull/resolve/apply;
- `AccountApiClient`: versioned HTTPS transport;
- `ImportCoordinator`: manifest, upload, per-item status and rollback visibility;
- `AiRoutingPolicy`: local/cloud/third-party decision and consent event.

These are design names only; no files or classes are created in Phase 1A.

## 6. Current risks to preserve

`ChatStore` initialization contains `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE` fallback and an insert of the default chat; do not instantiate it merely for audit or import preview without an explicitly approved read/write boundary. `_row()` can lazily copy old attachment paths into `uploads/chat-media`, so inventory must use a non-mutating reader. Current toggle endpoints are not safe sync operations. Launcher contains a process-kill path for port 8000; account work must never invoke the launcher or process lifecycle.

## 7. Phase 1B/1C gate

Phase 1B may implement local identity/adapter only after owner approval of mapping storage and OS credential approach. Phase 1C may implement auth/API only after approval of email/domain/region, DTO version, server schema/migration policy, quotas, retention and isolated test environment.
