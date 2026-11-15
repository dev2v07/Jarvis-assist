# Jarvis Account System — frozen implementation roadmap

Порядок ниже относится к будущей разработке. Phase 1 не начинается автоматически после Phase 0.5.

## Phase 0 — audit

Фактическая архитектура, local storage, chat/memory/voice boundaries и ограничения зафиксированы в `ACCOUNT_SYSTEM_AUDIT.md` и `ACCOUNT_SYSTEM_PHASE0_REPORT.md`.

## Phase 0.5 — design freeze (текущий этап)

- Утвердить Personal Account, All Sync, consent-based memory, Hybrid AI, E2EE Later, VPS First.
- Заморозить canonical IDs, import identity, normalized favorites, attachment policy, deletion model and sync semantics.
- Зафиксировать Cloud Synced / Device Only / Excluded matrix.
- Согласовать unresolved parameters before implementation.

Exit: approved decisions, security/privacy model, data model, AI routing policy and Phase 1 gate.

## Phase 1A — implementation readiness and technical design

- Сопоставить утвержденный design freeze с фактическими boundaries `main.py`, `ChatStore`, `app-server`, `RequestContext`, frontend и backup/runtime.
- Зафиксировать Local Data Adapter без изменения текущей SQLite schema.
- Спроектировать durable outbox, push/pull cursor protocol, idempotency, import manifest, auth/device contracts and v1 API DTOs.
- Разделить Local Memory, consented Personal Account Memory и Shared Knowledge Library.
- Утвердить Hybrid AI routing gate, VPS module boundaries and isolated test strategy.

Exit: technical design documents, gap register, explicit open questions and Phase 1B/1C entry criteria. No production implementation.

## Phase 1B — local identity boundary and import adapter (implemented)

- Создать account/device context abstractions рядом с текущим local ChatStore, сохранив Local Mode.
- Реализовать read-only inventory and import preview interfaces, без изменения текущей SQLite schema until separately approved.
- Определить encrypted local metadata, outbox and canonical DTO adapters.
- Unit/contract tests for ID mapping, duplicate import and operation replay.

Фактически реализовано в изолированном `backend/account/`: LOCAL_ONLY context/provider, read-only SQLite adapter, inventory/import preview, canonical manifest mapper и in-memory ports для будущих mapping/outbox/credentials. Existing composition root, `/chat`, SQLite schema and settings remain unchanged.

Exit: local Jarvis works offline/no-auth; preview is read-only and retry-safe; durable encrypted identity/mapping/outbox storage remains a later approved scope.

## Phase 1C — persistent local identity and Account UI (implemented locally)

- Реализованы отдельные persistent metadata/mapping/outbox storage и стабильная локальная Device Identity.
- Реализован Windows Current User DPAPI adapter без plaintext fallback.
- Добавлены AccountContext/Coordinator boundary, auth provider contract и честный `UnavailableAuthProvider`.
- Existing profile affordance opens optional Account Panel; Local Mode remains the default and does not require network or registration.
- Added login, registration, email verification and password recovery UI as server-ready screens; no operation is faked as successful.
- Cloud authentication, email, sync, import upload and account server remain disabled until the next approved phase.

Exit: local application remains fully operational; Account metadata survives restart; credentials are OS-protected on Windows; Account UI is reachable without changing chat behavior; no production SQLite or cloud request is used.

## Phase 1D — server connection readiness

- Approve email/domain/region, API version, quotas, retention and test environment.
- Implement the real Auth API client, server ownership checks and session lifecycle.
- Add explicit post-auth sync opt-in, inventory and import preview flow without automatic upload.

## Phase 2 — local Account Server foundation (implemented locally)

- Standalone FastAPI modular monolith with PostgreSQL, SQLAlchemy and Alembic.
- Registration, local SMTP verification, login, opaque access/refresh sessions, rotation and reuse detection.
- Password reset/change, device/session listing and revocation, security events and ownership checks.
- Windows HTTP Auth Provider is opt-in through `JARVIS_ACCOUNT_API_URL`; missing server/configuration preserves `LOCAL_ONLY`.
- Docker Compose defines PostgreSQL, Account API and Mailpit on loopback-only development ports.

Exit: local PostgreSQL auth flow and isolated Windows client contract pass targeted tests. Public deployment, external email and Cloud Sync remain disabled.

## Phase 2 — auth/account API

- Deploy modular monolith on VPS staging: HTTPS edge, auth/account module, PostgreSQL, email adapter.
- Registration, email verification, login, reset, change password, logout, device/session list/revoke.
- Argon2id, rotating refresh tokens, rate limits, audit events and ownership middleware.

Exit: personal account lifecycle works; no cloud message sync yet.

## Phase 3 — All Sync for conversations

- Canonical conversations/messages/archive/favorites API.
- Durable outbox, idempotent push, cursor pull, server sequence and tombstones.
- Local-to-account import job with `import_id`, manifest and per-item result.
- Attachment upload to protected S3-compatible storage with MIME/size/hash/scan checks.
- Two-device/offline/retry/conflict tests.

Exit: all approved conversation data is available on authorized devices without duplicate messages.

## Phase 4 — settings, devices and account lifecycle

- Device management UI and per-device revoke.
- Allowlisted settings sync; explicit local-only settings.
- Export, account deletion, tombstone propagation, retention and backup interaction.

Exit: user can inspect data placement, export data and revoke access.

## Phase 5 — consent-based personal memory

- Memory inventory/preview, enable/disable sync, item edit/delete, provenance and version history.
- No bulk message-to-memory conversion.
- Keep Knowledge Library separate and shared/versioned.

Exit: memory sync is explicit, reversible before purge and account-scoped.

## Phase 6 — Hybrid AI policy

- Local/cloud/hybrid settings, allowlisted providers, category controls and cost budget.
- Visible “leaving device” notice before cloud request.
- Data minimization/redaction and fail-closed behavior when consent/network/provider is unavailable.
- AI execution metadata without secrets.

Exit: no automatic all-cloud routing; user can audit route and consent.

## Phase 7 — mobile and future clients

- Versioned client contract and reference Android/iOS adapters.
- Secure token storage, local cache/outbox and reconnect tests.
- TV/browser/auto/smart-home clients consume same account/sync APIs with capability restrictions.

Exit: new platforms do not require account-service rewrite.

## Phase 8 — operations and portability

- Docker Compose production baseline, PostgreSQL/Object Storage backups, restore drills, monitoring, secret rotation and update process.
- VPS-to-own-server migration rehearsal.
- Establish project RPO/RTO targets and measure them; do not claim them as guarantees.

Exit: documented disaster recovery and portable deployment.

## Separate future phase — E2EE

Device key enrollment, recovery, per-object encryption and cryptographic device identity are intentionally postponed. First version server-side encryption does not conceal synchronized message content from the server. E2EE must be designed and approved separately before implementation.

## Non-negotiable order

Identity/data contract -> auth/ownership -> durable sync -> attachments/deletion -> memory consent -> AI routing -> additional clients -> operations -> optional E2EE. No copying of the current SQLite file to a server and no UI-only login before ownership and sync semantics exist.
