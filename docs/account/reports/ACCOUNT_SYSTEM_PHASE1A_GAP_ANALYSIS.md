# Jarvis Account System — Phase 1A gap analysis

## 1. Existing and reusable

| Existing component | Reuse | Gap |
|---|---|---|
| `core/contracts.py` | UI-independent envelope foundation | add account/device/mode/policy only through versioned future contract |
| `ChatStore` | local conversation CRUD and attachment descriptors | mutating init, no ownership/revision/outbox/tombstones, local IDs |
| `AppServer` | local lifecycle transport concept | local-only, no remote auth/durable events/sync cursor |
| `main.py` routes | current Windows integration | must remain unchanged; future adapter boundary needed |
| QSettings/profile | Local Mode profile/preferences | not auth; paths/secrets and fixed `user:danil` semantics |
| `state_store.py` | local execution request state | not account conversation sync; current init mutates DB |
| BackupAgent | local backup source inventory | no encrypted cloud backup/restore/account retention |
| runtime/provider adapters | local AI/provider status | no Hybrid AI consent gate or cloud data minimization |

## 2. Components to create later

AccountContext, secure credential store, device/session client, Local Data Adapter, external mapping store, durable outbox, Sync Coordinator, versioned Account API client, import coordinator, attachment uploader, memory consent store/API, AI policy gate, auth/account/sync cloud modules, PostgreSQL/S3 repositories and worker jobs.

## 3. Isolation requirements

Keep VoiceRuntime, STT/TTS/WAV, Knowledge Library, `facts.json`, Chroma/documents, Ollama/local models, filesystem/application tools and existing `/chat` behavior outside cloud backend. Cloud must never receive local paths or invoke arbitrary Windows commands. Account Client stays independent of PySide6.

## 4. Contradictions/ambiguities

1. **All Sync vs memory consent:** approved decision says All Sync, while Personal Memory is separately consented. Resolution used here: All Sync includes all approved conversation/settings classes; memory is a separately gated class and is not uploaded until consent.
2. **Favorites in earlier proposal:** `conversations.favorite` appeared as a possible field and `favorites` relation existed. Resolution: normalized `favorites` is sole truth; DTO boolean is derived.
3. **Phase 0 roadmap vs Phase 1A:** earlier roadmap went directly from design to local identity. Resolution: Phase 1A is inserted as readiness/specification gate before implementation.
4. **Current toggle APIs vs sync:** current `/pin`/archive/reaction behavior is toggle-based. Resolution: future account API uses explicit set/delete operations; current APIs remain unchanged.
5. **Local IDs vs UUIDv7:** current IDs include `default` and `msg_` IDs. Resolution: server canonical IDs are UUIDv7; current values are namespaced source/client IDs.
6. **Current ChatStore lazy migration:** `_row()` can copy attachment files and `__init__` can alter schema. Resolution: adapter uses non-mutating read-only reader/export boundary.
7. **Current profile email vs verified email:** QSettings email is editable text. Resolution: it is a local profile candidate, never proof of account verification.

## 5. Blocking decisions before implementation

Mapping persistence location, reaction/pin import policy, avatar/profile sync, exact attachment quotas/MIME allowlist, retention, email/domain/VPS region, cloud AI provider/budget, token TTLs, recovery policy, server migration tool and local secure-storage mechanism remain approval items. No production code should be written as if these are final.
