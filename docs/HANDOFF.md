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

## Очередь 0014 — enable native TECH-A rotator animation

Дата: 2026-10-26

Состояние:

- native-style animation is enabled in `frontend/tech_a_animation.py`;
- static `BG1–BG6` remain fixed;
- animation is provided by the separate rotator layer using `1xx.png`, `2x.png` and `3x.png`;
- the current frontend restart confirms the animation module is connected to the HUD;
- `GET /health`: HTTP 200.

Файлы:

- `frontend/tech_a_animation.py`;
- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- backend and frontend are running after the previous queue;
- the active `Jarvis Assist` window is left open for visual confirmation.

## Очередь 0015 — rollback neutral TECH-A hover

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0015-rollback-neutral-hover/`

Изменения:

- отменена очередь 0013 по запросу пользователя;
- возвращён hover-кадр sprite sheet;
- возвращены hover-рамка и tooltip с названием кнопки;
- разбиение PNG на static/hover/pressed кадры сохранено.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит восстановленное hover-состояние.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0015-rollback-neutral-hover/`.

## Очередь 0016 — invisible TECH-A hover frame

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0016-invisible-button-hover-frame/`

Изменения:

- hover снова использует static-кадр без визуальной рамки и подсветки;
- tooltip с названием кнопки сохранён;
- pressed-кадр оставлен без изменений.

Проверка:

- `py_compile` для UI и HUD: ожидается после записи очереди;
- `git diff --check`: ожидается после записи очереди;
- backend и frontend будут перезапущены после фиксации журнала;
- пользователь проверит CFG: tooltip остаётся, прозрачная рамка исчезает.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0016-invisible-button-hover-frame/`.

## Очередь 0017 — hover animation without Qt overlay

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0017-hover-animation-no-overlay/`

Изменения:

- hover снова использует второй кадр оригинального TECH-A sprite sheet;
- Qt hover-background и border остаются полностью прозрачными;
- pressed-кадр и tooltip сохранены;
- отдельное выделенное окно вокруг кнопки не создаётся.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь проверит hover-анимацию CFG без прозрачной Qt-рамки.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0017-hover-animation-no-overlay/`.

## Очередь 0018 — explicit TECH-A button animation

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0018-explicit-button-animation/`

Изменения:

- переключение sprite-состояний переведено с автоматического `QIcon.Active` на явные события Qt;
- `enterEvent` показывает hover-кадр;
- `mousePressEvent` показывает pressed-кадр;
- `leaveEvent` возвращает static-кадр;
- прозрачный hover-background и border не изменялись.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь проверит, что hover-анимация снова работает без прозрачного окна.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0018-explicit-button-animation/`.

## Очередь 0019 — original Rainmeter button frame order

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0019-rainmeter-button-frame-order/`

Причина:

- у Rainmeter sprite sheet порядок кадров: `UP | DOWN | OVER`;
- предыдущая реализация ошибочно использовала: `UP | OVER | DOWN`.

Изменения:

- первый кадр оставлен static/UP;
- второй кадр назначен pressed/DOWN;
- третий кадр назначен hover/OVER;
- прозрачный Qt-overlay не добавлялся.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь проверит CHRM/CFG: hover-кадр должен быть светящимся, как в оригинальном TECH-A.

Откат:

- восстановить `frontend/jarvis_ui.py` и `docs/HANDOFF.md` из `backups/handoff-0019-rainmeter-button-frame-order/`.

## Очередь 0020 — TECH-A RAM side panel

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0020-tech-a-ram-side-panel/`

Сверка с оригиналом:

- добавлены значения из `freeRAM.p2x2`, `UsedTOTAL`, `UsedRAM.p2x`;
- добавлены дуги `RAMl12x`, `RAMl12xx`, `Circleram2`, `Circleram3`;
- значения используют текущую физическую RAM Jarvis: свободная %, общий объём в `G`, занятая %.

Изменения:

- справа на HUD добавлен RAM readout из трёх строк;
- добавлены cyan/white рабочие дуги и тонкие декоративные дуги;
- данные обновляются вместе с существующей RAM-статистикой.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит правый RAM-блок с процентами и полосками.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0020-tech-a-ram-side-panel/`.

## Очередь 0021 — RAM bar colors and original font

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0021-ram-colors-font/`

Изменения:

- цвета RAM-дуг переставлены местами по визуальному эталону пользователя;
- RAM-подписи теперь используют оригинальный `BitDust Two` из `TECH-A/SETTINGS` (`Font4`);
- остальные шрифты и слои HUD не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит цвета полосок и шрифт RAM-блока.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0021-ram-colors-font/`.

## Очередь 0022 — apply BitDust Two to RAM readout

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0022-fix-ram-font-target/`

Исправление:

- предыдущая привязка шрифта попала в подписи круговых индикаторов;
- подписи CPU/RAM/GPU/DISK возвращены на обычный HUD-шрифт;
- три строки правого RAM-блока теперь действительно используют `BitDust Two`.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит форму цифр в правом RAM-блоке.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0022-fix-ram-font-target/`.

## Очередь 0023 — thin TECH-A RAM bars

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0023-thin-ram-bars/`

Изменения:

- рабочие RAM-дуги уменьшены с 5 до 2 px;
- декоративные дуги уменьшены с 4 до 1 px;
- цвета, BitDust Two и расчёт значений не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит толщину RAM-полосок.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0023-thin-ram-bars/`.

## Очередь 0024 — balanced TECH-A RAM bars

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0024-balanced-ram-bars/`

Изменения:

- рабочие RAM-дуги увеличены с 2 до 3 px;
- декоративные дуги увеличены с 1 до 2 px;
- цвета, шрифт и значения не изменялись.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит новый промежуточный вес полосок.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0024-balanced-ram-bars/`.

## Очередь 0025 — add one pixel to RAM bars

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0025-ram-bars-plus-one/`

Изменения:

- рабочие RAM-дуги увеличены с 3 до 4 px;
- декоративные дуги увеличены с 2 до 3 px;
- цвета, шрифт и значения не изменялись.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит толщину RAM-полосок.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0025-ram-bars-plus-one/`.

## Очередь 0026 — native-quality TECH-A raster rendering

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0026-native-quality-render/`

Проблема:

- статичные BG-слои каждый repaint проходили через `QPixmap.scaled()` и сглаживание, из-за чего тонкие линии становились мягче оригинала Rainmeter.

Изменения:

- `BG1–BG6` один раз собираются в нативный кэш 710x710;
- статичный кэш рисуется 1:1 целочисленно, без повторного масштабирования;
- вращаемые Group/rotator-ресурсы отделены от статичного raster-слоя;
- постоянные gauge-background и Group предварительно масштабируются один раз;
- сглаживание применяется только к динамическим/векторным элементам, а не к нативному BG-кэшу.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально сравнит резкость тонких BG-линий с оригиналом.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0026-native-quality-render/`.

## Очередь 0027 — DPI-native HUD rasterization

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0027-dpi-native-hud/`

Диагностика:

- Windows scale: 120%;
- Qt `devicePixelRatio`: 1.25;
- из-за этого 710x710 HUD дополнительно масштабировался при выводе на экран.

Изменения:

- статичный BG-кэш теперь создаётся сразу в физическом размере `710 * devicePixelRatio`;
- кэш помечается правильным `devicePixelRatio`, чтобы Qt не пересэмплировал его повторно;
- масштаб оболочки Jarvis не менялся.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь сравнит резкость BG-линий на текущем DPI с оригиналом.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0027-dpi-native-hud/`.

## Очередь 0028 — freeze CPU/RAM/GPU indicator positions

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0028-freeze-cpu-ram-gpu-indicators/`

Изменения:

- орбитальное движение `CPU`, `RAM` и `GPU` остановлено;
- позиции зафиксированы на исходных углах `-90°`, `0°` и `90°`;
- значения загрузки продолжают обновляться плавно;
- `DISK` оставлен на текущей орбите.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: ожидается после записи очереди;
- `git diff --check`: ожидается после записи очереди;
- backend и frontend будут перезапущены после фиксации журнала;
- пользователь визуально проверит неподвижность CPU/RAM/GPU.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0028-freeze-cpu-ram-gpu-indicators/`.

## Очередь 0029 — freeze DISK indicator

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0029-freeze-all-indicators/`

Изменения:

- орбитальное движение `DISK` остановлено;
- позиция зафиксирована на исходном угле `180°`;
- теперь CPU, RAM, GPU и DISK неподвижны, меняются только их значения.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен после фиксации очереди;
- `GET /health`: HTTP 200;
- frontend перезапущен после фиксации очереди, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит неподвижность всех четырёх показателей.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0029-freeze-all-indicators/`.

## Очередь 0030 — original TECH-A indicator cell layout

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0030-original-indicator-cell-layout/`

Изменения:

- CPU, GPU, DISK и RAM переставлены в повторяющиеся визуальные ячейки исходника TECH-A;
- применена раскладка исходного блока дисков: левый верх, левый низ, правый низ, правый верх;
- итоговые якоря HUD: `CPU (80,250)`, `GPU (80,465)`, `DISK (645,465)`, `RAM (645,250)`;
- значения показателей остаются живыми, анимация их позиций не возвращается;
- координаты взяты из `TECH-A 6 CPU.ini`, данные физических дисков не переносились.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: ожидается после записи очереди;
- `git diff --check`: ожидается после записи очереди;
- backend и frontend будут перезапущены после фиксации журнала;
- пользователь визуально проверит совпадение четырёх индикаторов с ячейками оригинала.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0030-original-indicator-cell-layout/`.

## Очередь 0031 — six TECH-A indicator cells

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0031-six-indicator-cells/`

Изменения:

- добавлены все шесть исходных ячеек TECH-A;
- CPU, GPU, DISK и RAM занимают четыре боковые ячейки;
- верхняя центральная `(365,53)` и нижняя центральная `(365,656)` ячейки оставлены пустыми;
- пустые ячейки отображают только базовое кольцо без выдуманных показателей;
- движение индикаторов не включалось: изменяются только их значения.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит все шесть ячеек.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0031-six-indicator-cells/`.

## Очередь 0032 — TEMP and NET indicators

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0032-temp-net-indicators/`

Изменения:

- верхняя центральная ячейка `(365,53)` теперь показывает `TEMP`;
- `TEMP` берётся как максимальная доступная температура CPU/GPU в градусах Цельсия;
- нижняя центральная ячейка `(365,656)` теперь показывает `NET`;
- `NET` показывает суммарный входящий и исходящий трафик в Mbps, ограниченный шкалой 0–100 для совместимости с дугой;
- оба значения обновляются раз в секунду и плавно интерполируются, позиции ячеек остаются неподвижными;
- если датчик температуры недоступен, `TEMP` безопасно показывает `0` до появления доступного источника.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- прямой вызов датчика вернул `TEMP_SAMPLE 0`: доступный Windows-датчик температуры не обнаружен, предусмотрен безопасный fallback;
- пользователь визуально проверит верхний `TEMP` и нижний `NET`.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0032-temp-net-indicators/`.

## Очередь 0033 — readable unavailable temperature and low network values

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0033-readable-temp-net-values/`

Изменения:

- `NET` больше не округляет малый трафик до нулевого Mbps;
- значения ниже 1 Mbps показываются в коротком формате `K` — например `16K`;
- для значений выше 1 Mbps сохраняется формат Mbps;
- `TEMP` при отсутствии доступного датчика показывает `--`, а не ложный `0`;
- если температура станет доступна, ячейка автоматически вернётся к числовому значению;
- дуги обоих индикаторов продолжают использовать числовые данные и обновляются плавно.

Ограничение:

- на текущем AMD-драйвере температура доступна Диспетчеру задач, но не отдаётся стандартным Python/ADL-интерфейсам; для фактического значения потребуется отдельный сенсорный провайдер вроде LibreHardwareMonitor.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- `TEMP` корректно отображает `--` при недоступном датчике;
- пользователь визуально проверит `TEMP --` и читаемое значение `NET`.

Откат:

- восстановить `frontend/jarvis_hud.py` и `docs/HANDOFF.md` из `backups/handoff-0033-readable-temp-net-values/`.

## Очередь 0034 — TECH-A actions and remove Group glow

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0034-actions-and-remove-group-glow/`

Изменения:

- отключён дополнительный слой `Group.png`, который создавал синее свечение на заднем фоне;
- `COMP` открывает «Этот компьютер»;
- `DOCS` открывает папку пользователя `Documents`;
- `CTRL` открывает системные «Параметры Windows»;
- `DESK` сворачивает окна через Windows Shell и показывает рабочий стол;
- `XPLR` переключает оригинальную большую bitmap-анимацию `ANI ON/OFF`;
- `CHRM` открывает браузер по умолчанию через `about:blank`;
- `GAME` переключает `GAME MODE/DESK MODE`: останавливает или возвращает rotator-анимацию;
- `CFG` открывает страницу настроек Jarvis.

Файлы:

- `frontend/jarvis_ui.py`;
- `frontend/jarvis_hud.py`;
- `frontend/tech_a_animation.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD, UI и animation: пройден;
- `git diff --check`: пройден;
- переключатель `ANI` проверен: `False -> True -> False`;
- переключатель `GAME` проверен: `DESK -> GAME` корректно отключает rotator;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит отсутствие синего Group-свечения и работу кнопок.

Откат:

- восстановить файлы из `backups/handoff-0034-actions-and-remove-group-glow/`.

## Очередь 0035 — match original TECH-A animation speed

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0035-match-original-animation-speed/`

Изменения:

- скорость rotator-слоёв приведена к `Update=50` из исходного `rotator.ini`;
- `rotator_1` повторяет `Counter % 1500` и `ValueReminder=2500`;
- `rotator_2` повторяет `Counter % 2500` и `ValueReminder=2500`;
- `rotator_3` повторяет `Counter % 10` и `ValueReminder=20`;
- большая `ANI` bitmap-анимация теперь меняет кадр раз в `1000 мс`, как основной TECH-A skin;
- кнопки `XPLR` и `GAME` сохраняют прежнюю логику включения/выключения своих режимов.

Файлы:

- `frontend/tech_a_animation.py`;
- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD, UI и animation: пройден;
- `git diff --check`: пройден;
- симуляция шага `50 мс`: `rotator_1=0.144°`, `rotator_2=-0.144°`, `rotator_3=-18°`;
- симуляция `1000 мс`: `BigAnimation` переходит на следующий кадр;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально сравнит скорость rotator и ANI с оригиналом.

Откат:

- восстановить файлы из `backups/handoff-0035-match-original-animation-speed/`.

## Очередь 0036 — Chrome launch and true GAME/DESH visibility

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0036-chrome-and-game-mode/`

Изменения:

- `CHRM` сначала ищет установленный Chrome в стандартных Windows-путях и запускает его через `chrome.exe --new-window`;
- если Chrome не найден, сохраняется fallback на браузер по умолчанию;
- `GAME MODE` теперь скрывает все три rotator-слоя, как исходный `!RainmeterDeActivateConfig "TECH-A\\rotator"`;
- `DESK MODE` возвращает все три rotator-слоя, как исходный `!RainmeterActivateConfig`;
- переключение больше не оставляет последние кадры колец на экране.

Файлы:

- `frontend/jarvis_ui.py`;
- `frontend/jarvis_hud.py`;
- `frontend/tech_a_animation.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD, UI и animation: пройден;
- `git diff --check`: пройден;
- тест режима: `GAME` даёт `rotator_visible=False`, `DESK` возвращает `True`;
- `C:\Program Files\Google\Chrome\Application\chrome.exe`: найден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь проверит фактический запуск Chrome и исчезновение/возврат всех rotator-колец.

Откат:

- восстановить файлы из `backups/handoff-0036-chrome-and-game-mode/`.

## Очередь 0037 — increase RAM readout font

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0037-increase-ram-font/`

Изменения:

- шрифт цифр боковой RAM-панели увеличен с `6` до `8.3`;
- используется тот же оригинальный `BitDust Two`;
- остальные шрифты и размеры HUD не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит размер цифр RAM-панели.

Откат:

- восстановить файлы из `backups/handoff-0037-increase-ram-font/`.

## Очередь 0039 — rollback disk readouts

Дата: 2026-10-26

Изменения очереди 0038 откатированы по запросу пользователя:

- удалены дополнительные значения `MB`, `%` и `GB` из ячейки `DISK`;
- удалён расчёт активности дисковой подсистемы;
- предыдущие очереди проекта не изменялись.

Rollback point:

- `backups/handoff-0038-disk-readouts/` содержит состояние до очереди 0038;
- текущий код восстановлен до состояния очереди 0037.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит возврат к состоянию до дисковых readout-значений.

## Очередь 0040 — left-side disk values

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0040-left-disk-readouts/`

Изменения:

- слева от `CPU` и `GPU` добавлены два блока по образцу исходных левых дисковых ячеек;
- каждый блок показывает активность дисковой подсистемы в `MB` и объём доступного тома в `GB`;
- буквы дисков намеренно не отображаются;
- значения обновляются динамически из `psutil`;
- текущие позиции CPU/GPU/DISK/RAM/TEMP/NET не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит четыре значения слева от CPU/GPU.

Откат:

- восстановить файлы из `backups/handoff-0040-left-disk-readouts/`.

## Очередь 0041 — align left disk values to TECH-A anchors

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0041-align-left-disk-values/`

Изменения:

- исправлено смещение левых дисковых значений;
- применены точные исходные якоря `X=80/Y=220`, `X=80/Y=276`, `X=55/Y=435`, `X=115/Y=493`;
- значения больше не рисуются одной ошибочной колонкой у края HUD.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит совпадение позиций с оригиналом.

Откат:

- восстановить файлы из `backups/handoff-0041-align-left-disk-values/`.

## Очередь 0042 — restore original NET readouts

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0042-original-net-readouts/`

Изменения:

- удалены ошибочно добавленные дисковые пары слева от CPU/GPU;
- перенесена исходная группа `NET` из Rainmeter;
- `UPLOAD` показывает текущий исходящий трафик;
- `UPLOAD.Total` показывает накопленный исходящий трафик;
- `DOWNLOAD.Total` показывает накопленный входящий трафик;
- `DOWNLOAD` показывает текущий входящий трафик;
- применены исходные координаты `X=57`, `Y=315/335/365/385`;
- значения форматируются автоматически в `B`, `KB`, `MB`, `GB`.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- форматирование байтов проверено для `B`, `KB`, `MB`, `GB`;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит NET-блок в отмеченной области.

Откат:

- восстановить файлы из `backups/handoff-0042-original-net-readouts/`.

## Очередь 0043 — match NET readout font

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0043-match-net-font/`

Изменения:

- шрифт четырёх сетевых значений `UPLOAD/DOWNLOAD` увеличен до размера правых RAM-показателей;
- используется тот же `BitDust Two`, размер `8.3`;
- координаты и источники сетевых значений не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит размер NET-шрифта.

Откат:

- восстановить файлы из `backups/handoff-0043-match-net-font/`.

## Очередь 0044 — shift NET readouts right

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0044-shift-net-readouts/`

Изменения:

- `UPLOAD`, `UPLOAD.Total`, `DOWNLOAD.Total` и `DOWNLOAD` сдвинуты вправо на `2 px`;
- вертикальные координаты и размер шрифта не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит горизонтальное смещение NET-блока.

Откат:

- восстановить файлы из `backups/handoff-0044-shift-net-readouts/`.

## Очередь 0045 — shift NET readouts one more pixel

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0045-shift-net-readouts-one-more/`

Изменения:

- сетевой блок дополнительно сдвинут вправо на `1 px`;
- итоговая координата X для четырёх значений: `60`;
- вертикальные координаты, шрифт и значения не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- пользователь визуально проверит итоговое смещение NET-блока.

Откат:

- восстановить файлы из `backups/handoff-0045-shift-net-readouts-one-more/`.

## Очередь 0046 — integrate UP/DN network direction labels

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0046-integrate-up-dn-labels/`

Изменения:

- в документацию добавлена расшифровка `UP` и `DN` по схеме оригинального TECH-A;
- визуально используются родные подписи `UP` и `DN` из `BG3.png`, без повторной
  отрисовки этих слов кодом;
- `UP` обозначает исходящий трафик (`NetOut`), `DN` — входящий (`NetIn`);
- четыре динамических значения сохранены без изменения: текущий и накопительный
  исходящий трафик, затем накопительный и текущий входящий трафик;
- расшифровка терминов добавлена в `docs/CANONICAL_STRUCTURE.md`.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- health-ответ подтвердил текущие показатели CPU/RAM/DISK; `ollama` в текущей
  среде отключён, что не связано с сетевыми подписями.

Откат:

- восстановить файлы из `backups/handoff-0046-integrate-up-dn-labels/`.

## Очередь 0047 — remove duplicated UP/DN labels

Дата: 2026-10-26

Изменения:

- удалена дополнительная программная отрисовка `UP` и `DN`;
- сохранены оригинальные подписи из `BG3.png` и все четыре динамических
  сетевых значения;
- документация уточнена: направление трафика обозначается исходным слоем,
  а не дублируется в коде.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- обе полосы используют толщину `2 px`; UP — циан `RGB(0,235,245)` с alpha
  `220`, DN — светло-серый `RGB(235,235,235)` с alpha `210`.

Откат:

- вернуть коммит очереди `8159446` и восстановить состояние до очереди 0047.

## Очередь 0048 — connect NET progress arcs

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0048-network-progress/`

Изменения:

- полосы прогресса NET подключены к текущему исходящему и входящему трафику;
- толщина полос выставлена `2 px`, как у визуальных полос `FREE/USED`;
- нормализация повторяет исходный TECH-A: `NetOut / 1048576` и
  `NetIn / 6144000`;
- добавлено плавное изменение длины дуг, чтобы сетевые всплески не мигали;
- подписи и четыре текстовых значения `UP/DN` не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend перезапущен, `GET /health`: HTTP 200;
- frontend перезапущен, актуальное окно `Jarvis Assist` открыто;
- основные ячейки используют циан `RGB(0,235,245)`, а `TEMP` и `NET` больше
  не отрисовываются как центральные gauge-ячейки.

Откат:

- восстановить файлы из `backups/handoff-0048-network-progress/`.

## Очередь 0049 — cyan primary gauges and remove TEMP/NET cells

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0049-cyan-main-gauges-remove-temp-net/`

Изменения:

- цвет дуги значения для `CPU`, `RAM`, `GPU` и `DISK` установлен в
  `RGB(0,235,245)`;
- центральные ячейки `TEMP` и `NET` удалены из отрисовки виджета;
- отдельный блок `UP/DN` с сетевыми значениями и живыми полосами сохранён.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- ожидается: `py_compile`, `git diff --check`, перезапуск backend/frontend и
  `GET /health` со статусом HTTP 200.

Откат:

- восстановить файлы из `backups/handoff-0049-cyan-main-gauges-remove-temp-net/`.

## Очередь 0050 — move font settings and add configurable accent color

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0050-settings-accent-color/`

Изменения:

- добавлена отдельная страница истории, поэтому пункт `ИСТОРИЯ ЧАТОВ` больше
  не показывает содержимое настроек;
- выбор шрифта закреплён за настоящей страницей `НАСТРОЙКИ`;
- добавлен выбор акцентного цвета через системный color picker;
- значение по умолчанию — `#00EBF5` (`RGB 0, 235, 245`), оно сохраняется через
  `QSettings`;
- выбранный цвет применяется к дугам индикаторов HUD, сетевым полосам и
  акцентам кнопок/навигации приложения без перезапуска.

Файлы:

- `frontend/jarvis_ui.py`;
- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- страница истории отделена от страницы настроек, акцентный цвет по умолчанию
  сохранён как `#00EBF5`.

Откат:

- восстановить файлы из `backups/handoff-0050-settings-accent-color/`.

## Очередь 0051 — apply selected font to HUD and application tabs

Дата: 2026-10-26

Изменения:

- выбранное семейство шрифта из настроек передаётся в `JarvisHUD`;
- шрифт применяется ко всем отрисованным текстовым элементам HUD и к Qt-
  интерфейсу вкладок;
- растровые подписи внутри исходных PNG-слоёв TECH-A не заменяются.

Файлы:

- `frontend/jarvis_ui.py`;
- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- выбранный шрифт передаётся в HUD и применяется к его живым текстовым слоям.

Откат:

- вернуть состояние из backup очереди 0050 и отменить изменения очереди 0051.

## Очередь 0052 — fix settings text contrast

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0052-fix-settings-text-contrast/`

Изменения:

- живые `QLabel` интерфейса принудительно получили светлый цвет текста;
- выпадающий список шрифтов получил читаемый текст и контрастное popup-меню;
- исправлена видимость названий настроек при выборе TECH-A шрифта.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- ожидается: `py_compile`, `git diff --check`, перезапуск backend/frontend и
  `GET /health` со статусом HTTP 200.

Откат:

- восстановить файлы из `backups/handoff-0052-fix-settings-text-contrast/`.

## Очередь 0053 — font color setting and settings UI cards

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0053-font-color-settings-ui/`

Изменения:

- добавлена отдельная настройка цвета текста, по умолчанию `#FFFFFF`;
- цвет текста сохраняется через `QSettings` и применяется к живому тексту HUD
  и интерфейса настроек;
- страница настроек оформлена карточками «ТИПОГРАФИКА» и «ЦВЕТА»;
- добавлены RGB/HEX-превью текущих цветов и отдельные кнопки выбора.

Файлы:

- `frontend/jarvis_ui.py`;
- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- цвет текста и карточный UI настроек загружаются без ошибок.

Откат:

- восстановить файлы из `backups/handoff-0053-font-color-settings-ui/`.

## Очередь 0054 — style color dialog and selected menu text

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0054-style-color-dialog-and-selected-menu/`

Изменения:

- системный цветовой диалог заменён на тёмный Jarvis-styled non-native dialog;
- поля RGB/HTML и кнопки диалога получили контрастную тёмную тему;
- выделенный пункт бокового меню теперь использует чёрный текст на акцентном
  фоне.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- цветовой диалог загружается в Jarvis-теме, выделенный пункт меню получил
  чёрный текст.

Откат:

- восстановить файлы из `backups/handoff-0054-style-color-dialog-and-selected-menu/`.

## Очередь 0055 — apply selected font to every Qt widget

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0055-apply-font-to-all-widgets/`

Изменения:

- выбранное семейство шрифта принудительно применяется ко всем существующим
  Qt-виджетам приложения;
- применение выполняется при запуске и сразу после смены шрифта;
- кастомный HUD продолжает получать то же семейство через свой renderer.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- выбранный шрифт применяется рекурсивно ко всем Qt-виджетам и к живому HUD.

Откат:

- восстановить файлы из `backups/handoff-0055-apply-font-to-all-widgets/`.

## Очередь 0056 — live local time and date in HUD

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0056-live-time-date/`

Изменения:

- сверху виджета добавлены локальные часы ПК в формате `HH:MM`;
- снизу виджета добавлена дата в формате `25TH OCT`;
- дата и время синхронизируются с локальным `datetime.now()` компьютера;
- новые надписи наследуют выбранные в настройках шрифт и цвет текста.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- часы и дата синхронизируются с локальным временем ПК.

Откат:

- восстановить файлы из `backups/handoff-0056-live-time-date/`.

## Очередь 0057 — align time/date to TECH-A source anchors

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0057-align-time-date-source-anchors/`

Изменения:

- время и дата переведены с приблизительных прямоугольников на исходные
  baseline-якоря TECH-A;
- время размещается по `X=350, Y=167`;
- день и месяц размещаются по `X=348/379, Y=534`, как в оригинале;
- 24-часовой формат и синхронизация с локальным ПК сохранены.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- время и дата используют исходные baseline-якоря TECH-A.

Откат:

- восстановить файлы из `backups/handoff-0057-align-time-date-source-anchors/`.

## Очередь 0058 — fix time/date font metrics import

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0058-fix-time-date-import/`

Изменения:

- добавлен отсутствующий импорт `QFontMetricsF`, необходимый для выравнивания
  времени и даты по исходным координатам;
- устранено исключение `NameError` в `paintEvent`.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- после исправления импортов frontend перезапущен.

Откат:

- восстановить файлы из `backups/handoff-0058-fix-time-date-import/`.

## Очередь 0059 — fix time/date point import

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0059-fix-time-date-point-import/`

Изменения:

- добавлен отсутствующий импорт `QPointF` для baseline-позиционирования времени
  и даты;
- устранено исключение `NameError` при отрисовке HUD.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- frontend запустился без повторяющихся ошибок `paintEvent`.

Откат:

- восстановить файлы из `backups/handoff-0059-fix-time-date-point-import/`.

## Очередь 0060 — move time/date to the first outer BG6 ring

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0060-move-time-date-to-bg6/`

Изменения:

- время и дата перенесены с внутреннего кольца на первое внешнее кольцо
  `BG6`;
- оба значения выровнены по вертикальной оси центра виджета;
- время размещено на верхней точке кольца, дата — на нижней;
- синхронизация с локальным временем ПК и пользовательские шрифт/цвет
  сохранены.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- время и дата размещены на вертикальной оси первого внешнего кольца `BG6`.

Откат:

- восстановить файлы из `backups/handoff-0060-move-time-date-to-bg6/`.

## Очередь 0061 — raise date inside BG6

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0061-raise-date-in-bg6/`

Изменения:

- дата поднята с baseline `Y=697` до `Y=660`;
- время не изменялось;
- дата теперь находится внутри первого внешнего кольца `BG6`, а не на его
  нижней границе.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- дата поднята внутрь первого внешнего кольца `BG6`.

Откат:

- восстановить файлы из `backups/handoff-0061-raise-date-in-bg6/`.

## Очередь 0062 — increase live clock font

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0062-increase-time-font/`

Изменения:

- для времени добавлен отдельный размер шрифта `10.3 pt`;
- дата сохраняет прежний размер и позицию;
- выбранное семейство и цвет текста настроек продолжают применяться к часам.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- увеличенный шрифт времени загружается без ошибок.

Откат:

- восстановить файлы из `backups/handoff-0062-increase-time-font/`.

## Очередь 0063 — increase live clock font again

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0063-increase-clock-font-again/`

Изменения:

- размер отдельного шрифта времени увеличен с `10.3 pt` до `12.3 pt`;
- позиция времени, дата и остальные текстовые элементы не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- время отображается увеличенным размером `12.3 pt` без ошибок frontend.

Откат:

- восстановить файлы из `backups/handoff-0063-increase-clock-font-again/`.

## Очередь 0064 — shift HUD date right

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0064-shift-date-right/`

Изменения:

- дата сдвинута вправо на `3 px`, с `X=355` до `X=358`;
- время, формат даты и вертикальная координата не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- дата сдвинута вправо на `3 px` без ошибок frontend.

Откат:

- восстановить файлы из `backups/handoff-0064-shift-date-right/`.

## Очередь 0065 — shift HUD date right again

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0065-shift-date-right-again/`

Изменения:

- дата дополнительно сдвинута вправо на `3 px`;
- итоговый центр даты: `X=361`;
- время, формат даты и вертикальная координата не изменялись.

Файлы:

- `frontend/jarvis_hud.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- итоговый сдвиг даты вправо на `6 px` от исходного центра выполнен без ошибок.

Откат:

- восстановить файлы из `backups/handoff-0065-shift-date-right-again/`.

## Очередь 0066 — date shift, remove 3x layer, resize START, enlarge clock

Дата: 2026-10-26

Backup по прямой просьбе пользователя не создавался.

Изменения:

- дата дополнительно сдвинута вправо на `2 px`, итоговый центр `X=363`;
- слой `rotator/3x.png` исключён из загрузки и отрисовки;
- кнопка `START` уменьшена с `300×300` до `150×150`;
- часы увеличены с `12.3 pt` до `14.3 pt`;
- дата, время и остальные пользовательские настройки сохранены.

Файлы:

- `frontend/jarvis_hud.py`;
- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для HUD и UI: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- `3x.png` отключён, START уменьшен до `150×150`, часы увеличены до `14.3 pt`.

Откат:

- использовать Git-коммит до очереди 0066; backup намеренно не создавался.

## Очередь 0067 — readable START text shadow and contour

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0067-start-text-shadow/`

Изменения:

- текст `START` получил мягкую тёмную тень со смещением `2 px`;
- добавлен тонкий низкоальфа-акцентный контур для читаемости на Aero Glass;
- цвет тени, контура и текста не усиливает общий glow и синхронизируется с
  настройками цветов интерфейса.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- ожидается: `py_compile`, `git diff --check`, перезапуск backend/frontend и
  `GET /health` со статусом HTTP 200.

Откат:

- восстановить файлы из `backups/handoff-0067-start-text-shadow/`.

## Очередь 0068 — START text hover response

Дата: 2026-10-26

Перед правками создан backup:

- `backups/handoff-0068-start-text-hover-response/`

Изменения:

- при наведении на `START` контур текста становится немного ярче;
- тень текста слегка усиливается и смещается на `3 px`, создавая мягкий
  эффект подъёма;
- реакция применяется только к надписи и не раздувает внешний glow кнопки.

Файлы:

- `frontend/jarvis_ui.py`;
- `docs/CANONICAL_STRUCTURE.md`;
- `docs/HANDOFF.md`.

Проверка:

- `py_compile` для UI и HUD: пройден;
- `git diff --check`: пройден;
- backend и frontend перезапущены;
- `GET /health`: HTTP 200;
- frontend запускается без ошибок, реакция текста START готова к визуальной
  проверке наведением.

Откат:

- восстановить файлы из `backups/handoff-0068-start-text-hover-response/`.

