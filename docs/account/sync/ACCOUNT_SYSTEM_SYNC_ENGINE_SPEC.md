# Jarvis Account System — Sync Engine specification

Статус: future implementation contract; no engine exists in current Jarvis.

## 1. Operation envelope

```json
{
  "schema_version": 1,
  "operation_id": "uuidv7",
  "account_id": "from_token",
  "device_id": "registered-device",
  "entity_type": "conversation|message|attachment|favorite|preference|memory",
  "entity_id": "uuidv7-or-client-id",
  "operation": "create|set|delete|redact|attach",
  "base_revision": 3,
  "client_message_id": "uuidv7-or-null",
  "payload_hash": "sha256:...",
  "payload": {}
}
```

Server derives `account_id` from token and rejects a mismatching body value. The outbox stores request, retry count, next attempt, last error, state and prior server result. Sensitive content is not written to logs.

## 2. Push behavior

1. Local transaction commits an allowed change and an outbox operation together in the future local store.
2. Coordinator sends operations in dependency order: conversation before message, attachment acceptance before message reference where required.
3. HTTPS retry uses bounded exponential backoff with jitter; offline means pending, not failure.
4. Server verifies token/device, payload hash, account ownership, revision and idempotency key.
5. Same `(account_id, operation_id)` + same hash returns the original result (`duplicate`); same ID + different hash is `rejected`.
6. Success returns canonical entity ID, new revision, server sequence and mapping.
7. Conflict returns current revision/entity summary and a typed conflict code; client does not overwrite automatically unless policy says so.
8. Rejected is permanent until user/action changes payload; auth expiry is recoverable after refresh/login.

## 3. Pull behavior

`GET /v1/sync/pull?cursor=<server_sequence>&limit=<n>` returns `changes`, `next_cursor`, `has_more` and schema version. Changes are ordered by server sequence. Each item carries entity ID, operation, revision, origin device and tombstone/redaction state.

Client applies one page atomically to local account cache, records mappings and only then persists `next_cursor`. Crash before commit replays the page safely because changes are revision/idempotency aware. Crash after commit but before cursor persistence replays and no-ops. Cursor gaps or invalidated retention cause a full resync job, never silent skipping.

## 4. Conflict matrix

| Operation | Concurrent behavior |
|---|---|
| message append | client ID/idempotency; same message retry returns original canonical message |
| conversation title | `base_revision`; return conflict with both values; UI merge/choose |
| preference set | explicit key/value with revision; last-write-wins only for approved low-risk keys |
| archive | `set archived=true/false`, revision checked; no toggle |
| favorite | create/delete normalized relation, idempotent; no toggle |
| conversation delete | tombstone wins over stale metadata update; resurrection requires explicit restore contract |
| message delete | tombstone/redaction propagates; stale edit rejected |
| attachment delete | tombstone immediately; offline upload cannot resurrect without new explicit attach |
| memory edit | revision conflict and user review; never silent merge facts |

## 5. Offline and recovery

Outbox survives process restart and network loss. Account Mode can answer from local cache while offline. On reconnect: refresh/re-authenticate, push pending operations, pull from cursor, apply tombstones, then reconcile conflicts. If device is revoked, keep local data available in Local Mode but stop cloud push/pull and show re-registration state.

## 6. Tombstones

Deletes are represented by minimal tombstone `(entity_type, entity_id, account_id, revision, server_sequence, deleted_at)`. Tombstones remain for approved retention and are included in pull. Physical object deletion is separate from metadata tombstone. Backup restore must preserve tombstones or replay an equivalent deletion ledger.

## 7. Not supported

No blind toggles, no rowid-based cloud ordering, no WebSocket-only delivery, no client-selected account ownership, no automatic text deduplication and no direct sync of local absolute paths.
