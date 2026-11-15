# JARVIS — Phase 3.1 Live Runtime Acceptance

Дата: 2026-11-15  
Рабочая директория: `C:\projects\Jarvis`  
Режим: runtime diagnostics only, без исправления исходников и пользовательских данных

## Краткий итог

Результат этапа: **PARTIAL**.

Подтверждено:

- UI запускается и accessibility tree содержит HUD, START, верхние/нижние
  кнопки и системные панели;
- реальный микрофон Minifuse открывается через PortAudio и отдаёт аудиоданные;
- изолированный VoiceRuntime проходит путь start → Silero VAD state → stop;
- контекстный диалог работает через общий VoiceRuntime/ConversationResolver;
- сообщения сохраняются в правильный `chat_id` изолированной временной SQLite;
- повторный stop освобождает voice runtime без зависшей session state.

Не принято:

- screenshot/HUD visual acceptance заблокирован capture timeout;
- живой STT на произнесённой человеком фразе не подтверждён;
- Fish Audio inference и слышимое TTS playback не подтверждены;
- основной live backend на 8000 оказался старым процессом без актуального
  Phase 3 integrity response;
- launcher из venv породил UI-процесс с системным Python 3.11, что требует
  отдельного расследования.

## 1. Защита проекта и состояние Git

- Ветка: `master`.
- HEAD: `c94ce87594ccb976c75e55212ecf54ef936b3096`.
- Рабочее дерево было dirty до начала этапа; зафиксировано 116 modified/
  untracked entries на момент завершения. Существующие изменения не чистились,
  не откатывались и не перезаписывались.
- Commit, push, reset и checkout не выполнялись.
- Основная БД: `C:\projects\Jarvis\backend\data\jarvis_state.sqlite3`.
- Основной `ChatStore` использует этот путь по умолчанию, поэтому live POST через
  UI/API не выполнялся.
- Изолированные проверки использовали только временные каталоги ОС и
  `state.db` внутри них; основной ChatStore не изменялся.

## 2. Процессы и запуск

Команда:

```powershell
backend\jarvis_env\Scripts\python.exe frontend/launch_jarvis.py
```

До запуска существовали:

- PID 4416: `backend/jarvis_env/Scripts/python.exe backend/main.py`;
- PID 10580: `Python311/python.exe backend/main.py`, listener `127.0.0.1:8000`.

Оба процесса оставлены работающими. Запущенный для acceptance launcher получил
PID 12896 и дочерний UI PID 19908; после проверки окно закрыто, эти acceptance
процессы завершены. PID 4416/10580 не останавливались.

### Отклонение единого окружения

Родитель launcher был запущен из `backend/jarvis_env`, но фактическое окно
`Jarvis Assist` было связано с:

```text
C:\Users\Данил\AppData\Local\Programs\Python\Python311\python.exe
```

Accessibility tree был получен, однако это не подтверждает использование
проектного venv самим UI. Это **FAIL/P3**, требующий отдельного root-cause
анализа launcher/Qt process ownership.

## 3. UI и HUD

### Проверка

Accessibility tree реального окна `Jarvis Assist` содержал:

- HUD container;
- `START`;
- 8 `techTool` buttons;
- `CHAT`, `AGENTS`, `FUNCTION`, `HISTORY`;
- 5 `hudPanelIcon` buttons;
- сообщения о состоянии микрофона и доступных возможностей.

Результат inventory: **PASS**.

### Screenshot и геометрия

Вызов screenshot capture завершился:

```text
window capture timed out: timed out waiting on channel
```

Поэтому координаты, размеры, наклоны, hitbox, resize/fullscreen и визуальное
соответствие HUD не принимаются. Accessibility tree не использовался как замена
визуальному доказательству.

Лог запуска также содержит:

```text
Failed to create GLES3 context, fallback to GLES2.
ContextResult::kFatalFailure: Failed to create shared context for virtualization.
```

QtWebEngine окно создаётся, но влияние fallback на все визуальные сценарии не
установлено.

## 4. Read-only live backend

Проверены без изменения состояния:

- `GET /health` → HTTP 200;
- `GET /voice/status` → HTTP 200;
- `GET /voice/models` → HTTP 200;
- `GET /knowledge/integrity` → HTTP 200.

Live `/voice/status` сообщил:

- `enabled=false`, `listening=false` до теста;
- выбран `fish_jarvis`;
- `available=true`, но `ready=false`, `inference_verified=false`;
- локальная библиотека: 246 intents, 2460 responses, 1564 ready, 896 pending.

Live `/knowledge/integrity` не содержал нового Phase 3 поля `status` и вернул
`ok=true` при `58/62`, `11/12`, `4/7`, `3/8`, `5/6` готовых audio records.
Это подтверждает, что listener PID 10580 обслуживает код до Phase 3 integrity
изменения либо не был перезапущен после него. Процесс не останавливался.

## 5. Реальный микрофон и аудиозахват

### Прямой PortAudio capture

Устройство:

```text
Mic/Line/Inst 1-2 (Minifuse 2)
index=1, max_input_channels=2, default_samplerate=44100
```

Тестовый формат runtime:

- samplerate: 16000 Hz;
- blocksize: 512;
- dtype: int16;
- channels: 1;
- latency: high.

За 2.5 секунды получено:

- callbacks: 74;
- bytes: 75,776;
- PortAudio status errors: отсутствуют.

Результат: **PASS — реальный аудиопоток захватывается**.

Содержимое аудио не сохранялось и в лог не записывалось.

### VoiceRuntime isolated start/stop

Создан временный ChatStore и `VoiceSessionManager` с `chat_id=phase31-test-chat`.
После `runtime.start()` через 4 секунды состояние было:

- `enabled=true`;
- `listening=true`;
- `phase=слушаю (Silero VAD)`;
- `last_error` пустой;
- `conversation_worker=true`.

После `runtime.stop()`:

- `enabled=false`;
- `listening=false`;
- `conversation_worker=false`;
- voice session освобождена.

Результат: **PASS — lifecycle и освобождение runtime подтверждены**.

Это не подтверждает распознавание речи: тестовая фраза человеком не
произносилась, `last_transcript` остался пустым.

## 6. Контекстный диалог и chat_id

В изолированном runtime с подменённой только TTS queue выполнен сценарий:

1. `Хочешь спать?`
2. `Точно не хочешь спать?`
3. `А я вот хочу спать`

Получены три различных смысловых ответа через `ConversationResolver`; в очередь
TTS попали ровно три ответа, без второго ответа от другой подсистемы.

Временная SQLite сохранила ровно 6 сообщений в `dialog-test`:

```text
user → assistant → user → assistant → user → assistant
```

Другие chat_id сообщений не получили. Результат: **PASS — логический контекст,
порядок и изолированная persistence подтверждены**.

Сценарии B и C с произнесённым голосом не выполнялись, так как STT-фраза не
была фактически подана в микрофон.

## 7. STT/VAD/TTS

| Компонент | Результат | Доказательство |
|---|---|---|
| PortAudio input | PASS | 74 callbacks, 75,776 bytes, no status errors |
| Silero VAD path | PASS/PARTIAL | runtime entered `слушаю (Silero VAD)` |
| Human speech → transcript | BLOCKED | no spoken test phrase available in controlled run; `last_transcript` empty |
| ConversationResolver | PASS | three sequential isolated responses |
| Fish Audio config | PARTIAL | profile available, `inference_verified=false`, `ready=false` |
| Local TTS package | PASS/PARTIAL | `TTS` import exists in project venv; model load/inference not executed |
| TTS inference | BLOCKED | would load/download/use model or call external provider; no approved budget/test limit |
| Playback heard by user | NOT TESTED | no reliable auditory observation channel |
| Playback device release | NOT TESTED | no TTS playback was started |

No Fish Audio request, model download, WAV generation or voice-cache change was
performed.

## 8. Root-cause registry for Phase 3.1

| ID | Status | Priority | Root cause / symptom | Evidence |
|---|---|---|---|---|
| RT31-001 | CONFIRMED | P2 | Live listener is stale relative to Phase 3 source: `/knowledge/integrity` lacks `status` and still reports `ok=true` with partial groups. | Live GET response vs current source implementation |
| RT31-002 | CONFIRMED | P2 | Launcher invocation from venv resulted in UI process owned by system Python 3.11. | Parent PID 12896 and child PID 19908 command lines |
| RT31-003 | CONFIRMED | P2 | Computer-use screenshot capture cannot acquire Qt window frame. | `window capture timed out` |
| RT31-004 | CONFIRMED | P2 | QtWebEngine cannot create GLES3 virtualization context and falls back to GLES2. | launcher stderr |
| RT31-005 | CONFIRMED | P1 | Fish profile is configured but not inference-verified. | `/voice/status`, `VoiceModelManager.status()` |
| RT31-006 | CONFIRMED | P1 | Human speech-to-STT and audible TTS response remain unaccepted. | no transcript/audio playback evidence |
| RT31-007 | PASS | — | Real input device and VoiceRuntime lifecycle work in isolated run. | PortAudio capture and start/stop result |

## 9. Recommendations for Phase 3.2

1. Do not restart PID 4416/10580 automatically. First define a controlled
   maintenance window or an isolated alternate backend port and verify that
   the exact current source is serving the UI.
2. Trace why the launcher child changes interpreter identity; capture
   `sys.executable`, `sys.prefix` and parent/child command lines at the launcher
   boundary without changing behavior.
3. Use a user-supervised microphone phrase to complete VAD → STT acceptance;
   do not store raw audio.
4. Obtain explicit Fish Audio test-budget approval or choose an already-local
   model with known files before testing inference.
5. Repeat visual acceptance only when a screenshot-capable display channel is
   available; do not accept HUD geometry from accessibility data.

## 10. No-change confirmation

No source code, `.env`, provider configuration, Knowledge Library, WAV,
voice cache, primary SQLite or user chat was changed. Only temporary isolated
SQLite directories and acceptance stdout/stderr under `%TEMP%\jarvis-phase3-1`
were used. The acceptance UI processes created in this run were closed; the
pre-existing backend PIDs 4416 and 10580 were left running.
