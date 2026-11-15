# Jarvis Account System — security and privacy design

Статус: security baseline для утвержденной Phase 0.5 архитектуры. Реализации пока нет.

## 1. Threat model

Защищаем: account credentials, email, conversation/message content, attachments, personal memory, device/session access and sync integrity. Основные угрозы: credential stuffing, stolen refresh token, cross-account IDOR, replayed operations, duplicate uploads, malicious files, compromised device, leaked backups, over-broad AI forwarding and stale offline deletion.

Не считаем локальный Windows host доверенным серверным boundary: local tools remain local, but cloud API must authenticate and authorize every request. E2EE threat model не входит в v1; therefore server operators and server compromise can expose plaintext synced messages despite encryption at rest.

## 2. Identity and sessions

- Normalize email for uniqueness and verification; never disclose whether an email exists in reset/login errors.
- Hash passwords with Argon2id and calibrated memory/time parameters; never log passwords or raw reset tokens.
- Use short-lived access tokens and opaque rotating refresh tokens stored hashed server-side.
- Detect refresh-token reuse, revoke token family and record security audit event.
- Store browser tokens in HttpOnly/Secure/SameSite cookies; native clients use OS secure storage.
- Device/session list shows platform, label, last seen and revoke action; revoke blocks refresh and future sync.
- Rate limit login, reset, verification, upload, import and sync endpoints by account/IP/device.

## 3. Authorization and isolation

Every request derives `account_id`, `device_id` and scopes from validated credentials. Every query and object-storage key is account-prefixed and ownership-checked. Resource IDs are unguessable but are never treated as authorization. Cross-account tests must cover conversations, messages, attachments, memory, exports, cursors and deletion jobs.

Audit events record login, verification, password change, device registration/revoke, export, import, memory consent change, AI cloud consent, deletion and suspicious token reuse. Avoid putting message bodies, API keys or raw attachment content in logs.

## 4. Sync integrity and privacy

`operation_id` is unique per account; same ID with same payload returns the original result, while same ID with another payload hash is rejected. `base_revision` prevents silent lost updates. Pull cursor advances only after atomic local apply. Tombstones are retained long enough for offline devices and are not exposed as message content.

Cloud Synced data is minimized to canonical account objects. Device Only and Excluded data are rejected by import manifest/API policy, not merely hidden in UI. No absolute local paths, filesystem index, local model, WAV cache, raw microphone recording, system data or provider secret is included by default.

## 5. Attachments

Upload is authenticated and uses opaque object keys. Enforce detected MIME allowlist, extension consistency, file size, account quota, SHA-256 and malware/content scanning. Reject mismatches and never serve an unaccepted object. Use short-lived download URLs or authenticated streaming. Proposed defaults for agreement: 25 MiB/file, 1 GiB/account, 100 files/message; these are not final values.

Deletion marks attachment unavailable immediately, creates sync tombstone and schedules object purge after retention. Backups have separate expiry and may temporarily retain encrypted copies.

## 6. Hybrid AI privacy gate

Default policy is Local Preferred + Cloud Disabled until enabled. Before a request leaves the device, UI/voice reports the route and asks for consent when policy requires it. Cloud payload contains only the minimum conversation context needed; local files/system information are never attached without explicit user action. Third-party providers require separate allowlist/consent.

If cloud consent is off, network is unavailable, cost budget is exhausted or provider fails, do not silently switch to another external provider. Use local model, local deterministic service, or explain that the request cannot be completed. Route/provider and consent decision may be stored as non-secret execution metadata.

## 7. Local protection

Store account tokens and encryption keys in Windows Credential Manager/OS secure storage or platform equivalent. Protect local cache/outbox and attachment cache with filesystem ACLs and, where available, OS/device encryption. Do not expose tokens in QSettings, logs, crash reports, URLs or desktop IPC payloads. Local Mode must not require a network account and must preserve local-only data if account login fails.

## 8. Backup and recovery

Encrypt PostgreSQL and object-storage backups before off-host storage; keep keys separate from backup media. Restrict backup bucket access, enable versioning/immutability where supported and record backup manifests without content secrets. Restore tests must run in isolated environment and verify account ownership, tombstones, attachments and token revocation—not only database startup.

## 9. Deletion, export and retention

Before account deletion offer a portable export of conversations, messages, accepted attachments and consented memory. Deletion revokes all sessions/devices, stops new sync, creates tombstones, queues purge of server data and object blobs, and records minimal audit evidence. Physical purge occurs after approved retention windows; backups expire under a documented backup policy and are not restored into production without respecting deletion state.

Proposed defaults requiring agreement: 30-day tombstone window, 30-day backup retention, monthly restore drill. These are planning defaults, not promises.

## 10. E2EE later

Phase 0.5 reserves `devices.public_key`/key-enrollment concepts and per-object encryption metadata, but v1 does not use them. Future E2EE requires device enrollment, key rotation, recovery/escrow choice, lost-password behavior, multi-device removal, search/indexing limitations and server-side AI changes. Until that phase is approved, explicitly document that TLS and at-rest encryption do not provide end-to-end confidentiality.

## 11. Open security decisions

Email provider/domain, VPS region, exact quotas, retention, backup deletion policy, AI provider allowlist/budget, incident notification, data export format and recovery-key policy require approval before implementation.
