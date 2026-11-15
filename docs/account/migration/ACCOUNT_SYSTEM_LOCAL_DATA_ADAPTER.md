# Jarvis Account System — Local Data Adapter specification

Статус: design only. Existing SQLite schema is read-only and unchanged.

## 1. Current local sources

`backend/data/jarvis_state.sqlite3` currently contains `chat_sessions`, `chat_messages`, `chat_reactions`, `chat_pins`, `chat_attachments` and `requests`. The observed database was read using SQLite `mode=ro`; it contained 9 sessions, 68 messages, 70 attachments, 6 reactions and 0 pins at audit time. `requests` is execution-state history, not canonical conversation history.

Current facts from code: session/message IDs are text; messages use `msg_` + UUID hex by default; sessions may use caller-provided IDs; message order uses SQLite rowid plus `created_at`; attachments have `stored_path`; archive/pin/reaction are local state. There is no account/device/revision mapping.

Other sources are separate: QSettings local profile/preferences; `backend/data/facts/facts.json` for local memory; `backend/data/chroma/documents.json` for local documents/context; `data/filesystem_index.db` for filesystem index; local voice/models/cache and backup archives. Only explicitly selected account objects enter import.

## 2. Adapter contract

The adapter has two strictly separated operations:

**Inventory/read:** enumerate sessions, messages, reactions, pins, accepted attachment descriptors, allowlisted preferences and separately memory candidates. It must use a read-only SQLite connection or a frozen export and must not call `ChatStore` methods that initialize, alter, insert, lazily migrate or copy files.

**Export/manifest:** serialize selected objects to canonical import DTOs and produce source IDs, content hashes and attachment SHA-256. It does not delete or rewrite local rows.

The adapter must report `source_kind`, `source_local_id`, source timestamps, role, content, reply reference, archive/favorite state, attachment references and unsupported/excluded reason. It must never export `stored_path`; it may read the file only to hash/upload after explicit selection.

## 3. Mapping rules

| Local source | Canonical target | Mapping |
|---|---|---|
| `chat_sessions.id` | `conversations.conversation_id` | server generates UUIDv7; local value becomes `source_local_id` namespaced by device/import |
| `chat_messages.id` | `messages.message_id` | server generates UUIDv7; local value becomes `client_message_id`/source provenance |
| `chat_messages.chat_id` | conversation source | resolve through session source map; orphan requires review, never guessed |
| `chat_reactions` | reaction/future message metadata | preserve only if approved canonical reaction contract exists |
| `chat_pins` | message favorite/annotation | do not silently map to conversation favorite; explicit policy required |
| `chat_attachments` + safe file | `attachments` | new attachment UUID, object upload, MIME/size/SHA-256 validation; no path |
| session `archived` | conversation archive state | explicit set operation |
| UI profile QSettings | account/profile preferences | preview and explicit selection; local avatar path is not uploaded as path |
| `facts.json` | `memory_items` | separate consent/preview/import, never automatic |
| `requests` | not conversation by default | retain local; export only if a future execution-history contract approves |

No canonical UUIDv7 is retrofitted into current rows in Phase 1A. The mapping is external to current DB and may be held in import job results/outbox metadata later; storage mechanism requires approval.

## 4. Duplicate and failure rules

Identity key: `(account_id, device_id, import_id, source_local_id)` for import items; `(account_id, client_message_id)` for message append. Same manifest hash and import ID returns previous result. Same source ID with different payload hash is a conflict, not an overwrite. Similar text never deduplicates messages.

Partial upload leaves item/job status pending or failed and is retryable. Local data remains untouched. Corrupt/missing attachment is reported as a per-item error; conversation import may continue only if user policy permits a message without attachment reference.

## 5. Local Mode compatibility

When no `AccountContext` exists, current local routes and QSettings continue unchanged. The adapter is passive and must not be on the critical path of local chat response. Account Mode can read local history and enqueue outbox entries, but local display still uses current local IDs until cloud mapping is known.

## 6. Explicit unresolved adapter choices

Approval is needed for mapping persistence location, reaction/pin canonical treatment, whether profile/avatar is synced, whether execution `requests` are exportable, and whether attachments are imported before or after message commit. No choice is implemented here.
