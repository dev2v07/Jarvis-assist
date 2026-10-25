# Jarvis — журнал изменений разработки

Этот файл содержит очереди изменений, проверки после них и точки отката.

## Главные правила работы

1. Каждый слой изменений и каждая очередь правок обязательно записываются в этот файл.
2. Перед сложными или рискованными правками создаётся backup, а его путь и способ восстановления фиксируются здесь.
3. После каждой очереди правок запускаются backend и frontend Jarvis.
4. После запуска проверяется, что backend отвечает, frontend открылся, а пользовательский сценарий доступен для проверки.
5. Если frontend или backend не может запуститься, причина и точный результат фиксируются в этом файле до перехода к следующей очереди.
6. Нельзя считать очередь завершённой без записи проверки и точки отката.

## Правило работы

Каждая очередь изменений должна иметь:

- уникальный номер;
- дату и описание;
- список изменённых файлов;
- проверку запуска приложения;
- проверенные пользовательские сценарии;
- известные ограничения;
- точку отката.

## Очередь 0001 — архитектурное ТЗ и базовая стабилизация

Дата: 2026-10-26

Изменения:

- добавлено целевое ТЗ для desktop, web, smartphone, smart home и smart speaker;
- исправлен запуск агентов через `Agent.start()`;
- голосовой агент сделан необязательным для запуска текстового backend;
- Qt UI переведён на `POST /chat` порт 8000;
- добавлены timeout и проверка HTTP-ошибок в UI.

Файлы:

- `docs/JARVIS_TZ.md`;
- `backend/main.py`;
- `frontend/jarvis_ui.py`.

Проверка:

- синтаксис ключевых backend/core/frontend-файлов: пройден;
- импорт backend: пройден;
- регистрация агентов: пройдена, 15 агентов;
- full runtime smoke-test: пройден частично;
- `GET /health`: HTTP 200;
- `POST /chat` с командой мониторинга CPU: HTTP 200, performance agent выполнил задачу;
- fallback/stub-ответ при недоступном Ollama: работает;
- graceful shutdown через Uvicorn: пройден.

Ограничения:

- `TTS` отсутствует в текущем окружении, поэтому voice agent отключается;
- Ollama и FFmpeg не обнаружены в startup check;
- конфигурационный слой содержит рассинхрон переменных и требует отдельной очереди.
- Ollama недоступен, поэтому критик использовал fallback/stub-поведение после retry.

Откат:

- вернуть `backend/main.py` и `frontend/jarvis_ui.py` к состоянию до очереди 0001;
- удалить `docs/JARVIS_TZ.md`, если ТЗ больше не актуально.

## Очередь 0002 — правила handoff и проверка двух приложений

Дата: 2026-10-26

Изменения:

- в начало HANDOFF добавлены обязательные правила журнала, backup и проверки;
- подтверждено, что сложные очереди должны иметь отдельную точку отката;
- зафиксировано требование запускать backend и frontend после каждой очереди.

Файлы:

- `docs/HANDOFF.md`.

Проверка:

- backend запущен на `127.0.0.1:8000`;
- `GET /health`: HTTP 200;
- frontend запущен отдельным процессом;
- окно `Jarvis Assist` обнаружено в системе.

Ограничения:

- TTS отключён из-за отсутствующей зависимости `TTS`;
- Ollama и FFmpeg не обнаружены.

Откат:

- удалить блок `Очередь 0002` и раздел `Главные правила работы` из `docs/HANDOFF.md`.

## Очередь 0003 — единый runtime configuration contract

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0003-pre-config/`

В backup сохранены исходники backend/frontend и документы, исключая виртуальные окружения, кэш и бинарные модели. Для отката достаточно вернуть содержимое этой папки в рабочие каталоги.

Изменения:

- добавлены общие runtime-параметры API, Ollama, OpenAI-compatible providers и LLM;
- добавлены `CONFIG_HOME`, `STATE_DB_PATH` и `REQUEST_HISTORY_LIMIT`;
- добавлены безопасные `read_runtime_config()` и `update_runtime_config()`;
- настройки сохраняются атомарной заменой временного файла;
- обновлённые значения применяются к текущему процессу без перезапуска;
- `config_service.py` и `state_store.py` теперь используют существующий единый config contract.

Файлы:

- `backend/config.py`;
- `docs/HANDOFF.md`.

Проверка:

- импорт `config_service`: пройден;
- импорт `state_store`: пройден;
- получение settings bundle: пройдено, provider `ollama`;
- py_compile изменённых Python-файлов: пройден;
- backend запущен после финальной записи очереди;
- `GET /health`: HTTP 200;
- frontend запущен после финальной записи очереди;
- окно `Jarvis Assist` обнаружено.

Ограничения:

- текущая конфигурация по умолчанию всё ещё использует Ollama;
- Ollama недоступен в текущем окружении;
- существующие legacy-настройки в `dev.env` требуют отдельной миграции.

Откат:

- восстановить `backend/config.py` из `backups/handoff-0003-pre-config/backend/config.py`;
- удалить добавленный блок `Очередь 0003` из HANDOFF.

## Очередь 0004 — завершение Этапа 0

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0004-pre-stage0/`

Изменения:

- секреты удалены из рабочего `dev.env` и заменены на пустые локальные переменные;
- Picovoice и OpenWeather теперь читаются только из environment;
- добавлены `.gitignore` и `backend/.env.example`;
- зависимости разделены на core и optional;
- добавлены `README.md`, `docs/CANONICAL_STRUCTURE.md` и GitHub Actions syntax-check;
- создан локальный Git baseline;
- исторические поколения сохранены на диске, но исключены из активного Git baseline;
- зафиксирована каноническая структура текущего Jarvis.

Git:

- baseline commit: `75d2400`;
- legacy exclusion commit: `aafffd7`.

Файлы:

- `.gitignore`;
- `README.md`;
- `.github/workflows/jarvis-check.yml`;
- `backend/dev.env`;
- `backend/.env.example`;
- `backend/jarvis_fast.py`;
- `backend/requirements-core.txt`;
- `backend/requirements-optional.txt`;
- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- активный source secret scan: совпадений не найдено;
- синтаксис 42 ключевых Python-файлов: пройден;
- импорт backend и 15 агентов: пройден;
- импорт `config_service` и `state_store`: пройден;
- локальный Git baseline создан;
- backend/frontend будут перезапущены после финальной записи этой очереди.

Ограничения:

- старые backup до удаления секретов содержат исходные значения и не добавлены в Git;
- старые поколения не удалялись, а только исключены из активного baseline;
- Ollama, FFmpeg и TTS остаются внешними ограничениями окружения.

Откат:

- восстановить рабочие файлы из `backups/handoff-0004-pre-stage0/`;
- Git rollback: `git revert aafffd7`, затем `git revert 75d2400` при необходимости полного возврата baseline;
- старые каталоги на диске не затрагивались.

## Очередь 0005 — TECH-A visual scale integration

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0005-pre-tech-a-front/`

Исследование источника:

- Rainmeter skin: `C:\Users\Данил\Documents\Rainmeter\Skins\TECH-A`;
- 59 графических TECH-A-файлов в проекте совпадают с оригиналом по SHA-256;
- native размер основного skin: 710x710;
- текущая анимация колец в Jarvis сохранена как рабочая и не переписана.

Изменения:

- главный HUD увеличен с 520x520 до 710x710;
- окно ассистента увеличено до 1280x850;
- контейнер главного экрана подстроен под native HUD;
- радиус текущих системных индикаторов увеличен пропорционально;
- существующая анимация колец и текущий порядок рендера сохранены.

Файлы:

- `frontend/jarvis_hud.py`;
- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- backend запущен после финальной записи очереди;
- `GET /health`: HTTP 200;
- frontend запущен после финальной записи очереди;
- одно актуальное окно `Jarvis Assist` оставлено открытым;
- визуальная проверка native-scale HUD выполняется пользователем.

Откат:

- восстановить `frontend/jarvis_hud.py`, `frontend/jarvis_ui.py` и `frontend/styles.css` из `backups/handoff-0005-pre-tech-a-front/`.

## Очередь 0006 — orbit indicators, Aero Glass START and TECH-A fonts

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0006-pre-hud-fonts/`

Изменения:

- CPU, RAM, GPU и DISK теперь двигаются по общей орбитальной оси `a2`, не ломая существующую анимацию колец;
- центральная кнопка заменена на стеклянный круг Aero Glass;
- иконка Play заменена на текст `START`, активное состояние показывает `STOP`;
- добавлены glass-gradient, прозрачность, граница и cyan glow;
- шрифты из `TECH-A/SETTINGS` перенесены в `frontend/assets/fonts`;
- в настройки Jarvis добавлен выбор Good Times, Imagine font, HandelGotD, Nasalization и BitDust Two;
- выбранный шрифт сохраняется через `QSettings`.

Файлы:

- `frontend/jarvis_hud.py`;
- `frontend/jarvis_ui.py`;
- `frontend/assets/fonts/*.ttf`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- после финальной записи будут запущены backend и frontend;
- будет проверен `/health`, окно `Jarvis Assist`, START/STOP и экран настроек шрифтов.

Откат:

- восстановить `frontend/jarvis_hud.py`, `frontend/jarvis_ui.py`, `frontend/styles.css` и fonts из `backups/handoff-0006-pre-hud-fonts/`.

