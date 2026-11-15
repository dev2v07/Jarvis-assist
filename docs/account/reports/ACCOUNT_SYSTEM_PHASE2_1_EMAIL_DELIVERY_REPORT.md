# Account System Phase 2.1 — Email Delivery Report

Date: 2026-11-14

## Implemented

- Extended the existing `SMTPEmailProvider`; no parallel email mechanism was added.
- Added SSL/STARTTLS selection, SMTP timeout, optional authentication and explicit `EMAIL_DELIVERY_ENABLED` behavior.
- Added Yandex 360 configuration fields to `backend/account_server/.env.example`.
- Added sender name/email handling for `JARVIS ASSIST`.
- Added HTML and text alternatives for verification and password-reset emails.
- Added expiring action URLs using `ACCOUNT_PUBLIC_BASE_URL`; localhost URLs are rejected for enabled Yandex delivery.
- Disabled delivery raises an error and never reports a successful send.
- SMTP credentials are loaded only from local environment configuration and are never sent to the frontend or logged.

## Yandex 360 configuration

The intended local configuration is:

```dotenv
ACCOUNT_SMTP_HOST=smtp.yandex.ru
ACCOUNT_SMTP_PORT=465
ACCOUNT_SMTP_USERNAME=jarvis@tandemarketing.ru
ACCOUNT_SMTP_PASSWORD=<Yandex application password, local only>
ACCOUNT_SMTP_FROM_EMAIL=jarvis@tandemarketing.ru
ACCOUNT_SMTP_FROM_NAME=JARVIS ASSIST
ACCOUNT_SMTP_USE_SSL=true
ACCOUNT_SMTP_USE_STARTTLS=false
ACCOUNT_SMTP_TIMEOUT=10
ACCOUNT_EMAIL_DELIVERY_ENABLED=true
ACCOUNT_PUBLIC_BASE_URL=<approved non-local account URL>
```

No local `.env` or SMTP password was present during this run. The password must be entered by the project owner into `backend/account_server/.env`; it is ignored by Git through `*.env`. The password must be a Yandex application password, not the main Yandex ID password.

## Testing

- SMTP adapter unit tests: passed; SSL mode, sender, subjects, HTML/text links and disabled-delivery failure were verified without network transmission.
- PostgreSQL auth flow, Windows HTTP boundary and existing targeted regressions: **28/28 passed**.
- PostgreSQL migration remains applied to the isolated test database.
- Account API health: passed on `127.0.0.1:8080`.
- Mailpit: not started because `axllent/mailpit:v1.21` is not present locally and Docker registry requests failed with EOF. No volume was deleted and no endless pull loop was attempted.

## Real delivery

The authorized delivery attempt to `managment2v@gmail.com` was made through the configured Yandex SMTP adapter. TLS connection to `smtp.yandex.ru:465` succeeded, but SMTP authentication returned **535**. No message was accepted for delivery. The registration transaction rolled back, so no pending test account was left behind.

The most likely cause is an invalid/expired application password or disabled application-password/mail-client access in Yandex. The password field is populated, has no surrounding whitespace or quotes, and was not printed or logged. A second authorized attempt after reloading `.env` returned the same SMTP 535, so delivery remains blocked at Yandex authentication.

## Windows client

The existing HTTP Auth Provider remains opt-in through `JARVIS_ACCOUNT_API_URL`, uses the existing DPAPI credential adapter and preserves `LOCAL_ONLY` when unset or unavailable. No chat, SQLite, Voice Engine, Knowledge Library or MemoryAgent changes were made.

## User action required

1. Create/verify the Yandex 360 application password for `jarvis@tandemarketing.ru`.
2. Enter it locally as `ACCOUNT_SMTP_PASSWORD` in `backend/account_server/.env`.
3. Set an approved non-local `ACCOUNT_PUBLIC_BASE_URL` that leads to the future verification/reset UI.
4. Explicitly authorize a control recipient before any real delivery test.
5. Start Account API with `ACCOUNT_EMAIL_DELIVERY_ENABLED=true` and run the registration/reset test against a separate PostgreSQL database.

## Continued work after SMTP pause

The request to pause this step was honored. No further SMTP attempts were made. The local Account API remains available, the Windows HTTP client boundary remains opt-in, and non-email targeted checks can continue without transmitting messages.

## Final status

**NOT READY — SMTP AUTHENTICATION FAILED**

Reason: Yandex rejected the current application password with SMTP 535. The SMTP implementation, HTTPS tunnel and safe configuration boundary are ready; real delivery and first registration must not be claimed until a newly verified Yandex application password is entered locally.

