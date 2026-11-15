# Jarvis Account System — Phase 1A final report

Дата: 2026-11-14  
Режим: READ-ONLY audit + technical design.

## 1. Executive result

Phase 1A подготовила implementation-ready design без реализации. Текущий Jarvis остается локальным runtime; Account System добавляется как UI-independent client/account layer, Local Data Adapter, durable outbox/sync coordinator и отдельный HTTPS cloud backend. Current SQLite, `/chat`, QSettings, Voice, Knowledge and provider behavior не меняются.

## 2. Reusable vs new vs isolated

Переиспользуются `core/contracts.py`, `ChatStore` как источник локальной истории через read-only adapter, `AppServer` как локальный lifecycle boundary, `main.py` composition awareness, QSettings для Local Mode и BackupAgent как источник требований. Создаются позднее account/device/auth client, secure token storage, mapping/outbox/sync/import/attachment/memory/policy layers and cloud modules. Изолируются Voice/Knowledge/Memory files, local models, filesystem tools, current local APIs and process lifecycle.

## 3. Local and Account Mode

Local Mode works without account/network and remains the fallback for all cloud failures. Account Mode registers a device, maintains secure session/cache/outbox, imports selected local data by explicit job and syncs authorized account objects. Logout/revocation stops cloud access but does not erase local data. No cloud component can execute arbitrary Windows actions.

## 4. Local data and import

Current SQLite schema was verified read-only: `chat_sessions`, `chat_messages`, `chat_reactions`, `chat_pins`, `chat_attachments`, `requests`; observed counts were 9/68/6/0/70, while `requests` is execution state. Current local IDs become source/client IDs; cloud canonical entities receive UUIDv7. `import_id`, manifest hash, source namespace and per-item status prevent duplicate imports. Absolute paths are never sent; attachments use bytes/opaque object key plus MIME/size/SHA-256/scan checks. Local copy remains intact.

## 5. Sync

REST/HTTPS push/pull is authoritative. `operation_id`, `client_message_id`, payload hash and `base_revision` provide idempotency/concurrency. Pull uses ordered `server_sequence`, atomic page apply and durable `sync_cursor`; tombstones propagate deletes. WebSocket/SSE, if later added, is only a wake-up hint. Explicit set/delete replaces blind toggle in future API; current endpoints remain unchanged.

## 6. Auth, memory and AI

Auth design covers email registration/verification, Argon2id, short-lived access, opaque rotating refresh, reuse detection, device registration/revoke, rate limits and lost-device behavior without choosing provider/domain/region. Memory is split into Local Memory, consented Personal Account Memory and Shared Knowledge Library; no `facts.json` or MemoryAgent changes. AI default is Local Preferred + Cloud Disabled; cloud requires policy/consent/notice/minimized context and never receives local files/system data silently.

## 7. Server foundation

VPS First containerized modular monolith: auth/account/sync/import/attachment/memory/policy/export modules, PostgreSQL, S3-compatible storage, worker/email, monitoring and encrypted backups. Cloud has its own migration framework later; it must not reuse the local SQLite file. Proposed RPO/RTO and retention values remain planning defaults, not guarantees.

## 8. Open questions

- mapping persistence location;
- reaction/pin and profile/avatar import policy;
- exact MIME allowlist, file/account quotas;
- tombstone and backup retention;
- email provider, domain and VPS region;
- cloud provider allowlist and AI budget;
- access/refresh TTLs and recovery policy;
- local OS secure-storage mechanism;
- cloud migration framework and deployment owner;
- exact acceptance of per-request AI consent UX.

## 9. Proposed next phases

**Phase 1B:** approve open parameters, define DTO/schema versions, build isolated test fixtures and implement only local identity/adapter interfaces with Local Mode preserved.

**Phase 1C:** implement cloud auth/account foundation in isolated environment, including PostgreSQL migrations, email test double, session/device management and ownership tests.

**Phase 2:** implement conversation All Sync, outbox/cursors/tombstones/import and protected attachments.

**Phase 3:** settings/devices/export/deletion, then Phase 4 consented memory and Phase 5 Hybrid AI policy, followed by mobile/future clients and operations. E2EE remains separate later phase.

## 10. Phase 1A acceptance evidence

- Mandatory Phase 0.5 documents were read and reconciled.
- Current source boundaries and SQLite schema were inspected read-only.
- All requested technical design documents were created in `docs/`.
- No tests, servers, migrations, dependencies, email, VPS or production runtime were started.
- Existing dirty worktree changes were preserved and not treated as Phase 1A work.

## 11. File and change confirmation

Phase 1A changes are limited to Account System documentation files in `C:\projects\Jarvis\docs\`: the updated roadmap and the ten new technical design/report files requested for Phase 1A. No production Python, SQLite database, `.env`/`dev.env`, QSettings, API implementation, Voice Engine, Knowledge Library, Fish Audio, WAV, Ollama model or system process was changed.

Verification completed: `git status --short` shows the pre-existing README/backend/voice/knowledge worktree changes plus Account System documentation files; no production file was added to the Phase 1A change set. `git diff --check` exited with code 0. Git emitted only existing LF/CRLF normalization warnings for pre-existing tracked files; no whitespace error was reported. These are repository checks, not runtime tests.
