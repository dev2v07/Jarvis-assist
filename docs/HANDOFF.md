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
- backend запущен после финальной записи очереди;
- `GET /health`: HTTP 200;
- frontend запущен после финальной записи очереди;
- окно `Jarvis Assist` обнаружено, старое дублирующее окно закрыто;
- START/STOP и экран настроек шрифтов доступны для визуальной проверки пользователем.

Откат:

- восстановить `frontend/jarvis_hud.py`, `frontend/jarvis_ui.py`, `frontend/styles.css` и fonts из `backups/handoff-0006-pre-hud-fonts/`.

## Очередь 0007 — opaque Aero Glass START mask

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0007-pre-start-mask/`

Проблема:

- белые сегменты внутренних TECH-A-колец просвечивали через полупрозрачную кнопку `START`.

Изменения:

- центральная кнопка увеличена с 240x240 до 300x300;
- Aero Glass сделан визуально плотнее, с сохранением glass-gradient;
- в обычном, hover и active-состояниях повышена непрозрачность фона;
- анимация колец и орбитальные показатели не изменялись.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- backend запущен после финальной записи очереди;
- `GET /health`: HTTP 200;
- frontend запущен после финальной записи очереди;
- актуальное окно `Jarvis Assist` оставлено открытым;
- визуальная проверка того, что кольца не заходят в зону START, остаётся за пользователем.

Откат:

- восстановить `frontend/jarvis_ui.py` и `frontend/jarvis_hud.py` из `backups/handoff-0007-pre-start-mask/`.

## Очередь 0008 — static BG3 and TECH-A layer audit

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0008-pre-bg3-static/`

Сверка с оригиналом:

- в оригинальном `TECH-A 6 CPU.ini` `BG1.png`–`BG6.png` подключены как отдельные полноразмерные слои 710x710;
- все шесть PNG в проекте совпадают с оригиналом по SHA-256;
- оригинальный `rotator/rotator.ini` — отдельный конфиг с тремя ротаторными слоями и `Update=50`, а не часть базового списка BG-слоёв;
- в текущем порте действительно была ошибка: `BG3.png` проходил через `self.a3` и вращался вместе с кольцами.

Изменения:

- `BG3.png` теперь рисуется с углом `0` и остаётся стабильным;
- анимация остальных колец и орбитальных показателей не изменялась;
- порядок базовых BG-слоёв и отдельный rotator зафиксированы как отдельная зона аудита, чтобы не менять проверенную пользователем анимацию без визуального сравнения.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации журнала;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации журнала, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит стабильность `BG3.png` и отсутствие перепутанных слоёв.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0008-pre-bg3-static/`.

## Очередь 0009 — restore TECH-A action buttons

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0009-tech-buttons/`

Проблема:

- на главном экране отсутствовали восемь кнопок, отмеченных пользователем на сравнительном скриншоте.

Изменения:

- восстановлены кнопки `COMP`, `DOCS`, `CTRL`, `DESK`, `XPLR`, `CHRM`, `GAME`, `CFG`;
- использованы оригинальные PNG из `TECH-A/TECH-A` без перерисовки;
- координаты и размеры перенесены из секций `Meterbutton*` оригинального `TECH-A 6 CPU.ini`;
- `CFG` открывает экран настроек Jarvis, остальные кнопки пока дают локальный статус без привязки к пользовательским путям из старого Rainmeter-конфига;
- кнопки добавлены отдельным верхним слоем и не перекрывают центральную START-кнопку.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации журнала;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации журнала, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит восемь кнопок на главном экране.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0009-tech-buttons/`.

## Очередь 0010 — устранение дублирования TECH-A кнопок

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0010-deduplicate-tech-buttons/`

Проблема:

- интерактивные `QToolButton` дополнительно рисовали те же PNG, которые должны быть частью единого HUD-слоя; при анимированных кольцах это выглядело как несколько копий кнопок.

Изменения:

- artwork восьми TECH-A-кнопок рисуется ровно один раз в `JarvisHUD.paintEvent`;
- UI-кнопки оставлены только как прозрачные hit-area для клика, наведения и tooltip;
- центральная START-кнопка и анимация колец не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации журнала;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации журнала, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит, что каждая TECH-A-кнопка отображается в единственном экземпляре.

Откат:

- восстановить `frontend/jarvis_hud.py`, `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0010-deduplicate-tech-buttons/`.

## Очередь 0011 — static BG1-BG6 with detachable TECH-A animation

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0011-static-tech-a-bg-layers/`

Сверка с оригиналом:

- базовый `TECH-A 6 CPU.ini` имеет `Update=1000` и рисует `BG1.png`–`BG6.png` как шесть статичных 710x710 image meters в порядке `BG1 → BG6`;
- отдельный `rotator/rotator.ini` имеет `Update=50` и содержит только `1xx.png`, `2x.png`, `3x.png`;
- кнопки в оригинале — отдельные `Meter=BUTTON` с одним `ButtonImage` и событиями Rainmeter.

Изменения:

- `BG1–BG6` теперь рисуются один раз, статично и в оригинальном порядке;
- ротаторные PNG вынесены в отдельный подключаемый модуль `frontend/tech_a_animation.py`;
- текущая анимация сохраняется в этом модуле и может быть отключена/возвращена без изменения статичной композиции;
- восстановлены отдельные PNG-кнопки как интерактивные Qt-кнопки, без дополнительной отрисовки в HUD;
- используются оригинальные rotator-ресурсы `1xx.png`, `2x.png`, `3x.png`.

Файлы:

- `frontend/jarvis_hud.py`;
- `frontend/jarvis_ui.py`;
- `frontend/tech_a_animation.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI, HUD и animation-модуля: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит отсутствие дублей и отдельно стабильность BG-слоёв.

Откат:

- восстановить `frontend/jarvis_hud.py`, `frontend/jarvis_ui.py`, `frontend/tech_a_animation.py` и `docs/HANDOFF.md` из `backups/handoff-0011-static-tech-a-bg-layers/`.

## Очередь 0012 — split TECH-A button sprite states

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0012-button-sprite-states/`

Проблема:

- каждый оригинальный PNG кнопки является горизонтальным sprite sheet из трёх состояний, а предыдущая реализация показывала весь файл целиком; поэтому одна кнопка визуально троилась.

Изменения:

- каждый `COMP/DOCS/CTRL/DESK/XPLR/CHRM/GAME/CFG.png` делится на три равных кадра;
- первый кадр используется как static;
- второй подключён к состоянию hover;
- третий подключён к состоянию pressed/selected;
- размер интерактивной области соответствует одному кадру, а не всему sprite sheet.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- размеры всех восьми sprite sheet проверены, ширина делится на 3 без остатка;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит, что каждая кнопка отображается одним кадром и меняет состояние при наведении/нажатии.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0012-button-sprite-states/`.

## Очередь 0013 — neutral TECH-A button hover

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0013-no-button-hover-highlight/`

Изменения:

- hover-кнопки теперь использует тот же static-кадр, что и обычное состояние;
- убраны hover-background и hover-border у интерактивной области;
- tooltip с названием кнопки отключён;
- pressed-кадр sprite sheet сохранён.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит наведение на CFG и остальные кнопки.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0013-no-button-hover-highlight/`.

