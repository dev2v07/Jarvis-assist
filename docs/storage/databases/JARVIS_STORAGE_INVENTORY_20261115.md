# JARVIS Storage Inventory — 2026-11-15

Status: CURRENT / READ-ONLY INVENTORY  
Scope: local SQLite and file indexes. No migration was executed in this inventory.

## Findings

| Database | Size | Tables / rows | Owner | Decision |
|---|---:|---|---|---|
| `backend/data/jarvis_state.sqlite3` | 120 KiB | `chat_messages` 86; `chat_sessions` 17; attachments 70; reactions 6; pins 0 | `ChatStore` | Keep as local canonical chat state |
| `backend/data/jarvis.sqlite3` | 40 KiB | `requests` 3 | request/agent persistence | Keep as separate request journal; no entity overlap with chat tables |
| `backend/data/account_system/account_state.sqlite3` | 40 KiB | identity 1; device 1; schema 1; sync metadata 1; outbox/mapping 0 | `PersistentAccountStore` | Keep as local account/sync metadata boundary |
| `data/filesystem_index.db` | 3.0 MiB | `filesystem_index` 12,002 | filesystem indexer | Keep as specialized read/index store |

## Conclusions

- No evidence supports physically merging these databases: they have different owners, schemas and bounded contexts.
- The logical storage contract remains Local Chat + Request Journal + Account/Sync Metadata + Filesystem Index.
- Existing SQLite baseline backups are in `backend/backups/phase4_baseline_20261115_204813/` with manifest and SHA-256.
- Local Account Store uses deterministic connection closing through `contextlib.closing`; ChatStore closes every connection through its context manager.
- No user database was rewritten, migrated or deleted in this inventory.

## Next migration gate

Before any schema consolidation, create copied fixtures for all four stores, define canonical UUID/entity ownership, run an idempotent import twice, verify counts and foreign-key relationships, then rehearse rollback. The current evidence does not justify destructive merging.

## Storage contract and isolated gate

- `backend/services/storage_registry.py` is the canonical path registry. It names the four stores explicitly and does not imply that they share one physical database.
- `backend/scripts/storage_migration_harness.py` uses SQLite Online Backup API against read-only source connections, then verifies `PRAGMA integrity_check`, physical SHA-256 snapshots, logical dump hashes for idempotence and an isolated rollback copy.
- The real project stores passed the gate without writes to their source paths: chat state, request journal, account state and filesystem index were all copied and verified.
- The harness does not migrate schemas or rows. A future logical migration must be implemented as a separate, reviewed operation on copied fixtures first.
