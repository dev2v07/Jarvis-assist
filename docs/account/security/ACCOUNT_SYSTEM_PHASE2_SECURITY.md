# Phase 2 Security

- Passwords use Argon2id through `argon2-cffi`; the server stores only encoded password hashes.
- Access and refresh credentials are opaque random values. Only SHA-256 digests are stored in PostgreSQL; raw refresh values are returned once.
- Refresh rotation creates a replacement session. Reuse of a revoked refresh token revokes the complete token family and emits a security event.
- Verification and reset tokens are one-time, expiring and stored only as digests.
- Login and registration have an in-process rate limiter suitable for local development; a shared production limiter remains required before deployment.
- Device revocation invalidates all sessions for that device and does not erase local Jarvis data.
- Security events exclude passwords, raw tokens, message bodies, local paths and attachment content.
- TLS, secret management, reverse proxy policy, distributed rate limiting and external email provider remain deployment work.

No E2EE or cloud sync is implemented. Local Mode remains independent of this server.

