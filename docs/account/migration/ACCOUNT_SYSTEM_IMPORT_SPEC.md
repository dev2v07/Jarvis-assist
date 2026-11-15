# Jarvis Account System — Local-to-Account import specification

Статус: design only; import does not run in Phase 1A.

## 1. User flow

1. User creates/connects Personal Account.
2. Client registers this installation and receives `device_id`.
3. Adapter performs read-only inventory without changing SQLite/QSettings/memory.
4. UI shows counts for chats, messages, attachments, selected preferences and memory candidates.
5. UI separately lists Device Only and Excluded categories with reasons.
6. User selects categories/items and confirms.
7. Client creates UUIDv7 `import_id` and immutable manifest hash.
8. Manifest records source IDs, source type, payload hash, attachment SHA-256 and expected size.
9. Server accepts import job and returns per-item status; upload uses protected attachment flow.
10. Client retries pending items safely and polls/pulls results.
11. Server returns canonical IDs, mapping and committed counts.
12. Client stores mapping in the future account-local mapping store; local source rows remain untouched.

## 2. Manifest boundary

Allowed: conversation metadata, message role/content/timestamps/reply references, archive state, normalized favorite intent, selected reactions if contract exists, accepted attachment bytes/metadata, explicitly selected preferences and consented memory items with provenance.

Forbidden by default: local paths, filesystem index, API keys, local models, voice/WAV cache, raw microphone data, system data, unrelated `requests` execution state and shared Knowledge Library. A rejected item is visible to the user, not silently dropped.

## 3. Repeatability

`import_id` is immutable. Server stores manifest hash and import-item key `(account_id, device_id, import_id, source_local_id)`. Repeating the same job returns previous status/mapping. Reusing an ID with a different manifest hash is rejected. A new import with identical text is not deduplicated automatically.

## 4. Partial failure and resume

Jobs have `created`, `validated`, `uploading`, `committing`, `completed`, `partial`, `failed`, `cancelled`. Per-item states include `pending`, `accepted`, `rejected`, `conflict`, `uploaded`, `committed`. Network failure resumes from item status and upload checksum. Local data is never deleted on partial failure. User may retry rejected items after correcting selection; accepted items remain idempotent.

## 5. Attachments

Client computes SHA-256 and size before upload. Server detects MIME independently, checks allowlist/extension, size/quota and scan status. Upload references opaque object key only. Missing/corrupt file becomes a visible item error; no absolute path is sent. Proposed quota defaults remain unapproved: 25 MiB/file, 1 GiB/account, 100 files/message.

## 6. Conflicts

Existing local source and already synced cloud content are not merged by text similarity. If an explicit source mapping already exists, return the existing canonical object. If the same source key carries changed payload, mark conflict and show local/cloud summaries. User chooses import as a new object, replace where permitted, or skip. Local data remains available until separate cleanup confirmation.

## 7. Memory import

Memory inventory is separate from chat inventory. Every candidate shows value, source, source date, provenance and proposed canonical ID. No item enters account memory without memory-sync consent and import confirmation. `facts.json` stays local and unchanged.

## 8. Rollback boundary

Before final commit, canceling the job leaves server objects in pending/garbage-collectable state and leaves local data unchanged. After a committed import, rollback means deleting imported account objects through normal tombstone workflow; it does not mutate or erase local source. Local cleanup requires separate export/confirmation and is outside import commit.
