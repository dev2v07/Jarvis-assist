# Jarvis Account System — Phase 1B implementation

Дата: 2026-11-14  
Статус: реализовано локальное основание; cloud/auth/sync не реализованы.

## 1. Реализованные компоненты

Добавлен независимый пакет `backend/account/`:

- `domain/enums.py` — mode, lifecycle, connection, session, sync and data classification enums;
- `domain/models.py` — `AccountContext`, `AccountIdentity`, `DeviceIdentity`, `SessionStateModel`;
- `domain/contracts.py` — typed local DTOs, inventory, manifest and preview DTOs;
- `domain/ids.py` — stdlib-only UUIDv7 generator/validator for transient import IDs;
- `application/account_context.py` — safe LocalOnly provider and guarded context state machine;
- `application/mode_coordinator.py` — UI-independent mode snapshot facade;
- `application/local_data_adapter.py` — application boundary around read-only reader;
- `application/inventory_service.py` — inventory service;
- `application/canonical_mapper.py` — source-to-canonical import manifest mapper;
- `application/import_preview_service.py` — read-only preview service;
- `ports/identity_store.py` — identity port and in-memory test store;
- `ports/mapping_store.py` — mapping port and in-memory test adapter;
- `ports/outbox_store.py` — future outbox port and in-memory test adapter;
- `ports/credential_store.py` — future OS-protected credential port only;
- `infrastructure/local_sqlite_reader.py` — SQLite `mode=ro` reader independent of `ChatStore`.

No new production route or composition-root integration was added. This is intentional: Local Mode has no dependency on Account Layer.

## 2. AccountContext behavior

`LocalOnlyAccountContextProvider` returns `LOCAL_ONLY`, local connection, no account ID, no device ID, local session, empty permissions, `NOT_CONFIGURED` sync and available local data. It does not fabricate an account, persist a random identity or interpret `user:danil` as account identity.

`AccountContextService` contains guarded transitions for future real identity: `CONNECTING`, `AUTHENTICATED_DEVICE`, `ACCOUNT_SYNCING`, `ACCOUNT_ONLINE`, `OFFLINE_ACCOUNT`, `AUTH_REQUIRED`, and return to a clean local state. Cloud transitions reject missing account/device/authenticated session.

## 3. ID behavior

Existing local IDs are not rewritten. UUIDv7 is generated only for transient `import_id`/manifest identities in Phase 1B; server-owned account/device/conversation/message IDs are not invented locally. Local values remain `source_local_id`/`client_message_id` in manifest metadata.

## 4. Compatibility boundary

The new package imports no PySide6, FastAPI, AI agent, voice or knowledge module. It can be used by a future UI adapter or mobile client through DTOs. Existing `/chat`, `/app-server`, voice, QSettings, provider and backup behavior were not changed.
