# Jarvis — Codex Project Instructions

These instructions apply to C:\projects\Jarvis.

## Project shape and architecture

Jarvis is a local Windows AI assistant with a PySide6 desktop client, a local
FastAPI backend, text chat, voice runtime, agents, knowledge catalogs and an
optional account/cloud boundary.

- backend/main.py is the normal FastAPI composition root and API entrypoint.
- frontend/launch_jarvis.py is the supported launcher. It owns the backend
  child process, waits for /health, and starts the desktop UI in the same
  interpreter environment.
- frontend/jarvis_ui.py is the main PySide6 window/HUD and desktop integration
  layer.
- backend/services/ contains ChatStore, runtime/provider, knowledge, voice,
  storage, device and application services.
- backend/agents/ contains planner, executor, critic and specialized agents.
- backend/voice_engine/ contains STT, VAD, TTS, wakeword and voice-library
  adapters and tooling.
- backend/account/ is the local account/domain/sync boundary.
- backend/account_server/ is a separately deployable account/auth service;
  do not assume it is part of the normal local backend.
- core/ contains shared contracts/message-bus code and legacy/simple API
  modules.
- data/ contains knowledge catalogs, voice-response assets and indexes.
- docs/ contains architecture decisions, handoffs, audits, testing and
  operational documentation.
- packaging/ contains PyInstaller and Inno Setup build recipes.

The normal request path is:

  PySide6 UI -> local HTTP/WebSocket API -> services/agents -> storage,
  knowledge, provider or voice boundaries.

Keep KnowledgeSearchService as the logical facade over the physical
voice_responses, offline_knowledge and knowledge3 roots. Do not merge those
roots or the SQLite stores mechanically.

## Technology and runtime

- Python 3.11+ on Windows.
- FastAPI, uvicorn, Pydantic, requests, python-dotenv and Ollama integration.
- PySide6 6.10.2 for the optional desktop client.
- Optional faster-whisper/Silero VAD/TTS/Vosk/OpenCV/torch stacks.
- Ollama is the documented default provider; provider adapters also cover
  OpenAI-compatible, DeepSeek and other configured backends.
- Local stores are SQLite-based; the account server uses a separate
  PostgreSQL-oriented boundary.
- Dependencies are split between backend/requirements-core.txt,
  backend/requirements-optional.txt and backend/requirements-device.txt.
- There is no pyproject.toml or setup.py; do not invent one as part of an
  unrelated change.

## Serena workflow

Before a substantial coding task:

1. Activate C:\projects\Jarvis in Serena and read Serena's initial
   instructions for the current session.
2. Read the relevant Serena Memory entries, starting with mem:core and then
   focused module memories such as mem:backend/core or mem:frontend/core.
3. Read the applicable project documents, especially the current architecture
   audit and the relevant HANDOFF.
4. For complex work, study only the relevant modules through Serena. Use file
   listings, pattern search, symbol overviews, symbol/reference search and
   declaration lookup where available. Do not reread the whole repository.
5. If LSP is unavailable, report that limitation and use bounded pattern/file
   inspection; do not claim symbol-level verification that was not performed.

Prefer Serena's semantic tools for code discovery and structure-aware edits.
Use ordinary file tools for small, clearly scoped edits or non-code documents.
Never use Serena Memory as a substitute for checking current source behavior.

### Python LSP configuration

- Serena uses the LSP backend with the `python` language-server identifier;
  Serena's `python` backend is the official Pyright integration.
- Project configuration is in `.serena/project.yml`; it pins the Pyright
  package version and indexes `backend/`, `frontend/` and `core/`.
- `pyrightconfig.json` points Pyright at Python 3.11 and the project virtual
  environment `backend/jarvis_env`; generated directories and both project
  environments are excluded from indexing.
- `uv`/`uvx` provide Serena's managed language-server dependency. Do not add
  Pyright to Jarvis runtime requirements unless the application itself needs
  it.
- After changing Serena configuration, restart the Serena MCP process and
  activate the project again before judging LSP behavior.
- Validate the real LSP operations: symbols overview, symbol lookup,
  declaration lookup and reference lookup. Pattern search is not an LSP
  substitute.
- Current known working pin: Pyright `1.1.414`; project interpreter:
  `backend\\jarvis_env\\Scripts\\python.exe` (Python 3.11.9).
- Configuration backups are kept under `.serena/config-backups/`; preserve
  them when troubleshooting or reverting LSP setup.

## Dependency and refactoring checks

Before refactoring an existing module or changing a public contract:

- inspect its imports, callers, references and route/UI consumers through
  Serena;
- inspect the relevant requirements files, environment/configuration keys and
  storage/provider boundaries;
- inspect focused tests and current handoff/audit notes;
- identify whether the change crosses backend/frontend, voice, account,
  storage, provider or packaging boundaries;
- preserve backward compatibility or update every confirmed consumer;
- avoid removing a duplicate-looking component until its runtime ownership and
  references are proven.

Do not begin a broad refactor from a filename search alone.

## Safe change rules

- Do not delete, reset, overwrite, stash, or revert user changes.
- Treat existing modified and untracked files as user-owned unless explicitly
  proven otherwise.
- Before editing an overlapping file, inspect its current diff and isolate the
  requested change.
- Do not stop or replace a process on port 8000 during diagnostics without
  explicit authorization.
- Do not migrate, merge, delete or rewrite databases, user data, models, WAV
  files or knowledge roots without a separately confirmed scope.
- Keep Windows autostart user-scoped through HKCU; do not assume administrator
  rights.
- Preserve confirmation-first behavior for filesystem, device, DAW, backup and
  other potentially destructive operations.
- Do not claim live microphone, audible TTS, provider availability, installed
  EXE behavior or visual acceptance from static checks alone.

## Tests and verification

Use the same interpreter for backend and desktop checks. The documented basic
checks are:

    python -m compileall -q backend frontend core
    $env:PYTHONPATH = "backend"
    python -m unittest discover -s backend/tests -p "test_*.py" -v

When frontend code changes, include the applicable tests under frontend/tests.
For API/runtime changes, add focused bounded smoke checks and do not replace
live-device acceptance with unit tests. Before handoff, inspect:

    git diff --check
    git status --short --branch

Distinguish checks run during the current task from historical results
recorded in documentation.

## Documentation, HANDOFF and Memory

- Read the current relevant handoff before continuing an unfinished workstream.
- Update docs/HANDOFF_ASSIST.md or another handoff only when the task creates
  a meaningful checkpoint, decision, verification result or next action.
- Do not duplicate an existing audit, handoff or Serena Memory entry. Prefer a
  concise link/reference and record only new durable information.
- Keep historical claims marked as historical; never promote an unverified
  observation to a current fact.
- Update Serena Memory only with stable, non-obvious project knowledge that
  will prevent future rediscovery. Follow mem:memory_maintenance.
- Before writing Memory, check existing entries and add/update only the
  affected focused memory. Preserve existing knowledge and references.
- After Memory changes, run serena memories check from the project root.

## Release caution

Jarvis is a pre-release project. Installed EXE launch, uninstall, reboot and
autostart cleanup remain separate release gates. Full faster-whisper/TTS live
acceptance and account/cloud deployment are not implied by passing automated
tests.

