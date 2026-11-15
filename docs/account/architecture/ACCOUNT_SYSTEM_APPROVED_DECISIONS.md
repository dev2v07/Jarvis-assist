# Jarvis Account System — approved decisions

Дата фиксации: 2026-11-14  
Статус: решения пользователя, утвержденные для design freeze Phase 0.5.

## 1. Что утверждено

| Область | Утвержденное решение | Следствие |
|---|---|---|
| Account type | Personal Account | один личный account, несколько devices; household/team не реализуются сейчас |
| Sync | All Sync | dialogs, messages, attachments, archive, favorites, sync history and selected settings sync across authorized devices |
| Memory | Consent-Based Memory Sync | memory off by default until explicit consent; preview/import/edit/delete/history |
| AI | Hybrid AI | Local AI preferred; cloud/third-party only by policy and visible consent |
| E2EE | Later | v1 uses TLS, server encryption, encrypted backups; server can read synced message content |
| Hosting | VPS First | portable containerized modular monolith, PostgreSQL, S3-compatible storage and worker |
| Local operation | preserved | Local Mode works without account, internet or server |

## 2. Data classification freeze

**Cloud Synced:** all selected conversations/messages, archive, normalized favorites, accepted attachments, sync ledger/cursors/tombstones, selected allowlisted preferences and approved AI conversation records.

**Device Only:** local models, voice models/WAV cache, local provider keys, microphone/device settings, local execution capabilities, local encrypted cache/outbox and local-only data.

**Excluded:** local absolute paths, filesystem indexes, raw microphone recordings, local system data, unrelated temporary data and shared Knowledge Library replication. These categories are not automatically uploaded.

Personal memory is separate: it enters Cloud Synced only after memory sync consent and item-level import/management rules.

## 3. Frozen invariants

- `account_id` is the authorization root; client-supplied account IDs never grant access.
- New canonical IDs use UUIDv7 strings.
- `source_local_id` is retained only as import provenance; it is not a cloud identity.
- `client_message_id` and `operation_id` make retries idempotent.
- `import_id` makes a complete import job repeatable and duplicate-safe.
- `favorites` is the sole normalized source of truth; `conversation.favorite` is only a derived DTO projection.
- REST cursor push/pull is authoritative; WebSocket/SSE is notification only.
- Tombstones propagate deletion before physical purge.
- Local copy remains until user separately confirms deletion.
- Current SQLite schema and current APIs are not changed in Phase 0/0.5.

## 4. Security freeze

Argon2id password hashing, email verification, short-lived access tokens, rotating/revocable refresh tokens, TLS, encrypted server storage/backups, OS-protected local credentials, rate limits, strict ownership checks, attachment validation and audit events are baseline requirements. E2EE key enrollment/recovery fields may be reserved but do not imply E2EE in v1.

## 5. Compatibility intent

The personal-account model must be extensible to future household/team memberships by adding membership and role layers around the same account-scoped resources. No household/team behavior, sharing permission or multi-tenant UI is part of this freeze.

## 6. Not yet approved

The following remain open and must not be silently chosen as final requirements: email provider, domain, VPS region, exact attachment quotas, tombstone/backup retention, AI provider allowlist, cloud-AI budget, recovery policy and E2EE schedule. Defaults are documented as proposals in the architecture/security documents.
