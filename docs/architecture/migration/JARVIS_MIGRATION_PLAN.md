# Jarvis — Architecture Migration Plan

Status: CURRENT  
Last Updated: 2026-11-15  
Replaces: none

План составлен после read-only аудита. Выполненным изменением на текущем проходе считается только dependency injection общего `KnowledgeSearchService` в `VoiceRuntime`; остальные пункты ниже — staged work.

## Phase 0 — evidence lock

- сохранить branch/HEAD/status и список dirty files;
- сделать read-only import graph для backend/frontend/account/knowledge;
- зафиксировать владельцев процессов и портов;
- не менять пользовательские БД, WAV, `.env` и Knowledge roots.

Rollback: отсутствует, потому что этап не изменяет состояние.

## Phase 1 — request/voice consolidation

1. Ввести контракт одного request lifecycle вокруг существующего `KnowledgeSearchService`/`ConversationResolver`.
2. Развести telemetry причин route: command, local knowledge, Ollama, error.
3. Проверить и затем устранить возможное двойное ACK/WAV воспроизведение. **Phase 4: устранено и покрыто тестом.**
4. Свести UI dictation Vosk и backend STT к адаптерному интерфейсу, не удаляя Vosk до acceptance faster-whisper.
5. Проверить `wakeword_engine.py` импортами и runtime ownership; после evidence либо deprecated, либо подключить явно.

Проверка: isolated SQLite, mocked providers, one live microphone scenario, one playback confirmation, no duplicate messages/audio.

## Phase 2 — one backend composition

- сохранить `backend/main.py` как один local entrypoint;
- оставить `account_server` отдельным deployable service пока PostgreSQL/SMTP/OAuth lifecycle не подтверждены для in-process integration;
- при интеграции сначала включить account router behind explicit configuration and health isolation;
- test backend запускать только через env overrides (`JARVIS_API_PORT`, `JARVIS_STATE_DB_PATH`), не превращать его в product backend.

Rollback: feature/config switch возвращает client к external Account API.

## Phase 3 — storage contracts

- составить entity map для `jarvis_state.sqlite3`, `jarvis.sqlite3`, account SQLite и PostgreSQL;
- определить canonical tables and ownership;
- написать migration fixtures against copied databases;
- проверить UUIDv7, client_message_id, operation_id, revisions, tombstones, cursor and idempotency;
- только после isolated acceptance подготовить user-data migration and backup procedure.

Не объединять физические базы автоматически.

## Phase 4 — Bible logical unification

Phase 4 implementation adds `data/Bible/index/catalog.json` as the canonical
read-only source registry. `KnowledgeSearchService` resolves its current
physical sources through this manifest. The JSON/WAV roots remain in place
until a separately backed-up and verified physical cutover; no source files are
deleted by the manifest step.

- canonical ID and metadata schema;
- adapters for `offline_knowledge`, `knowledge3`, `voice_responses`;
- one search/index contract and explicit `NOT_FOUND`;
- duplicate/link/audio readiness report;
- migration dry-run on copies;
- cutover with rollback and deprecated-path telemetry.

Не перемещать и не удалять физические каталоги на этапе проектирования.

## Phase 5 — UI/account acceptance

- map every UI action to callback/API/result;
- keep UI free of provider/storage internals;
- test Local Mode offline;
- test Google OAuth only with configured isolated client and callback;
- test refresh/logout/device revoke and failure states.

## Change classification

| Change | Risk | Current disposition |
|---|---:|---|
| shared `KnowledgeSearchService` injection | Low | implemented and tested |
| remove Vosk | High | prohibited until live STT comparison |
| merge SQLite files | High | migration plan only |
| move Bible directories | High | migration plan only |
| inline Account Server | High | requires deployment/auth review |
| route/telemetry cleanup | Medium | next implementation phase |
| UI callback map | Low/Medium | audit first, then targeted fixes |

## Acceptance gates

Every stage must pass import smoke, targeted tests, `git diff --check`, isolated data checks and a rollback rehearsal before the next stage. No component is removed solely because it is old, duplicated by name, or outside the main import path.
