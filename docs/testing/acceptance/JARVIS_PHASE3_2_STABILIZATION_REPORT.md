# JARVIS — Phase 3.2 Stabilization Report

Дата: 2026-11-15  
Результат: **PARTIAL**  
Режим: исправление подтверждённых проблем и контролируемая runtime-проверка

## Итог

Выполнены безопасные исправления runtime isolation:

- backend уважает `JARVIS_API_PORT` вместо жёсткого `8000`;
- ChatStore уважает `JARVIS_STATE_DB_PATH`, production default не изменён;
- CORS учитывает выбранный тестовый порт;
- launcher использует `JARVIS_API_BASE_URL`/`JARVIS_API_PORT`;
- UI все API-вызовы направляет через единый `API_ROOT`, сохраняя default
  `http://127.0.0.1:8000`;
- добавлен непубличный диагностический лог launcher с `sys.executable`,
  `sys.prefix`, `sys.base_prefix` и cwd без секретов.

Это позволяет поднимать актуальный backend на отдельном порту и отдельной
SQLite, не затрагивая listener 8000 и пользовательскую историю.

## Git и процессы

- Ветка: `master`.
- HEAD: `c94ce87594ccb976c75e55212ecf54ef936b3096`.
- До работы дерево было dirty; существующие modified/untracked файлы сохранены.
- Commit, push, reset и checkout не выполнялись.
- Pre-existing backend PID 4416 и listener PID 10580 не останавливались.
- Временный backend Phase 3.2 запускался на 18081 и был остановлен после теста.
- Основная БД не использовалась в state-changing сценариях.

## Runtime isolation

Тестовый backend запускался с:

```text
JARVIS_API_PORT=18081
JARVIS_STATE_DB_PATH=%TEMP%\jarvis-phase32-runtime\isolated.sqlite3
```

Проверены:

- `GET /voice/status` → HTTP 200;
- `GET /knowledge/integrity` → HTTP 200, `status=PARTIAL`;
- `GET /settings/llm` → HTTP 200;
- `GET /health` был запрошен до полной готовности процесса и получил один
  connection-refused; последующие endpoints отвечали штатно. Это startup timing,
  а не принятая ошибка API.

Актуальный integrity response содержит `READY/PARTIAL` и `audio_groups`, в
отличие от legacy listener на 8000, который всё ещё возвращает только `ok=true`.

## Launcher root-cause result

Прямой диагностический запуск проектного interpreter подтвердил:

```text
sys.executable = C:\projects\Jarvis\backend\jarvis_env\Scripts\python.exe
sys.prefix     = C:\projects\Jarvis\backend\jarvis_env
sys.base_prefix= C:\Users\Данил\AppData\Local\Programs\Python\Python311
```

Наблюдение child process с образом системного Python 3.11 является особенностью
Windows venv redirector; фактический `sys.executable` внутри venv остаётся
проектным. Это подтверждено новым diagnostic log. Доказательств запуска UI на
чужом virtualenv после этой проверки нет.

## UI/API binding

UI теперь вычисляет:

```python
API_ROOT = os.getenv("JARVIS_API_BASE_URL", "http://127.0.0.1:8000")
```

Все найденные UI endpoints переведены на `API_ROOT`, включая chat, voice,
settings, media, devices, backups, runtime events и embedded chat page.

Прямой повторный UI launch с отдельным портом не завершён: текущая среда
заблокировала запуск фонового launcher-процесса политикой terminal tool. Поэтому
UI→18082 не объявляется PASS.

## Voice runtime

Существующие Phase 3.1 результаты остаются действительными:

- Minifuse input: 74 callback-а, 75,776 байт, ошибок PortAudio нет;
- VoiceRuntime: `слушаю (Silero VAD)` → штатный stop;
- ConversationResolver и изолированная chat persistence проходят;
- Fish `fish_jarvis`: `available=true`, `ready=false`,
  `inference_verified=false`;
- локальный пакет `TTS` в venv импортируется, но model load/inference не
  запускался и ничего не скачивалось.

Реальная человеческая фраза через STT и слышимое TTS не подтверждены. Для этого
нужно запустить изолированный UI/backend и получить короткую фразу пользователя;
аудио нельзя заменить mock-текстом.

## UI/HUD

Из Phase 3.1 подтверждено наличие HUD accessibility elements: START, 8 tech
buttons, CHAT/AGENTS/FUNCTION/HISTORY и нижняя группа кнопок.

Визуальный screenshot capture по-прежнему заблокирован:

```text
window capture timed out: timed out waiting on channel
```

QtWebEngine продолжает сообщать GLES3 virtualization fallback. Security,
sandbox и site isolation не отключались. Геометрия HUD, hitbox и визуальные
артефакты не объявляются принятыми.

## Verification

- `py_compile` изменённых source files: PASS;
- launcher interpreter diagnostic: PASS;
- isolated backend import with port/db env: PASS;
- isolated backend `/knowledge/integrity`: PASS (`PARTIAL`);
- unittest regression: **56/56 PASS**;
- `ResourceWarning`: отсутствуют;
- `git diff --check`: PASS.

Общий `compileall backend frontend` отдельно обнаружил SyntaxError в стороннем
повреждённом файле `backend/device_env/site-packages/mediapipe/.../text_embedder_test.py`.
Изменённые исходники компилируются; зависимости не исправлялись.

## Phase 3.2 status matrix

| Area | Status | Comment |
|---|---|---|
| Test backend isolated port | PASS | 18081, separate SQLite |
| Current integrity implementation | PASS | `PARTIAL` and audio groups |
| Production listener 8000 refresh | BLOCKED | pre-existing process not stopped |
| Launcher interpreter identity | PASS | venv `sys.executable` confirmed |
| UI configurable backend root | PASS | source changed and compiles |
| UI connected to isolated backend | BLOCKED | terminal launch policy prevented repeat |
| Physical microphone capture | PASS | Phase 3.1 Minifuse evidence |
| VAD lifecycle | PASS/PARTIAL | Silero state observed, no human speech segment |
| Human speech → STT | BLOCKED | requires controlled spoken phrase |
| ConversationResolver/context | PASS | isolated real runtime path |
| TTS inference | BLOCKED | Fish unverified; local model not loaded |
| Audible playback | NOT TESTED | no inference started |
| HUD screenshot/geometry | BLOCKED | capture channel timeout |

## Changed files in Phase 3.2

- `backend/config.py`
- `backend/main.py`
- `frontend/launch_jarvis.py`
- `frontend/jarvis_ui.py`
- `docs/JARVIS_PHASE3_2_STABILIZATION_REPORT.md`
- `docs/JARVIS_RUNTIME_BUG_REGISTRY.md`
- `docs/HANDOFF_ASSIST.md`

Другие modified/untracked файлы были pre-existing и не очищались.

## Safety confirmation

Не изменялись `.env`, секреты, WAV, Knowledge Library, primary SQLite и
пользовательские чаты. Не выполнялись миграции, платные Fish Audio requests,
массовая генерация или commit/push/reset.

Jarvis пока нельзя считать полностью готовым к ежедневному голосовому
использованию: STT по реальной речи, TTS inference и слышимое воспроизведение
остаются неподтверждёнными.
