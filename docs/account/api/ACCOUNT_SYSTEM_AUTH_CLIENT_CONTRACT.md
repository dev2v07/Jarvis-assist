# Account Auth Client Contract

`backend/account/application/auth_client.py` defines the provider boundary used by UI/application code. Operations are typed as `AuthResult(ok, data, error)` and errors contain a stable code, user-facing message, retryability and optional details.

Provider operations:

- `register(email, password)`
- `verify_email(email, code)`
- `login(email, password)`
- `refresh_session()`
- `logout()`
- `request_password_reset(email)`
- `confirm_password_reset(email, code, password)`
- `get_account_profile()`
- `list_devices()`
- `revoke_device(device_id)`

`UnavailableAuthProvider` is the only provider used by the current coordinator. It returns `account_server_unavailable` for all operations except local logout, which returns a local success. It never manufactures account ids, sessions, tokens or verified email state.

Future HTTP implementation must translate invalid credentials, unverified email, expired/revoked session, rate limit, server failure and incompatible API version without leaking provider internals to the user. Ownership checks and token rotation remain server responsibilities.

