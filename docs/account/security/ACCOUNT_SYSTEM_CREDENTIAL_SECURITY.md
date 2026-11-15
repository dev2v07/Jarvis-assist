# Account System Credential Security

## Current implementation

On Windows, `WindowsDPAPICredentialStore` protects the access and refresh token JSON with Current User DPAPI (`CryptProtectData`). The protected blob is written atomically through a temporary file and replacement. The adapter has no Base64, plaintext or homemade cryptography fallback.

Tokens are not written to QSettings, ordinary JSON, the Account metadata database or diagnostic messages. `clear()` removes the protected file and surfaces removal failures to the caller; Local Mode itself does not depend on credentials.

On non-Windows hosts the adapter reports `CredentialStoreUnavailable`; it does not silently downgrade security.

## Future server session

The future auth client will use short-lived access tokens and opaque rotating refresh tokens. Refresh-token reuse detection, revocation, rate limiting and account recovery belong to the server contract. Logout/revoke must clear locally protected credentials after the server operation or an explicitly documented offline policy.

## Limits

Phase 1C does not implement authentication, email, server sessions, E2EE or cross-platform secure storage. Android/iOS clients must provide platform keystore adapters behind the same port. DPAPI protection is user-profile scoped and is not an account backup mechanism.

