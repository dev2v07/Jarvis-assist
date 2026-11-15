# Jarvis Account System — VPS server foundation

Статус: deployment design only. VPS, Docker Compose, databases and network services are not created in Phase 1A.

## 1. Modular monolith boundaries

One deployable application initially contains separate modules:

- Auth: registration, verification, login, reset, token/session lifecycle.
- Account/Device: personal profile, devices, sessions, scopes.
- Conversation: canonical metadata/messages/archive.
- Sync: operation ledger, revision checks, change feed, cursors/tombstones.
- Import: manifests, mapping, resumable jobs.
- Attachment: upload intents, validation, object references, quotas, deletion.
- Memory: consent, provenance, versions and account scope.
- Policy: preferences and Hybrid AI consent/routing decisions.
- Export/Deletion: asynchronous jobs and retention.
- Audit/Health: security events, metrics, readiness/liveness.

Modules share domain DTOs and repositories, not UI or Windows tool code. A worker handles email, import, scanning, export, deletion, backup compaction and garbage collection.

## 2. Initial topology

```text
Internet
  -> TLS reverse proxy/WAF boundary
  -> API container (modular monolith)
  -> PostgreSQL private network
  -> S3-compatible object storage/private endpoint
  -> Worker container + SMTP adapter
  -> monitoring/log collector
```

Docker Compose is an initial packaging topology, not a production deployment command for this phase. PostgreSQL and object storage are not exposed directly to clients. Upload/download uses authenticated API or short-lived signed URLs.

## 3. Secrets and configuration

Use deployment secret injection/secret files outside the image for database credentials, signing keys, SMTP credentials, object-storage keys and backup encryption keys. Rotate secrets with versioned key IDs. Never reuse Jarvis local `dev.env`, provider keys, QSettings or Windows runtime config as cloud secrets. No concrete provider, domain or VPS region is selected.

## 4. Database and migration boundary

Cloud PostgreSQL gets its own versioned migration framework and schema history. It is unrelated to `backend/data/jarvis_state.sqlite3`; never copy the local SQLite file as a server database. Migrations run only in isolated deployment pipeline with backup/rollback policy. Phase 1A specifies schema concepts but creates no server tables.

## 5. Object storage

S3-compatible adapter exposes put/get/head/delete/retention/version operations. Object keys are account-scoped opaque IDs, not local paths. Metadata remains in PostgreSQL. Accepted uploads require detected MIME, size, SHA-256, scan status and quota. Deletion tombstones metadata first and garbage-collects blobs later.

## 6. Health, logs and monitoring

Liveness checks process availability; readiness checks database/object-storage dependency state without exposing secrets. Metrics: auth failures, token reuse, active devices, push outcomes, conflict rate, cursor lag, import progress, upload rejection/quota, worker backlog, backup age and restore result. Structured logs use request/operation/device IDs and omit content, tokens, paths and keys.

## 7. Backup, restore and portability

Encrypted PostgreSQL logical/base backups plus encrypted object-storage backup/versioning. Keep encryption keys separate. Restore into isolated environment, validate ownership/tombstones/attachments and revoke all restored sessions before any recovery use. Portable components are containers, PostgreSQL, S3 API, SMTP adapter and documented volumes; moving VPS to owned hardware changes host/network/secrets, not domain logic.

## 8. Planning targets, not guarantees

Initial proposal for discussion: RPO 24h, RTO 24h, 30-day backup retention, 30-day tombstone retention and monthly restore drill. These are not approved SLAs; measure them before claiming operational capability.
