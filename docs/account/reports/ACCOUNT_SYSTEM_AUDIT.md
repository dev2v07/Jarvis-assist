# Jarvis: аудит текущей архитектуры для системы аккаунтов

Дата аудита: 2026-11-14  
Режим: только чтение. Production-код, существующая схема БД, конфигурации и процессы не изменялись.

## 1. Границы и статус достоверности

Ниже разделены факты, подтвержденные исходниками/файлами, и ограничения, выявленные по этим фактам. Файлы Knowledge Library, voice library и WAV не изменялись. В рабочем дереве до аудита уже были незакоммиченные изменения в README, voice/runtime и knowledge-направлении; они не являются результатом этого аудита.

## 2. Карта проекта

| Область | Фактическая реализация | Подтверждение |
|---|---|---|
| Язык | Python 3.11+ | `README.md`, `backend/requirements*.txt` |
| Desktop UI | PySide6, HUD и chat UI | `frontend/launch_jarvis.py`, `frontend/jarvis_ui.py`, `frontend/jarvis_hud.py` |
| Local backend | FastAPI + Uvicorn, loopback `127.0.0.1:8000` | `backend/main.py:810-817`, `README.md` |
| Core | MessageBus, Planner/Executor/specialist agents/Critic | `backend/core/message_bus.py`, `backend/agents/*`, `backend/main.py` |
| Transport boundary | JSON-RPC 2.0 POST, WebSocket, polling events | `backend/services/app_server.py`, `backend/main.py:663-692` |
| Config | `.env`/`dev.env`, environment variables, runtime `.env` | `backend/config.py`, `backend/.env.example`, `backend/services/config_service.py` |
| Local settings | Qt `QSettings` в frontend | `frontend/jarvis_ui.py`, `frontend/profile_dialog.py` |
| Background work | voice threads, TTS queue, async agent pipeline, backup scheduler | `backend/services/voice_runtime.py`, `backend/voice_engine/tts_queue.py`, `backend/agents/backup_agent.py` |
| Packaging | PyInstaller/Inno Setup scripts | `packaging/`, `JarvisAssistant.spec`, `JarvisBackend.spec` |

Основной запуск: `python frontend/launch_jarvis.py`. Launcher ожидает `GET /health`, затем открывает desktop UI. Backend сам запускается как `main:app` на порту 8000. Есть также исторические минимальные FastAPI entry points в `core/api.py` и `core/jarvis_api.py`; они не являются основным текущим pipeline и используют отдельные `/command`.

## 3. Текущий поток запроса

```text
PySide6 UI / voice runtime
        -> HTTP localhost /chat или локальный app-server
        -> FastAPI backend/main.py
        -> ChatStore сохраняет user message в SQLite
        -> MessageBus -> Planner -> Executor -> specialist/Critic
        -> local response / Ollama / provider adapter / tool
        -> ChatStore сохраняет assistant message
        -> UI получает ответ и runtime events
```

`backend/core/contracts.py` уже содержит JSON-совместимые `RequestContext`, `AgentResult`, `RuntimeEvent`, `ProviderStatus`. В `RequestContext` есть session/client/platform/mode/locale, но это не account identity и не authorization boundary.

## 4. Диалоги и история

`backend/services/chat_store.py` создает SQLite-схему:

- `chat_sessions(id, title, pinned, archived, created_at, updated_at)`;
- `chat_messages(id, chat_id, role, content, attachments_json, reply_to, created_at)`;
- `chat_reactions(message_id, reaction, actor, created_at)`;
- `chat_pins(message_id, actor, created_at)`;
- `chat_attachments(attachment_id, message_id, original_name, stored_path, media_type, size, created_at)`.

Идентификаторы: session/chat ID передается клиентом или генерируется UUID; message ID генерируется как `msg_` + UUID; request/turn IDs существуют отдельно в runtime. Это хорошая основа для будущего sync, но сейчас IDs не принадлежат пользователю, устройству или серверной tenant boundary.

Поддержаны создание, список, переименование, pin, archive, удаление сессии, удаление сообщения, pagination по rowid, reactions, message pins и attachment cache. Контекст LLM формируется в `backend/main.py` через последние 12 сообщений текущего `chat_id`. Полнотекстового поиска по истории нет; есть только чтение диапазона/ID. Долговременное восстановление диалога работает только внутри локальной БД конкретной установки.

Фактические локальные строки на момент аудита (прочитаны через SQLite `mode=ro`, содержимое сообщений не раскрывалось): `backend/data/jarvis_state.sqlite3` содержит 9 sessions, 68 messages, 70 attachments, 6 reactions и 0 message pins. Это наблюдение состояния, а не контракт приложения.

Локальные API без auth middleware:

- `GET /chat/sessions`, `POST /chat/sessions`, patch/pin/archive/delete;
- `POST /chat`, `GET /chat/history`, `GET /api/messages`, `DELETE /api/messages/{id}`;
- media, reaction и pin endpoints;
- `/app-server/rpc`, `/app-server/ws`, `/runtime/events`.

Следствие: если такой backend будет выставлен за пределы loopback без отдельного защищенного gateway, любой доступ к endpoint может стать доступом к данным всех локальных chat IDs.

## 5. Базы и локальное хранение

Текущий основной chat/request DB: `backend/data/jarvis_state.sqlite3`, путь задается `STATE_DB_PATH` в `backend/config.py`. `ChatStore` и `SQLiteStateStore` используют один файл, включают WAL и создают таблицы через `CREATE TABLE IF NOT EXISTS`; миграционный framework не обнаружен. `SQLiteStateStore` дополнительно хранит execution requests в таблице `requests` (events/plan/result/error JSON).

Отдельно существует `data/filesystem_index.db` с таблицей `filesystem_index(name, path, drive, object_type, last_seen, last_opened)`; это индекс файловой системы, не account/chat store.

JSON/file storage:

- `backend/data/facts/facts.json` — извлекаемые facts памяти;
- `backend/data/chroma/documents.json` — documents/context, несмотря на имя пути фактический адаптер читает JSON;
- `data/voice_responses/*.json` — offline conversational catalog и selection state;
- `data/applications.json` — локальный каталог приложений;
- `backend/uploads/chat-media/` — локальная копия вложений.

Backup: `BackupAgent` периодически/явно архивирует `CHROMA_PATH`, `FACTS_PATH`, `UPLOAD_DIR` и `STATE_DB_PATH` в `backups/`. Это локальный filesystem backup, без account-aware retention, encryption или remote restore protocol.

## 6. Профиль, настройки и память

`frontend/profile_dialog.py` хранит в Qt `QSettings` поля `profile_display_name`, `profile_username`, `profile_avatar_path`, `profile_email`, `profile_age`, `profile_address`. UI показывает фиксированный `entity_id: user:danil` и роль `Пользователь`. Это локальный профиль одного пользователя, не authentication account; email не подтверждается, пароль/сессия отсутствуют.

В `frontend/jarvis_ui.py` также сохраняются UI/runtime preferences, включая history/diagnostics flags, page size, appearance, hardware and provider settings. `backend/config.py` читает environment/runtime `.env` и позволяет менять LLM settings через `/settings/llm`; секреты маскируются только при выдаче config, но runtime storage остается локальным `.env`.

`MemoryAgent` (`backend/agents/memory_agent.py`) извлекает regex-based facts из текста и вызывает `store_fact()`; `storage_service.py` сохраняет строки в один общий `facts.json`, deduplicates exact strings и возвращает первые пять substring matches. User ID, chat ID, consent, provenance, confidence, deletion lifecycle и per-device scope отсутствуют. Долговременная память отделена от chat history физически, но не отделена по пользователю.

## 7. AI Engine

`backend/services/llm_service.py`, `provider_adapters.py` и runtime config поддерживают local Ollama по умолчанию (`127.0.0.1:11434`), OpenAI/OpenAI-compatible/DeepSeek adapters и stub; Claude/FreeLLMAPI отмечены как не подключенные. `backend/main.py` собирает history context и передает его в Planner/agents. Локальные модели и filesystem tools зависят от текущего Windows host. Серверная архитектура в будущем должна передавать на облачный service только авторизованный account conversation context, а local-only actions и Ollama оставлять device-side, если пользователь этого не меняет.

## 8. Voice Engine

`backend/services/voice_runtime.py` владеет microphone thread, wake words, conversation queue и TTS queue; `backend/voice_engine/stt.py` описывает faster-whisper push-to-talk path, а runtime использует локальный voice loop/fallback. `backend/voice_engine/vad.py` — Silero VAD/RMS fallback. TTS находится в `tts.py`/`tts_queue.py`, готовые ответы и WAV — в `backend/voice_engine/sound` и `data/voice_responses`. Voice runtime вызывает response router/local response/offline knowledge/LLM paths, но не формирует account identity. Voice files и generation pipeline в этот аудит не изменялись.

## 9. Внешние API и интеграции

Обнаружены requests к local backend, Ollama/OpenAI-compatible providers, OpenWeather, `ip-api.com`, web/search-related tools и Windows/local application integrations. Ключи читаются из environment/runtime env (`HEL_*`, `OPENWEATHER_API_KEY`, `PICOVOICE_TOKEN`, `OPENAI_TOKEN`); значения секретов в отчет не включены. Auth integration для Jarvis account отсутствует. Loopback endpoints сейчас предполагают доверенную локальную среду.

## 10. Ключевые ограничения для account system

1. Нет user/account foreign key у sessions/messages/facts/settings.
2. Клиент может выбрать произвольный `chat_id`; ownership check отсутствует.
3. Нет серверного durable sync cursor, idempotency key, operation log или conflict model.
4. `created_at`/`updated_at` генерируются SQLite current time; нет server revision/version per entity.
5. Нет search index по сообщениям.
6. Нет account auth, email verification, password reset, session/device management.
7. Профиль и memory имеют fixed single-user semantics.
8. Local backup не является защищенным cloud backup.
9. Runtime events in-memory deque (до 256) и не являются durable event history.
10. Existing app-server transport полезен как future protocol boundary, но его методы пока работают с локальным ChatStore и не имеют remote auth.

## 11. Аудит завершен без вмешательства

Не запускались migrations, backend/frontend processes, voice generation, Ollama probes, tests that could initialize state, installer/build/restart actions. Созданы только отчетные документы Phase 0.
