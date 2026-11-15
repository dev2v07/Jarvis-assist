# Account System Phase 1C — Local Implementation

Status: implemented locally; Account Server is not connected.

## Scope

Phase 1C adds an isolated Account Layer without replacing Jarvis Local Mode. It does not register an account, send email, upload history, call a server, or change the production chat database.

Implemented components:

- `backend/account/application/account_coordinator.py` — application boundary for local account state, storage and future auth.
- `backend/account/infrastructure/persistent_store.py` — separate versioned Account System SQLite store.
- `backend/account/infrastructure/dpapi_credentials.py` — Windows Current User DPAPI credential adapter; no plaintext fallback.
- `backend/account/application/auth_client.py` — typed auth boundary and explicit `UnavailableAuthProvider`.
- `frontend/account_ui.py` — Jarvis-styled Account Panel and login, registration, email verification and password recovery screens.
- `frontend/jarvis_ui.py` — existing profile affordance opens Account Panel; legacy local profile editor remains reachable from Settings.

## Product behavior

Jarvis starts directly in `LOCAL_ONLY`. Local AI, history, memory, Knowledge Library, Voice Engine, settings and local models remain independent of Account System. The Account Panel is opt-in and explains that cloud history and cross-device synchronization require a future server and explicit authorization.

The UI validates input and exposes the future flows, but every server operation currently returns a clear “Account Server is not connected” result. No successful login, registration or email delivery is simulated.

## Not implemented

Cloud auth, email, refresh sessions, sync, import upload, cloud attachments, Personal Account Memory sync, Hybrid AI routing, VPS/PostgreSQL/S3 and mobile clients remain future phases.

