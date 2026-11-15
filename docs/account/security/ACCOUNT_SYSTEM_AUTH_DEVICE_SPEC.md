# Jarvis Account System — authentication and device identity

Статус: future contract; no registration, email or token is created in Phase 1A.

## 1. Account lifecycle

Endpoints cover registration, email verification, login, logout, refresh, password reset request/confirm, password change, account profile, export and deletion. Personal Account is the only active model. Future household/team support may add membership/role resources without changing `account_id` semantics.

## 2. Token model

- Password hash: Argon2id; parameters calibrated in isolated deployment and versioned.
- Access token: short-lived (exact TTL requires approval), minimal claims: `sub=account_id`, session/device IDs, scopes, expiry, token version.
- Refresh token: opaque random value, rotating on every refresh, stored only hashed server-side with token family and reuse state.
- Reuse detection revokes the family and requires re-authentication; it creates an audit event.
- Browser transport: HttpOnly/Secure/SameSite cookie; native clients: OS secure storage. Never QSettings, URL, logs or chat payload.

## 3. Device registration

Device registration binds a new UUIDv7 `device_id` to the authenticated account after email/account confirmation. Store platform, client version, user label, created/last-seen/revoked timestamps and optional future public key. Reinstall is a new device unless a future recovery flow explicitly proves continuity.

Device list supports rename, inspect last seen, revoke one, revoke all except current. Revocation invalidates refresh and sync authorization; it does not remotely execute a command or erase local files. Local client switches to offline/local-only state and asks for re-registration.

## 4. Abuse controls

Rate limit registration, login, reset, verification, refresh, device enrollment, import and upload by IP/account/device. Use generic login/reset responses, failed-attempt counters and temporary lockout. Email provider/domain/region remain unresolved; use an SMTP abstraction and do not hard-code a vendor.

## 5. Recovery and lost device

Password reset requires verified email and one-time expiring token. Password change revokes refresh families by policy (safe default: all other sessions). Lost device is revoked from another authorized device; its access tokens stop working, while local data remains under device/user OS protection. Recovery keys/passkeys and E2EE key recovery are future decisions, not v1 behavior.

## 6. Authorization contract

Resource ownership comes from token `account_id` and registered `device_id`; body/query account identifiers are informational and must match or be rejected. Scope examples: `account:read`, `account:write`, `sync:read`, `sync:write`, `attachments:read/write`, `memory:read/write`, `export:create`, `deletion:create`. Server-to-worker jobs use internal scoped credentials, never user refresh tokens.

## 7. Security events

Audit login success/failure, verification, reset, password change, refresh reuse, device enroll/revoke, export, import, memory consent, cloud AI consent and account deletion. Logs must omit passwords, raw tokens, message bodies, local paths and attachment content.
