# Jarvis — Full Frontend & Backend Recovery Audit

Дата: 2026-11-17. Статус: discovery / root cause; реализация и приёмка продолжаются.

## Источники и граница доказательств

Текущее дерево и `git status` проверены до изменений: ветка `master` опережает remote на 23 коммита, рабочее дерево содержит многочисленные изменённые и новые файлы. Они считаются пользовательскими. Прочитаны актуальные разделы `docs/HANDOFF_ASSIST.md`, `docs/HANDOFF.md`, Phase 3/3.2, Phase 4.1, UI Architecture Recovery, UI/UX Audit, Architecture Audit, Dependency Map и Runtime Bug Registry. Исторические PASS не заменяют повторную проверку текущего кода. Большие журналы HANDOFF просматривались по относящимся к задаче разделам; остальные записи остаются историческим контекстом.

На `127.0.0.1:8000` продолжает слушать существующий backend PID 1636. Его не останавливали. В предыдущем проходе accessibility открытого окна показала AI страницу с Ollama `ON` и `qwen3-coder:30b`; read-only API подтвердил `provider=ollama`, семь профилей, `enabled_providers=ollama`, три доступные модели и наличие выбранной модели. Это свидетельство загрузки состояния в одном запуске, а не приёмка переключения/сохранения. Позже launcher повторно запустил UI PID 43360; Windows сообщил `Responding=True`, но capture timeout и root-only accessibility не позволяют подтвердить отрисовку.

## Фактическая архитектура

`frontend/launch_jarvis.py` использует один Python interpreter, singleton lock, проверку совместимости API и запускает или переиспользует `backend/main.py`. Основной PySide6 shell, HUD, Sidebar, Settings stack, встроенный AI panel и chat WebEngine живут в `frontend/jarvis_ui.py`. Backend `main.py` создаёт основной FastAPI app и сервисы; `ChatStore` хранит локальные чаты, а `/settings/llm*` вызывает существующий config service. `backend/account_server/app.py` — отдельная optional account/auth граница. `core/api.py` и `core/jarvis_api.py` содержат независимые примитивные `/command` приложения, но штатным launcher не запускаются. Их функция ограничена demo/legacy; переносить их `/command` без анализа контракта нельзя.

Цепочка AI: карточка Settings → `NetworkOperationWorker` → `/settings/llm` или `/settings/llm/models` → config service / provider adapter → ответ worker → UI. Чтение модели чата, сессий, погодных данных и Settings status/actions перенесено на этот общий worker; периодический voice-status GET использует неблокирующий `VoiceStatusClient` с `QNetworkAccessManager`.

## Подтверждённые причины и расхождения

| ID | Причина и код | Механизм и затронутая область | Статус |
|---|---|---|---|
| REC-01 | `JarvisUI.load_chat_model` (`frontend/jarvis_ui.py`) выполнял GET `/settings/llm` и `/settings/llm/models` в GUI-потоке | При старте UI и создании чата event loop мог блокироваться; при ошибке показывался фиктивный Ollama/`qwen3:8b` | Исправлено в исходнике; live UI retest открыт |
| REC-02 | `ai_inline.toggle_provider` и `select_active` меняли `enabled`, `active`, текст и карточки до результата POST | Неуспешный запрос оставлял видимый `ON` без подтверждения backend; общий error callback лишь писал ошибку | Исправлено в исходнике; runtime приёмка открыта |
| REC-03 | `ai_inline.fetch_all_models` выбирал `models[0]` в локальном профиле после GET | Кнопка чтения каталога могла показать другую выбранную модель без сохранения и без подтверждения backend | Исправлено в исходнике; runtime приёмка открыта |
| REC-04 | `JarvisUI.load_chat_sessions` делал GET `/chat/sessions` с timeout 4 s в GUI-потоке | Sidebar/переходы могли зависнуть; fallback создавал визуальный `default` chat и скрывал ошибку | Исправлено в исходнике; live UI retest открыт |
| REC-05 | Phase 4.1 и Phase 5 фиксируют размеры, scroll-host и конфликтующие stylesheet-слои | Автоматические Qt smoke и AX-дерево доказывают наличие страниц, но не отсутствие белых поверхностей, перекрытий и потери кликов после fullscreen | Визуальная приёмка открыта |
| REC-06 | Старый Dependency Map утверждал, что URL захардкожен в каждом UI callback | Текущий код централизовал base URL через `API_ROOT`; единого типизированного клиента ещё нет | Формулировка документа обновлена |
| REC-07 | `load_weather` и две формы сохранения погоды выполняли внешний HTTP в GUI-потоке | Старт окна/таймер могли ждать до 13 с, Settings-кнопки до 8 с | Исправлено в исходнике через существующий Qt worker; live UI retest открыт |
| REC-08 | Settings создавали `QTimer.singleShot(0)` для sync backup/capability GET; действия также вызывали sync HTTP | Открытие страниц и клики могли задерживать Qt на 3–45 с | Исправлено в исходнике через общий `NetworkOperationWorker`; live UI retest открыт |
| REC-09 | `load_history_sessions` и `load_chat_history` выполняли sync GET в GUI и подменяли сетевой сбой пустой историей | История Settings/переключение чатов могли зависать; устаревший ответ мог попасть в новый чат | Исправлено в исходнике через общий worker и generation guard; live retest открыт |

## Backend и тестовый контур

В текущем коде `backend/main.py` — один основной FastAPI. `core/api.py` запускается отдельно на 8001, `core/jarvis_api.py` — на 8000 только при прямом исполнении; оба возвращают простой `/command` и не имеют эквивалентного API Settings/Chat/Voice. `backend/account_server/app.py` создаёт отдельный FastAPI для PostgreSQL/OAuth. Ни один из этих модулей не является доказанным заменителем main backend; их импорты, реальные потребители и статус запуска следует проверить перед решением о legacy. Backend route inventory и сравнение контрактов продолжаются.

### Живой API inventory (read-only OpenAPI, 2026-11-17)

| Endpoint | Метод | Источник/потребитель | Статус доказательства |
|---|---|---|---|
| `/settings/llm` | GET, POST | config service / AI и model UI | Маршрут подтверждён OpenAPI; GET ранее вернул активную Ollama; POST в этом проходе не вызывался |
| `/settings/llm/test` | POST | config service / AI check | Маршрут подтверждён; операция не тестировалась |
| `/settings/llm/models` | GET | provider catalog / AI и chat model | Маршрут подтверждён; ранее GET вернул 3 Ollama модели |
| `/chat/sessions*` | GET, POST, PATCH, DELETE | ChatStore / Sidebar и история | Маршруты подтверждены; write операции не тестировались |
| `/chat/history`, `/api/messages*` | GET, DELETE | ChatStore / chat WebEngine | Маршруты подтверждены; UI цикл не тестировался |
| `/voice/*` | GET, POST | VoiceRuntime / HUD и chat voice | Маршруты подтверждены; физический голосовой цикл не тестировался |
| `/runtime/providers`, `/runtime/events` | GET, POST | RuntimeRegistry / UI polling | Маршруты подтверждены; event lifecycle не тестировался |
| `/hardware/settings`, `/devices/*` | GET, POST | device services / Settings | Маршруты подтверждены; оборудование не тестировалось |

OpenAPI подтверждает зарегистрированные пути listener, но не доказывает совместимость payload/response. `load_chat_model()` и `load_chat_sessions()` вызывают реально существующие GET endpoints, однако делают это синхронно в GUI-потоке.

Обновление после изменения исходника: последнее предложение описывает состояние на момент discovery. Теперь GET используют существующий `ProviderOperationWorker`/`ProviderOperationBridge` и QThread; `on_chat_model_changed()` также отправляет POST через этот worker и возвращает подтверждённый выбор после ошибки. Реальный запущенный PID 55880 загружен до этой правки и не является её runtime-проверкой.

## План исправления и проверки

1. Устранить REC-01/02/03 в существующем worker/API пути: подтверждённое состояние backend, pending, error/rollback и повторная загрузка без GUI blocking.
2. Вынести ожидание chat sessions из GUI-потока через существующий Qt lifecycle; сохранить различие между пустым списком и ошибкой сети.
3. Проверить Settings/Sidebar/window modes на четырёх контрольных размерах, реальные события и hit testing. Не считать геометрию QWidget визуальной приёмкой Aero Glass.
4. Составить полный API реестр из фактических route declarations и вызовов Frontend; сравнить legacy/test контуры и найти несовпадающие контракты.
5. Проверить изолированные backend/frontend/integration tests без изменения основной SQLite; запустить основной UI для сценариев Settings → AI → fullscreen → restore → Chat. Задокументировать каждый PASS/FAIL/BLOCKED.
6. После исправлений синхронизировать HANDOFF, Bug Registry, Dependency/Project Map, UI docs и итоговый `JARVIS_FULL_RECOVERY_REPORT.md`.

Текущий вердикт: полноценная готовность **не доказана**. Windows capture и click geometry ранее возвращали timeout/недоступность; это блокирует автоматическую визуальную приёмку, но не статический анализ, изолированное тестирование и исправление подтверждённых причин.

## Первый implementation checkpoint

Для REC-02 `ai_inline` больше не делает оптимистический переход карточек. Save operation принимает выбранный provider в payload и только после успешного ответа `save_llm_settings()` (он возвращает `get_settings_bundle()`) обновляет UI из подтверждённого bundle. На время сохранения переключатели отключены; ошибка возвращает их в состояние последней успешной загрузки и показывает `RETRY`/текст ошибки. До первой успешной загрузки toggles отключены. Для REC-03 чтение списка моделей больше не меняет выбранную модель. `frontend/jarvis_ui.py` скопирован перед изменением в `docs/runtime/diagnostics/phase5-backups/jarvis_ui.pre-full-recovery-20261117.bak`. `py_compile`, frontend suite 26/26 и `git diff --check` — PASS. Эти проверки не доказывают кликабельность или visual acceptance.

## Второй implementation checkpoint — асинхронное чтение

Перед правкой UI скопирован в `docs/runtime/diagnostics/phase5-backups/jarvis_ui.pre-async-reads-20261117.bak`. `load_chat_sessions`, `load_chat_model` и выбор модели чата больше не вызывают `requests` в GUI-потоке. Использован существующий worker/bridge; повторные запросы сессий объединяются, устаревшие ответы модели игнорируются, а закрытие окна ждёт завершения bounded workers через Qt event loop без синхронного `wait()`. При ошибке списка чатов прежний список остаётся; пустая область получает неактивный текст ошибки вместо фиктивного чата. Ошибка модели не подменяет активного провайдера/модель статическим значением. `frontend/tests/test_backend_read_worker.py` проверяет GUI tick во время 200 ms backend ожидания, GUI-thread callback, worker cleanup и возврат к подтверждённой модели после ошибки. Frontend suite **28/28 PASS**, `py_compile` и `git diff --check` PASS. Live перезапуск изменённого UI ещё не выполнен, потому что ранее запущенный Jarvis PID 55880 оставлен владельцу для ручной проверки.

## Текущий UI recovery checkpoint — 2026-11-17

Позднейшие ручные проверки заменяют устаревшие формулировки выше. Владелец
подтвердил: Settings открылись в обновлённом UI; белая область исчезла после
отключения palette fill у Settings scroll host; после первого fullscreen →
windowed клики не работали. Трасса показала скачки высоты от конкурирующих
normal/fullscreen constraints. После удаления повторных `setFixedSize`,
`resize` и фиксированного fullscreen Recent Chats владелец подтвердил работу
кликов при возврате. Backend PID 1636 на 8000 не останавливался.

Два дополнительных корня визуальной регрессии:

1. Только General имела локальный тёмный QSS; остальные `settingsCard`
   наследовали более светлый root QSS. Общая тёмная Glass theme и одинаковые
   внутренние отступы перенесены в root stylesheet. AI panel использует тот же
   surface contract. Отступы Settings body изменены по красной разметке
   владельца; General и другие страницы, кроме AI, визуально приняты в PID
   39240.
2. `QStackedWidget.heightForWidth()` удерживал высоту скрытой AI page на
   коротких страницах с word wrap. `CurrentPageStack` использует size hints
   и height-for-width только видимой страницы. Минимальный Qt repro показал
   лишний scrollbar до и отсутствие его после правки. В live PID 39240 все
   13 страниц показали `scroll_max=0` при normal 1280×850. Для более низких
   окон прокрутка остаётся функциональной, если содержимое действительно
   больше viewport.

Последняя AI-правка убрала `AlignLeft|AlignTop` у provider panel: именно он
оставлял AI карточку уже и ниже General. В UI PID 2248 владелец вручную
подтвердил совпадение AI с General по ширине и высоте, отсутствие лишнего
scrollbar и кликабельность AI/навигации после fullscreen → windowed. В trace
AI `scroll_max=0`. Frontend 36/36 PASS; это не полный runtime/visual acceptance:
изменение провайдера, другие разрешения и остальные действия не проверены.

## Runtime checkpoint — provider contract, account identity и capabilities

Повторный полный старт через `frontend/launch_jarvis.py` подтвердил один UI
PID 41128 и один дочерний основной backend PID 55412 на `127.0.0.1:8000`;
`/health` PASS, Ollama обнаружена. Альтернативный backend не создавался.

Дополнительная первопричина REC-UI-011 находилась на API boundary:
`LLMSettingsRequest.model_dump(exclude_none=True)` включал значения по
умолчанию для полей, которых не было в partial UI payload. Backend трактовал
их как явные пустые значения. POST routes теперь используют
`exclude_unset=True`, config service сохраняет отсутствующие provider fields,
а FreeLLMAPI нормализует пустую модель в `AUTO`. Реальный GET и безопасный
partial POST с неизменёнными текущими значениями подтвердили Ollama
`qwen3:8b` и FreeLLMAPI `AUTO` без взаимного переноса.

Account Store и QSettings больше не расходятся при старте: подтверждённый
Google email копируется в пустой `profile_email`. Runtime проверил заполненный
ключ; визуальное отображение в двух экранах ещё требует владельца.

Страница capabilities заменяет плоский список одной responsive сеткой из
восьми тёмных actionable cards (два столбца). Карточки используют только
существующие функции: snapshot, соответствующие Settings либо chat entry
point. Все Settings action buttons приведены к общему AI outline contract.
Автоматический Windows capture снова завершался timeout, поэтому визуальный
PASS этих новых элементов не заявляется.

Закрытие UI теперь очищает завершённые QThread jobs по фактическому
`isRunning()`. Реальный UI завершился по `CloseMainWindow=True`, а launcher
затем штатно остановил дочерний backend. Frontend **43/43 PASS**, provider
regressions **3/3 PASS**, voice overlay signal tests **4/4 PASS**.
