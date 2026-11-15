# Jarvis Account System — test strategy

Статус: future strategy. No tests are run in Phase 1A.

## 1. Test layers

1. Pure contract tests for DTO validation, UUID/source mapping, hashes and policy decisions.
2. Repository tests against isolated temporary PostgreSQL/object-store substitutes.
3. Auth integration tests with mail/token test doubles.
4. Sync integration tests with two or more device identities and controlled network faults.
5. Import tests using sanitized fixtures modeled on current SQLite schema.
6. Security tests with isolated service and synthetic accounts only.
7. Restore/disaster tests in separate environment.
8. Manual product acceptance for consent notices, Local Mode continuity and device/session UX.

## 2. Mandatory cases

| Area | Required assertions |
|---|---|
| Auth | verification, reset expiry, Argon2id, rate limit, refresh rotation/reuse revoke |
| Isolation | cross-account IDs, attachment URLs, memory/export/cursor IDOR all denied |
| Devices | register, list, revoke one/all, revoked device cannot sync |
| Idempotency | repeated operation/import/message returns prior result; changed hash rejected |
| Concurrency | title/settings/archive/favorite/delete conflict matrix respected |
| Cursor | page apply atomic, crash/replay safe, expired cursor triggers full resync |
| Tombstones | delete reaches offline device; stale update cannot resurrect |
| Attachments | MIME/size/hash/scan/quota/rejected object/download authorization |
| Import | counts, manifest, partial failure, retry, corrupt file, no text dedup, local copy unchanged |
| Memory | consent required, preview/source/revision/edit/delete, no bulk message conversion |
| AI | local default, cloud notice/consent, category/provider allowlist, fail-closed budget/offline |
| Local Mode | no account/network still uses existing local behavior; account outage does not block local runtime |
| Backup | encrypted backup, isolated restore, tombstones and session revocation |
| Deletion | export, revoke, propagation, retention and eventual purge |

## 3. Required test data controls

Use synthetic emails, fake tokens, sanitized chat fixtures and non-sensitive attachments. Never use current user facts, real provider keys, raw voice files or production database. Test services must be isolated from parallel Knowledge/Voice processes.

## 4. Automation vs manual

Automate contract/auth/ownership/idempotency/concurrency/cursor/attachment/import/memory-policy tests. Use isolated environment for database/object-store/backup/restore. Manual acceptance is required for visible cloud-routing notice, Local/Account transition, device revoke UX, offline recovery and destructive deletion confirmations. Live provider/Ollama/voice tests are separate and must not be part of account sync unit tests.

## 5. Exit evidence

Phase gates require test report, fixture version, environment identity, pass/fail counts, known exclusions and no claims of live behavior where only mocks were used.
