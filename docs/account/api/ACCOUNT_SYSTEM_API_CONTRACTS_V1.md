# Jarvis Account System — preliminary API contracts v1

Статус: proposed versioned contract, not implemented and not a change to current local `/chat` APIs.

## 1. Common envelope

All responses use JSON, UTC ISO-8601 timestamps and `schema_version: 1`. Errors:

```json
{"error":{"code":"conflict","message":"safe user-facing text","request_id":"uuid"}}
```

`request_id` is transport tracing only. Mutating calls that can be retried accept `Idempotency-Key` carrying `operation_id`; server stores payload hash and prior result.

## 2. Auth/account/device groups

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/auth/register` | none | create pending account; no raw password in logs |
| POST | `/v1/auth/verify-email` | verification token | activate email |
| POST | `/v1/auth/login` | none | issue access + refresh session |
| POST | `/v1/auth/refresh` | refresh credential | rotate token |
| POST | `/v1/auth/logout` | session | revoke current session |
| POST | `/v1/auth/password-reset` | none | request generic reset |
| POST | `/v1/auth/password-reset/confirm` | reset token | set new password |
| POST | `/v1/auth/password-change` | account session | change password |
| GET/PATCH | `/v1/accounts/me` | account | profile, no credential secret |
| GET/POST/PATCH/DELETE | `/v1/devices` | account | list/register/update/revoke devices |
| GET/DELETE | `/v1/sessions` | account | list/revoke sessions |

Exact email provider, domain, TTLs and regional deployment are open decisions.

## 3. Sync groups

`POST /v1/sync/push`: authenticated device; body `{schema_version, operations:[operation envelope]}`; returns per-operation `committed|duplicate|conflict|rejected`, canonical IDs, revisions, server sequences and prior result for duplicate.

`GET /v1/sync/pull?cursor=<sequence>&limit=<n>`: authenticated device; returns ordered changes, tombstones, `next_cursor`, `has_more`; cursor advances only after client apply.

Ownership: account from token; device must belong to account and not be revoked. Push validates base revision, payload hash and idempotency. Pull never returns another account’s changes.

## 4. Import groups

`POST /v1/imports`: create job with `import_id`, manifest hash, counts and selected categories. `POST /v1/imports/{import_id}/items`: submit manifest items or upload references. `POST /v1/imports/{import_id}/commit`: explicit commit after validation. `GET /v1/imports/{import_id}`: job/item status and mapping. All are idempotent by import ID and manifest hash.

## 5. Conversations/attachments

Canonical CRUD may be exposed via sync; if direct resources are needed: `GET /v1/conversations`, `GET /v1/conversations/{id}`, `POST/PATCH /v1/conversations/{id}/metadata`, `POST /v1/conversations/{id}/messages`, and explicit `PUT`/`DELETE` archive/favorite operations. No `toggle` endpoints.

`POST /v1/attachments/upload-intent` returns short-lived upload parameters and limits. `POST /v1/attachments/{id}/complete` verifies checksum/scan state. `GET /v1/attachments/{id}` downloads only accepted account-owned objects. `DELETE` creates tombstone; object purge is asynchronous.

## 6. Memory/preferences/export/deletion

`GET/POST/PATCH/DELETE /v1/memory` requires account auth and memory-sync consent; import preview is separate from commit. `GET/PATCH /v1/preferences` returns only allowlisted scoped keys. `POST /v1/export` creates an authenticated export job; `GET /v1/export/{id}` returns status/download. `POST /v1/deletion` creates account deletion request after confirmation and optional export.

## 7. Error codes

Minimum stable codes: `unauthorized`, `forbidden`, `not_found`, `invalid_request`, `email_unverified`, `rate_limited`, `token_reuse`, `device_revoked`, `payload_hash_mismatch`, `duplicate`, `conflict`, `cursor_expired`, `attachment_rejected`, `quota_exceeded`, `consent_required`, `offline`, `provider_denied`, `internal_error`.

## 8. Future clients

Windows, Android, iOS, TV, Auto and Browser consume the same versioned DTOs. Browser may use cookie transport; native clients use OS secure storage. Local `/chat`, `/app-server` and voice routes remain device-internal adapters until a separately approved compatibility layer exists.
