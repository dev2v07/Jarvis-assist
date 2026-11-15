# Jarvis Account System — Phase 0.5 report

Дата: 2026-11-14  
Режим: READ ONLY для Production-кода; изменены только документы Account System.

## 1. Результат design freeze

Зафиксирован фундамент: Personal Account + All Sync + consent-based memory + Hybrid AI + E2EE Later + VPS First. Jarvis остается полноценным Local Mode без регистрации/интернета, а Account Mode добавляет cloud sync только через ownership-aware API.

## 2. Обновленные и созданные документы

- `ACCOUNT_SYSTEM_ARCHITECTURE_PROPOSAL.md` — итоговая архитектура, data classes, Local-to-Account, full sync, attachments, AI policy, VPS boundary.
- `ACCOUNT_SYSTEM_DATA_MODEL.md` — frozen UUIDv7 IDs, import mapping, normalized favorites, entities, tombstones and sync ledger.
- `ACCOUNT_SYSTEM_IMPLEMENTATION_ROADMAP.md` — revised order with attachment, deletion, memory consent, Hybrid AI and operations phases.
- `ACCOUNT_SYSTEM_APPROVED_DECISIONS.md` — decisions explicitly approved by user vs unresolved parameters.
- `ACCOUNT_SYSTEM_SECURITY_AND_PRIVACY.md` — threat model, auth, authorization, sync integrity, attachment, AI privacy, backup, deletion and E2EE boundary.

Phase 0 audit and report remain historical evidence of current implementation; they are not rewritten as if proposed architecture already existed.

## 3. Final architecture summary

```text
Local client/runtime
  - Local Mode, local AI, voice, local cache, outbox
  - Account Mode, secure tokens, device identity
          |
          v HTTPS REST (authoritative push/pull)
VPS modular monolith
  - auth/account + device/session management
  - conversation/message/sync API
  - memory consent API + AI policy API
          |
          +--> PostgreSQL
          +--> S3-compatible object storage
          +--> worker/email/scanning/export/deletion
          +--> monitoring/encrypted backup
```

WebSocket/SSE is only a notification hint. Reconnect always uses cursor pull. Current local `/chat` and SQLite are not modified by this phase.

## 4. Canonical data and sync rules

- UUIDv7 canonical IDs for account/device/conversation/message/attachment/operation/import.
- Current local IDs are provenance/source IDs, not server identities.
- `client_message_id` prevents duplicate messages; `operation_id` replays the prior result; `import_id` replays the prior import job.
- `favorites` is normalized sole source of truth; DTO booleans are derived.
- All Sync covers dialogs, messages, attachments, archive, favorites, sync metadata and allowlisted settings.
- Memory is excluded from automatic sync until explicit consent and preview/import.
- Deletes use tombstones, propagate to offline devices, then physically purge after retention.
- Attachment upload validates detected MIME, size, SHA-256 and scan status; absolute local paths never cross the API.

## 5. AI Routing Policy

Default: Local Preferred, Cloud Disabled until the user enables it. Local commands, local Ollama and offline knowledge stay on device. Cloud AI is allowed only by account policy, category/provider allowlist and visible “data leaves device” notice. Sensitive requests/files/system data require local route or per-request consent. Offline/cloud failure is fail-closed to local fallback or an explicit error; no silent all-cloud or provider hopping.

## 6. VPS and recovery baseline

Initial deployment is portable Docker Compose: TLS edge, modular monolith, PostgreSQL, S3-compatible storage, worker/email, monitoring and encrypted backup. Exact provider, region and domain remain open. Proposed planning targets, not guarantees: RPO 24 hours and RTO 24 hours for the first VPS baseline; final values require workload and restore testing. Suggested initial retention defaults (also unapproved): tombstones 30 days, backups 30 days, monthly restore drill.

## 7. Unresolved parameters

| Parameter | Proposed default for discussion | Status |
|---|---|---|
| Email provider | SMTP adapter, provider-neutral | requires approval |
| Domain | dedicated Jarvis API/auth domain | requires approval |
| VPS region | selected by privacy/legal/data-residency needs | requires approval |
| Attachment quota | 25 MiB/file, 1 GiB/account, 100/message | requires approval |
| Tombstone retention | 30 days | requires approval |
| Backup retention | 30 days, encrypted | requires approval |
| AI providers | local Ollama first; explicit allowlist for cloud providers | requires approval |
| Cloud AI budget | disabled until user sets budget | requires approval |
| E2EE | separate future phase | approved as Later, schedule open |
| Account recovery | verified email first; recovery-key policy later | requires approval |

Ни один default выше не следует трактовать как финально выбранное эксплуатационное значение.

## 8. Risks controlled by this phase

- IDOR mitigated by account-derived authorization requirement.
- Duplicate sync/import controlled by operation/import/client IDs.
- Offline deletion handled by tombstones and retention.
- Attachment leakage reduced by no-path rule, quota/hash/MIME/scan pipeline.
- Cloud privacy controlled by explicit Hybrid AI policy and local-file exclusion.
- Parallel Knowledge/Voice work isolated: no production or shared library files were modified.

## 9. Criteria to enter Phase 1

Phase 1 may start only after explicit user authorization and agreement on:

1. canonical UUIDv7 and import mapping;
2. attachment quotas and accepted MIME policy;
3. tombstone and backup retention;
4. email/domain/VPS region;
5. initial cloud AI provider allowlist and budget policy;
6. local token/cache protection approach;
7. RPO/RTO as measurable targets;
8. migration/import test strategy and rollback expectations.

Until these are approved, do not implement account code, migrations, API changes or configuration changes.
