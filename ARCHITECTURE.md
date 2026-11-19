# Jarvis — Architecture

Concise entry point for agents. This file is an index, not a replacement for the
detailed architecture documents that already exist in `docs/architecture/`.

## Request path

```
PySide6 UI -> local HTTP/WebSocket API -> services/agents -> storage,
knowledge, provider or voice boundaries
```

## Composition roots

- `backend/main.py` — normal FastAPI composition root and API entrypoint.
- `frontend/launch_jarvis.py` — supported launcher; owns the backend child process,
  waits for `/health`, then starts the desktop UI in the same interpreter.
- `frontend/jarvis_ui.py` — main PySide6 window/HUD and desktop integration layer.
- `backend/account_server/` — separately deployable account/auth service; not part of
  the normal local backend.

## Boundaries

- `backend/services/` — ChatStore, runtime/provider, knowledge, voice, storage, device,
  application services.
- `backend/agents/` — planner, executor, critic and specialized agents.
- `backend/voice_engine/` — STT, VAD, TTS, wakeword and voice-library adapters.
- `backend/account/` — local account/domain/sync boundary.
- `core/` — shared contracts/message-bus and legacy/simple API modules.
- `data/` — knowledge catalogs, voice-response assets, indexes.
- `packaging/` — PyInstaller and Inno Setup recipes.

`KnowledgeSearchService` remains the logical facade over the physical
`voice_responses`, `offline_knowledge` and `knowledge3` roots. Do not merge those
roots or the SQLite stores mechanically.

## Detailed sources

- `docs/architecture/audits/JARVIS_ARCHITECTURE_AUDIT.md` — current architecture audit.
- `docs/architecture/target_design/JARVIS_TARGET_ARCHITECTURE.md` — target architecture.
- `docs/architecture/migration/JARVIS_MIGRATION_PLAN.md` — migration plan.
- `docs/architecture/README.md` — index of audits, target design, dependency maps.
- `docs/DOCUMENTATION_REGISTER.md` — register of project documentation.
- `AGENTS.md` — working instructions for agents (auto-loaded by DeepSeek Harness).

## Agent tooling for this project

- Serena: `serena-jarvis` MCP server, active project `Jarvis`, LSP backend with
  Pyright 1.1.414 for Python (`pyrightconfig.json` at the repo root).
- Project memory files: `ARCHITECTURE.md` (this file), `DECISIONS.md`, `TASKS.md`,
  `HANDOFF.md`; detailed history stays in `docs/HANDOFF.md`.
- Serena memory index: `project_memory` (see `list_memories`).
