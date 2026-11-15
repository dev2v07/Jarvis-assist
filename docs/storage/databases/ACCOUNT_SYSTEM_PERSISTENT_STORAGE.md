# Account System Persistent Storage

## Boundary

Account metadata is stored in a separate database at `backend/data/account_system/account_state.sqlite3` when the Account Panel is opened. The existing `backend/data/jarvis_state.sqlite3` is never opened by this store and its schema is unchanged.

## Schema version 1

`account_schema` stores the schema version. The separate database contains:

- `device_identity`: one stable local device identifier, platform and revocation timestamp.
- `account_identity`: the future server account id, email and verification flag. Empty in Local Mode.
- `entity_mapping`: source namespace/local id to canonical id mappings, entity type, account scope, import id, content hash and status.
- `sync_metadata`: cursors and other non-secret synchronization metadata.
- `account_outbox`: operation id, entity information, payload hash, base revision, status, retry count, error and serialized payload.

Passwords and access/refresh tokens are intentionally absent. Tokens belong to the OS credential adapter.

## Safety properties

Each write uses a SQLite transaction. Duplicate operation ids are ignored, mapping keys are idempotent, and the store reopens after process restart. A schema newer than the client is rejected rather than silently rewritten. Corrupt/unavailable storage raises `AccountStoreCorruptError`; Local Mode must remain available because this store is optional.

The current implementation uses a normal SQLite file for metadata/outbox. Sensitive credentials are not stored there. A future review must select the final at-rest protection for non-secret metadata before production sync is enabled; no SQLCipher or new dependency is introduced in Phase 1C.

## Device identity

The coordinator creates one UUIDv7 device id only when the separate Account store has no device row. It is not an account id, does not contain email or hardware serial data, and does not require network access. A future server registration may revoke and re-register this device without rewriting local history.

