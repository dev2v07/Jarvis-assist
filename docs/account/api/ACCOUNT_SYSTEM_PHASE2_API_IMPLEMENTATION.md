# Phase 2 API Implementation

Implemented prefix: `/api/v1`.

| Endpoint | Purpose |
|---|---|
| `POST /auth/register` | Create pending account and send local SMTP verification |
| `POST /auth/verify-email` | Consume one-time verification token |
| `POST /auth/login` | Issue opaque short-lived access and refresh credentials |
| `POST /auth/refresh` | Rotate refresh token and session |
| `POST /auth/logout` | Revoke current session |
| `POST /auth/password-reset/request` | Generic reset response and local email |
| `POST /auth/password-reset/confirm` | Consume reset token and revoke other sessions |
| `POST /auth/password-change` | Change password and revoke other sessions |
| `GET /account/profile` | Current account from bearer session |
| `GET /account/devices` | Current account devices |
| `POST /account/devices/{device_id}/revoke` | Revoke owned device and its sessions |
| `GET /account/sessions` | List owned sessions |
| `POST /account/sessions/{target_id}/revoke` | Revoke owned session |
| `POST /account/sessions/revoke-all` | Revoke all other sessions |

Every protected resource derives ownership from the validated bearer token. Client-supplied account ids are not trusted. Errors use a stable `detail.error.code/message/request_id` shape. Sync, imports, attachments and memory are intentionally absent from Phase 2.

