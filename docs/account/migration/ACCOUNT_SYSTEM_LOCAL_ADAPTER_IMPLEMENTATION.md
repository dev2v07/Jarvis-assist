# Jarvis Account System — Local Adapter implementation

## 1. Read-only guarantees

`ReadOnlySQLiteReader` opens the configured database using a SQLite URI with `mode=ro`. It does not import or instantiate `ChatStore`, does not execute DDL/DML, does not set persistent PRAGMAs, and does not copy/move attachments. Connections are explicitly closed with `contextlib.closing`.

The reader never returns `stored_path` in a DTO. It may inspect the path internally to classify an attachment as available, missing or corrupt and may calculate SHA-256 only when `compute_attachment_hashes=True` is explicitly requested.

## 2. Current schema mapping

| Current table | Phase 1B behavior |
|---|---|
| `chat_sessions` | read into `LocalConversationDTO`; archive retained; current `pinned` is not silently mapped to favorite |
| `chat_messages` | read into `LocalMessageDTO`; local ID retained as source/client identity |
| `chat_attachments` | read metadata and file availability/hash; no path exported |
| `chat_reactions` | counted/read for diagnostics; canonical sync semantics remain unsupported |
| `chat_pins` | counted/read for diagnostics; not conflated with conversation favorite |
| `requests` | explicitly excluded from conversation import |

Messages whose `chat_id` has no known session are marked excluded/orphan in the DTO and manifest. They are not attached to an arbitrary conversation.

## 3. Real database observation

Using the new adapter against `backend/data/jarvis_state.sqlite3` in read-only mode produced:

```text
conversations: 9
messages: 68
attachments: 70
reactions: 6
pins: 0
archived: 0
inventory errors: 0
manifest items: 153
excluded categories: 5
```

This is an observation of the current local state, not a schema contract or import commit.

## 4. Error behavior

Missing database/table/query errors raise `LocalDatabaseReadError` rather than silently returning an empty inventory. Missing/corrupt/orphan attachment records remain visible in `errors` and per-item status. The adapter does not repair or migrate them.

## 5. Mapping and outbox ports

`InMemoryMappingStore` and `InMemoryOutboxStore` exist only to prove future interfaces and tests. They are not durable, encrypted, account storage and are not wired into the application. `CredentialStore` is a protocol only; tokens are not stored anywhere by Phase 1B.
