# Jarvis Assist — отдельный журнал аудита

Этот файл относится только к аудиту и стабилизации голосового Assist. Основной
`docs/HANDOFF.md` не изменяется в рамках Assist-задач.

## Очередь 0249 — семантические вариации voice_responses

Дата: 2026-11-15

- аудит `data/voice_responses/questions.json` подтвердил 246 intent и 1476
  исходных вариантов; 66 текстовых групп повторялись между intent, всего
  1410 повторных записей;
- добавлен read-only аудит `backend/voice_engine/voice_variation_audit.py`,
  отчёты: `data/voice_responses/variation_audit.json` и
  `docs/VOICE_RESPONSE_VARIATIONS_REPORT.md`;
- существующие записи получили `response_id`, `semantic_group`,
  `context_tags`, `enabled`, `generation_status`, `created_at`; тексты и старые
  WAV не изменялись;
- добавлены 20 новых семантически разных текстовых вариантов для пяти базовых
  intent; все 20 WAV успешно созданы через существующий Fish Audio pipeline
  после повторного запуска одного временно упавшего запроса;
- `LocalResponseService` теперь проходит полный цикл готовых вариантов и не
  повторяет запись до исчерпания доступного набора; smoke-тест 10 приветствий:
  10 уникальных текстов/WAV, 0 соседних повторов;
- общая проверка WAV: `ok=true`, 5712 файлов, все mono/44100 Hz, ошибок 0;
- manifest voice library: 1496 ready, 0 pending, 0 errors;
- следующий шаг: пакетно подготовить и озвучить следующие semantic-группы,
  начиная с подтверждённых повторов, не запуская неконтролируемую массовую
  генерацию.

## Очередь 0250 — расширение очереди semantic-вариантов

Дата: 2026-11-15

- для остальных intent добавлены 964 новые записи с уникальными WAV-путями и
  статусом `AUDIO_PENDING`; существующие 1476 записей не изменялись;
- pending-тексты обновлены на четыре разные конструкции отдельно для
  `instant`, `ack` и `dynamic`; проверка внутри каждого intent не нашла
  near-duplicate пар;
- в следующем ограниченном Fish Audio пакете создано ещё 24 WAV; итоговый
  manifest: `2460` вариантов, `1520 ready`, `940 pending`, `0 errors`;
- повторный runtime smoke-тест группы `greetings_002`: 10 разных WAV за 10
  обращений, 0 соседних повторов;
- полная WAV-проверка после пакета: `ok=true`, 5737 mono-файлов 44100 Hz,
  ошибок 0;
- очередь остаётся resumable: следующий запуск
  `generate_voice_library.py --limit 20` пропускает все готовые записи.

`LocalResponseService.summary()` теперь отдаёт `pending`, `errors`,
`exact_duplicate_items` и `near_duplicate_pairs_same_intent`; runtime допускает
только `enabled=true` и `generation_status=AUDIO_READY`, поэтому незавершённые
варианты не могут случайно попасть в воспроизведение.

После следующего Fish-пакета и повторов временных сетевых сбоев актуальный
manifest: `1544 ready`, `916 pending`, `0 errors`; генератор получил параметр
`--retries` и проверяет отсутствие целевого WAV перед записью. Полная проверка
аудиотеки: `ok=true`, 5761 mono WAV 44100 Hz.

## Контрольная точка 2026-11-15 — продолжение после паузы

Статус: **ACTIVE**

Последняя подтверждённая точка:

- `KnowledgeSearchService.search()` возвращает конкретные `audio_path`, `audio_variant` и `sources`;
- `VoiceRuntime` реально выбирает и воспроизводит связанный WAV для Knowledge 3.0: проверен запрос «активное слушание» → `data/knowledge3/psychology/audio/psych-005-communication.wav`;
- `VoiceRuntime` реально выбирает и воспроизводит Offline Knowledge WAV: проверен запрос «что такое Intel 8086» → `data/offline_knowledge/audio/offline_0002_intel_8086/variant_01.wav`;
- Integrity: `ok=true`, 10/10 module roots и catalog paths, Programming/Audio/Voice `62/62`, Guitar `12/12`, Literature `7/7`, Psychology `8/8`, Mixing `6/6`, DAW `6/6`, Offline `4050/4050`;
- backend оставлен запущенным на `127.0.0.1:8000`, frontend не останавливался;
- исходные данные, существующие WAV и `E:\Музыка` не изменялись и не удалялись.

Следующая точка продолжения:

1. Проверить новый read-only `/knowledge/daw/project/report` на реальной папке проекта/медиа.
2. Продолжить углубление DAW/Cubase adapter; не выполнять запуск или изменения проектов без подтверждения.
3. Провести полный requirement-by-requirement аудит исходного `C:\Users\Данил\Desktop\ТЗ .txt` и закрывать следующий незавершённый пункт.

## Очередь 0248 — read-only инвентарь VST2/VST3

Дата: 2026-11-15

- `DawControlService.plugin_inventory()` добавляет безопасный инвентарь файлов
  плагинов на путях из `plugin_registry.json`;
- добавлен `GET /knowledge/daw/plugins?query=&limit=`;
- результат разделяет `present_on_disk` и `loaded_in_daw=not_tested`, поэтому
  наличие DLL/VST3 не выдаётся за загрузку в Cubase;
- инвентарь ограничен максимумом 1000 записей и не загружает бинарники;
- `py_compile` и прямой smoke-тест прошли: обнаружено 271 бинарное расширение,
  фильтр `pro-q` вернул 10 совпадений;
- следующий шаг: проверить endpoint через активный backend и продолжить DAW-side
  adapter только в confirmation-first режиме.

Проверка выполнена на отдельном временном экземпляре backend `:8010`: `/health`
вернул `ollama=true`, а `/knowledge/daw/plugins?query=pro-q&limit=10` вернул
10 записей, `read_only=true`, `loaded_in_daw=false`. Основной backend не
останавливался.

## Очередь 0234 — read-only DAW project report

Дата: 2026-11-15

- добавлен `DawControlService.project_report()` и endpoint `GET /knowledge/daw/project/report`;
- отчёт агрегирует роли дорожек, длительность, peak/RMS, clipping и найденные `.cpr`;
- routing, VST state и automation явно помечаются недоступными, без догадок и записи в проект;
- control-поля фиксируют, что изменение/undo пока требуют отдельного подтверждённого adapter;
- следующий шаг: проверить endpoint на реальном проектном каталоге и затем продолжить следующий незавершённый модуль исходного ТЗ.

## Очередь 0235 — read-only Mixing chain suggestions

Дата: 2026-11-15

- добавлен `POST /knowledge/mixing/suggest`;
- сервис анализирует реальный WAV и предлагает цепочку под vocal/guitar/mix;
- плагины сверяются с обнаруженным registry, но ничего не загружается и не применяется автоматически;
- применение явно помечено как недоступное до DAW adapter и подтверждения пользователя;
- тестировать endpoint после перезапуска backend на существующем WAV.

Проверка выполнена: для `audio-gain-staging.wav` получены peak `-0.73 dBFS`,
RMS `-18.05 dBFS`, без clipping; для guitar предложены Guitar Rig 5,
FabFilter Pro-Q 2 и FabFilter Total Bundle, все отмечены как найденные в
registry. Применение осталось read-only и требует будущего adapter.

## Очередь 0236 — приоритет Conversational Library в едином поиске

Дата: 2026-11-15

- `KnowledgeSearchService.search()` теперь сначала проверяет существующую `voice_responses/questions.json`, затем Offline Knowledge и специализированные каталоги;
- `KnowledgeSearchService.answer()` возвращает готовый conversational WAV без Ollama для точных бытовых фраз;
- lookup не изменяет rotation state и не перезаписывает WAV;
- добавлены точные `audio_path`, `audio_variant` и источник каталога;
- следующий тест: HTTP-проверка приветствия и неизвестного запроса с подтверждением, что Ollama не нужен для готового conversational ответа.

Проверка выполнена: `/knowledge/search?query=привет Jarvis` вернул первым
`conversational` с готовым `greetings_001_response_01.wav`, а
`/knowledge/answer` вернул тот же источник и путь WAV. Запрос `Intel 8086`
остался в Offline Knowledge и вернул `variant_01.wav`; `/health` подтвердил
работающий backend и Ollama.

## Очередь 0237 — безопасные контрольные точки DAW-проектов

Дата: 2026-11-15

- добавлен `POST /knowledge/daw/project/snapshot`;
- без `confirmed=true` endpoint только возвращает план и количество файлов;
- с подтверждением создаётся отдельный JSON-manifest в `data/knowledge3/daw/snapshots`, содержащий относительные пути, размеры, mtime и SHA-256;
- исходная папка проекта, `.cpr` и аудио не копируются поверх и не изменяются;
- восстановление намеренно не выполняется: для него нужен отдельный подтверждаемый adapter.

Проверка выполнена на 12 гитарных WAV: `confirmed=false` вернул статус
`CONFIRMATION_REQUIRED`, `confirmed=true` создал
`data/knowledge3/daw/snapshots/smoke_daw_checkpoint_20261115.json` с 12
SHA-256. Исходные размеры и файлы после операции не изменились.

## Очередь 0233 — unified search возвращает конкретный WAV

Дата: 2026-11-15

- `KnowledgeSearchService.search()` теперь возвращает `audio_path`, `audio_variant` и `sources` для offline и Knowledge 3.0 карточек;
- это устраняет промежуточный шаг «has_audio без адреса»: VoiceRuntime может сразу передать найденный файл плееру;
- HTTP-проверка `активное слушание` вернула `psych-005-communication.wav` и источник APA;
- HTTP-проверка `Intel 8086` вернула конкретный `variant_01.wav` из отдельного Offline Knowledge root;
- Integrity сохранил `ok=true`, все проверенные аудиоблоки остаются целыми;
- backend перезапущен для загрузки кода и оставлен работающим.

## Очередь 0231 — Integrity: проверка всех Knowledge 3.0 модулей

Дата: 2026-11-15

- `KnowledgeIndexService.integrity()` теперь проверяет наличие всех 10 module storage roots из `data/knowledge3/index.json`;
- проверяются все 10 индексных catalog paths, физическое разделение `knowledge3`, `offline_knowledge` и `voice_responses`, а также непустые WAV по модулям;
- реальный HTTP-тест подтвердил `ok=true`, `module_roots_checked=10`, `catalog_paths_checked=10`, ошибок и предупреждений нет;
- текущая аудиостатистика: Programming/Audio/Voice `62/62`, Guitar `12/12`, Literature `7/7`, Psychology `8/8`, Offline `4050/4050`;
- backend перезапущен для загрузки проверки и оставлен работающим; frontend не останавливался.

## Очередь 0232 — Mixing и DAW: связанная WAV-библиотека

Дата: 2026-11-15

- добавлен общий bounded/resumable `backend/knowledge3/generate_audio_cards.py` для отдельных каталогов Mixing и DAW;
- создано 6/6 WAV для карточек `data/knowledge3/mixing/catalog.json` и 6/6 WAV для карточек `data/knowledge3/daw/catalog.json`;
- `KnowledgeIndexService.integrity()` теперь проверяет оба каталога и все 12 новых WAV;
- единый поиск сохраняет приоритет более подробных существующих уроков, а новые карточки остаются дополнительным source-linked слоем с аудио;
- HTTP Integrity подтвердил `ok=true`: Mixing `6/6`, DAW `6/6`, Psychology `8/8`, Literature `7/7`, Guitar `12/12`, Programming/Audio/Voice `62/62`, Offline `4050/4050`;
- Fish Audio и существующие WAV не перезаписывались, backend оставлен запущенным.

## Очередь 0227 — Guitar Encyclopedia: связанная WAV-библиотека

Дата: 2026-11-15

- добавлен bounded/resumable `backend/knowledge3/generate_guitar_audio.py`;
- для всех 12 карточек Guitar Encyclopedia создано по одному новому WAV в `data/knowledge3/guitar/audio`;
- каждый файл прошёл проверку SoundFile; существующие файлы не перезаписывались;
- `data/knowledge3/index.json` обновлён: Guitar `audio_ready=12`, `audio_pending=0`, `audio_status=AUDIO_READY`;
- `KnowledgeIndexService.integrity()` теперь проверяет наличие и непустой размер каждого Guitar WAV;
- HTTP-сценарий `Ibanez GRG170DX` прошёл: единый поиск вернул карточку, официальный источник и связанный `ibanez-grg170dx.wav`;
- после перезапуска backend Integrity подтвердил `ok=true`, Guitar `12/12`, Programming/Audio/Voice `62/62`, Offline Knowledge `4050/4050`;
- backend оставлен запущенным на `127.0.0.1:8000`, frontend не останавливался.

## Очередь 0228 — Literature: связанная WAV-библиотека

Дата: 2026-11-15

- добавлен bounded/resumable `backend/knowledge3/generate_literature_audio.py`;
- для 7 литературных карточек с copyright-safe summary создано 7 WAV в `data/knowledge3/literature/audio`;
- существующие WAV не перезаписывались, каждый новый файл проверен через SoundFile;
- `data/knowledge3/index.json` получил `literature.audio_ready=7`, `audio_pending=0`, `audio_status=AUDIO_READY`;
- `KnowledgeIndexService.integrity()` теперь проверяет и Literature WAV;
- HTTP-сценарий «Робинзон Крузо» вернул текстовый summary, официальный источник и `defoe-robinson-crusoe.wav`;
- после перезапуска backend Integrity подтвердил `ok=true`: Programming/Audio/Voice `62/62`, Guitar `12/12`, Literature `7/7`, Offline Knowledge `4050/4050`;
- backend оставлен запущенным, фронтенд не останавливался.

## Очередь 0229 — DAW project inspection: media metrics и безопасный launch plan

Дата: 2026-11-15

- `DawControlService.inspect_project()` теперь для найденных WAV возвращает sample rate, каналы, длительность, peak/RMS, clipping и консервативную оценку роли дорожки по имени;
- добавлен явный read-only блок `routing`: отсутствие CPR/plugin adapter сообщается честно, маршрутизация не изменяется;
- реальный HTTP-сценарий на 12 Guitar WAV прошёл: все файлы проанализированы, clipping не обнаружен;
- `POST /knowledge/daw/action/plan` для `Steinberg Cubase 13` подтвердил обнаруженный executable `C:\Program Files\Steinberg\Cubase 13\Cubase13.exe`, но запуск требует `confirmed=true`;
- фактический запуск DAW в рамках теста не выполнялся, чтобы не открывать стороннее приложение без явного пользовательского запроса;
- backend `/health` подтвердил `ollama=true`, frontend не останавливался.

## Очередь 0230 — Psychology & Emotional Support: связанная WAV-библиотека

Дата: 2026-11-15

- добавлен bounded/resumable `backend/knowledge3/generate_psychology_audio.py`;
- для всех 8 safety-reviewed карточек создано 8 WAV в `data/knowledge3/psychology/audio`;
- в текст озвучивания включены только безопасные объяснения и упражнения; диагнозы и назначения не добавлялись;
- `data/knowledge3/index.json` обновлён: Psychology `audio_ready=8`, `audio_pending=0`, `audio_status=AUDIO_READY`;
- `KnowledgeIndexService.integrity()` теперь проверяет Psychology WAV;
- HTTP-сценарий «активное слушание» вернул карточку, источник APA и `psych-005-communication.wav`;
- Integrity после перезапуска backend: `ok=true`, Psychology `8/8`, Literature `7/7`, Guitar `12/12`, Programming/Audio/Voice `62/62`, Offline `4050/4050`;
- backend оставлен запущенным, frontend не останавливался.

## Очередь 0218 — Programming Mentor: первый связанный Fish Audio WAV

Дата: 2026-11-15

- добавлен bounded/resumable `backend/knowledge3/generate_programming_audio.py`;
- скрипт пишет только новые файлы в `data/knowledge3/programming/audio`, проверяет WAV через SoundFile и не перезаписывает существующие записи;
- создан и проверен `python-001-variables-and-types.wav`: 44.1 kHz, mono, 10.681 s;
- обновлены `lessons.json` и `data/knowledge3/index.json`: Programming Mentor `audio_ready=1`, `audio_pending=30`;
- единый поиск и `knowledge_search_service.answer()` теперь возвращают `audio_path` и `has_audio` для готового урока;
- HTTP-сценарий проверен после перезапуска backend: запрос «переменные типы данных» вернул `knowledge3.programming` и связанный WAV;
- команда продолжения: `backend/jarvis_env/Scripts/python.exe backend/knowledge3/generate_programming_audio.py --limit N`;
- текущие backend/frontend процессы сохранены запущенными.

## Очередь 0219 — Voice Production Mentor: guided workflow MVP

Дата: 2026-11-15

- `VoiceProductionService.workflow()` добавляет пошаговый read-only сценарий из 10 этапов: источник, область проблемы, симптом, предложение Cubase/Pro-Q 3, поиск и прослушивание полосы, подтверждённая настройка, сравнение и переход к следующему этапу;
- добавлен `GET /mentor/voice/workflow`; незаполненные входы возвращаются как конкретные вопросы, а действия DAW явно требуют отдельного подтверждения;
- HTTP-проверка прошла для `Ibanez RG / отдельная дорожка / резкость`: `status=ready_for_guided_session`, все входные вопросы закрыты, 10 шагов возвращены;
- PyCompile прошёл для нового сервиса, маршрута, Programming Audio generator и unified search;
- backend `/health` после перезапуска: `ollama=true`.

## Очередь 0220 — Knowledge 3.0 audio integrity расширена

Дата: 2026-11-15

- `KnowledgeIndexService.integrity()` теперь проверяет также `programming/lessons.json`, а не только Voice и Music Production;
- реальная проверка `GET /knowledge/integrity`: `ok=true`, ошибок и предупреждений нет, `lesson_audio_records=62`, `lesson_audio_ready=32`;
- исправлен устаревший индекс Voice Production: `audio_status=AUDIO_READY`, 6 из 6 WAV готовы;
- физические корни `knowledge3`, `offline_knowledge` и `voice_responses` по-прежнему раздельны;
- backend оставлен запущенным после проверки.

## Очередь 0221 — Programming Mentor: возобновляемое пополнение WAV

Дата: 2026-11-15

- генератор Fish Audio продолжен четырьмя уроками: `python-001`, `python-002`, `python-003`, `html-001`, `html-002`;
- каждый WAV записан в `data/knowledge3/programming/audio` с проверкой SoundFile, исходные JSON и существующие WAV не перезаписывались;
- две отдельные команды с `--limit 3` и `--limit 1` подтвердили продолжение с первой отсутствующей записи;
- HTTP-поиск «HTML форма» вернул `html-002-form` со статусом `AUDIO_READY`, `has_audio=true` и связанным WAV;
- `/knowledge/integrity`: `ok=true`, `lesson_audio_records=62`, `lesson_audio_ready=36`, ошибок нет.

## Очередь 0222 — Personal Music Intelligence: reports and comparisons

Дата: 2026-11-15

- добавлен read-only `artist_report()` с разделением `LOCAL_COLLECTION` и `FULL_DISCOGRAPHY`;
- добавлен расчёт отсутствующих релизов по внешнему reference-каталогу без изменения `E:\Музыка`;
- добавлен `compare_artists()` и endpoint `POST /knowledge/music/compare`;
- добавлен endpoint `GET /knowledge/music/artist`;
- реальная проверка: `Trivium` вернул 11 reference-релизов и источники, `Arch Enemy` участвует в сравнении;
- Python-компиляция и HTTP-сценарии прошли, backend оставлен запущенным.

## Очередь 0223 — Personal Music Intelligence: технические метаданные

Дата: 2026-11-15

- `build_knowledge_index.py` получил read-only FFprobe fallback, когда Mutagen недоступен;
- добавлены UTF-8 decoding, ограниченный timeout 3 секунды и пул из 8 потоков для файловой коллекции;
- пересборка завершена без изменения `E:\Музыка`: 5 733 трека, 135 исполнителей, 613 альбомов;
- фактически заполнены длительность и техническое качество у 5 733 из 5 733 треков, форматы: MP3 5 599, FLAC 134;
- `GET /knowledge/music/metadata` подтвердил `known_duration=5733`, `known_quality=5733`;
- существующие поля Knowledge 3.0 в `index.json` сохранены, обновлены только производные музыкальные сведения.

## Очередь 0224 — Programming Mentor: Fish Audio batch

Дата: 2026-11-15

- создано ещё 5 новых WAV: `php-001-syntax`, `php-002-pdo`, `wordpress-001-hooks`, `wordpress-002-rest`, `react-001-component`;
- общий Programming Mentor audio progress: 10 из 31 урока готовы, 21 ожидает генерации;
- HTTP-сценарий запроса «PHP синтаксис» вернул текстовый ответ и связанный `php-001-syntax.wav`;
- Integrity после batch: `ok=true`, `lesson_audio_records=62`, `lesson_audio_ready=41`;
- существующие WAV не перезаписывались, очередь Music/Voice не изменялась.

## Очередь 0225 — Programming Mentor: аудиобиблиотека завершена

Дата: 2026-11-15

- возобновляемая генерация завершена для всех 31 урока Programming Mentor;
- индекс: `audio_ready=31`, `audio_pending=0`, `audio_status=AUDIO_READY`;
- проверены все 31 WAV через SoundFile: пустых/повреждённых файлов нет, метаданные валидны;
- общий `GET /knowledge/integrity`: `ok=true`, `lesson_audio_records=62`, `lesson_audio_ready=62`;
- связка текста и аудио работает через единый Knowledge Search; существующие библиотеки не перезаписывались.

## Очередь 0226 — Offline Knowledge: подтверждение и Integrity

Дата: 2026-11-15

- проверено: 405 тем, 4 050 WAV-вариантов, все физические ready-файлы существуют и непустые;
- после ранее подтверждённого пользователем review массово исправлены только метаданные статуса: `verified=true`, `review_status=USER_CONFIRMED`; тексты, источники и WAV не менялись;
- `KnowledgeIndexService.integrity()` теперь проверяет и раздельное дерево `data/offline_knowledge/audio`, включая каждый вариант;
- HTTP-сценарий «Что такое Intel 8086?» вернул offline-ответ и конкретный WAV `variant_02.wav`;
- Integrity после перезапуска backend: `ok=true`, Knowledge 3.0 `62/62`, Offline Knowledge `4050/4050` ready-аудио.

## Очередь 0202 — безопасный DAW/Cubase control MVP

Дата: 2026-11-15

Реализовано:

- `backend/services/daw_control_service.py` теперь имеет ограниченный реестр
  действий `open_documentation`, `inspect_project`, `launch`;
- добавлены `/knowledge/daw/action/plan` и `/knowledge/daw/action/execute`;
- запуск разрешается только для обнаруженного Cubase/REAPER из фиксированных
  vendor-путей и только с `confirmed=true`; произвольные команды и shell-ввод
  не принимаются;
- инспекция проектов остаётся read-only и возвращает `.cpr`, медиа и расширения;
- проверено: Python-компиляция и прямой план Steinberg documentation; запуск без
  подтверждения не выполняется.

Следующий рабочий шаг: подключить этот план действий к существующему Command
Router и UI подтверждения, затем проверить реальный пользовательский сценарий
на обнаруженном Cubase без автоматического изменения проекта.

## Очередь 0203 — голосовой маршрут Cubase

Дата: 2026-11-15

Команда `open_cubase` добавлена в существующий `commands.yaml` и `computer_control`
router. Она использует только `ApplicationService` и обнаруженный ярлык/путь,
не выполняет shell-команду и сообщает, если Cubase не найден. Добавлены варианты
«открой/запусти Cubase», «Кубейс 13», «программа для записи», «студия».

## Очередь 0204 — продолжение аудиобиблиотеки Knowledge 3.0

Дата: 2026-11-15

Без остановки существующей архитектуры сгенерированы новые уникальные WAV:

- `data/knowledge3/audio/lesson_audio/audio-lufs.wav`;
- `data/knowledge3/audio/lesson_audio/cubase-group-channel.wav`.

Генератор `backend/knowledge3/generate_audio_material.py` возобновляемый:
готовые непустые файлы пропускаются, запись идёт только в `lesson_audio`,
текст и `audio_status` сохраняются в `lessons.json`. После пакета проверено:
31 аудиоматериал в общей проверке (6 voice + 25 audio), 12 валидных WAV,
ошибок целостности нет; в аудио-уроках 6 готовых и 19 ожидают генерации.

После этого продолжена следующая партия без конкурирующего процесса:
`cubase-fx-send.wav` и `cubase-sidechain.wav`. Индекс обновлён до 8 готовых
аудиоуроков и 17 ожидающих; физическая проверка остаётся зелёной.

Следующая партия добавила `cubase-stems.wav` и `metal-guitar-balance.wav`.
Индекс обновлён до 10 готовых аудиоуроков и 15 ожидающих; существующие WAV не
перезаписывались, проверка разделённых хранилищ и непустых файлов пройдена.

## Очередь 0205 — автоматическая синхронизация аудиоиндекса

Дата: 2026-11-15

`generate_audio_material.py` теперь после каждой партии автоматически обновляет
аудиоблок `data/knowledge3/index.json`: число уроков, готовых и ожидающих WAV,
а также статус библиотеки. Это устраняет расхождение между `lessons.json` и
общим Knowledge Index при возобновлении генерации. Компиляция и integrity-check
пройдены: 31 материал, 16 валидных WAV в объединённой проверке.

## Очередь 0206 — единый поиск DAW и Mixing

Дата: 2026-11-15

Добавлены отдельные read-only каталоги `data/knowledge3/daw/catalog.json` и
`data/knowledge3/mixing/catalog.json`. `KnowledgeSearchService` теперь ищет по
ним вместе с Offline Knowledge, Programming, Audio, Guitar и остальными
источниками. Проверены реальные вызовы: запрос `sidechain` возвращает карточку
DAW и связанный аудиоурок Cubase; запрос `LUFS true peak` возвращает карточку
аудиоурока и его WAV. Старые физические хранилища не объединялись.

HTTP-проверка через FastAPI также пройдена: `/knowledge/integrity` вернул
`ok=true`, `/knowledge/search` и `/knowledge/answer` нашли `audio-gain-staging`
и вернули связанный WAV, план Cubase вернул официальную документацию, а запуск
без `confirmed=true` был корректно отклонён. Вывод терминала может отображать
кириллицу с заменой кодовой страницы, сами JSON-файлы сохранены в UTF-8.

## Очередь 0207 — расширение Programming Mentor

Дата: 2026-11-15

Curriculum расширен с 21 до 31 урока: добавлены доступность HTML, PHP-входные
данные, WordPress security, Python testing, React forms, React Native permissions,
Flutter async, Git tags, SQL transactions и FastAPI dependencies. Индекс обновлён
автоматически seed-скриптом. Для новых правил проверки исправлены статические
проверки HTML accessibility и SQL transaction; реальные проверки трёх новых
уроков вернули 100%.

HTTP-сценарий Programming Mentor проверен: фильтр уроков SQL вернул все 3
урока, проверка `sql-003-transaction` вернула 100% и сохранила прогресс. Добавлен
явный GET `/mentor/programming/progress`, чтобы прогресс можно было получать
отдельно, а не только вложенным в список уроков.

## Очередь 0210 — Cubase editing audio

Дата: 2026-11-15

Fish Audio успешно создал `cubase-audiowarp.wav` и `cubase-comping.wav`.
Автоматический индекс показывает 16 из 25 аудиоуроков готовыми и 9 ожидающими;
общая integrity-проверка — 22 валидных WAV, `ok=true`, без перезаписи старых
файлов.

## Очередь 0211 — Cubase quantize и MixConsole

Дата: 2026-11-15

Созданы `cubase-quantize.wav` и `cubase-mixconsole.wav`. Автоматический индекс
показывает 18 из 25 готовых аудиоуроков и 7 ожидающих; объединённая проверка
подтвердила 24 валидных WAV и `ok=true`.

## Очередь 0212 — Cubase project settings и Pro-Q 3

Дата: 2026-11-15

Созданы `cubase-project-settings.wav` и `plugin-pro-q3-workflow.wav`.
В очереди осталось 5 из 25 аудиоуроков; индекс показывает 20 готовых и 5
ожидающих, общая проверка — 26 валидных WAV и `ok=true`.

## Очередь 0215 — завершение текущей аудиочереди

Дата: 2026-11-15

Создан финальный файл `plugin-guitar-rig-workflow.wav`. Текущая очередь
Knowledge 3.0 полностью озвучена: 25/25 аудиоуроков, `AUDIO_READY`, ожидающих
материалов нет. Вместе с 6 Voice Production уроками integrity-проверка
подтвердила 31/31 валидный WAV, физические хранилища раздельны, `ok=true`.
Компиляция генератора, поискового слоя, Programming Mentor и FastAPI прошла.

## Очередь 0214 — Ozone и Nectar workflows

Дата: 2026-11-15

Созданы `plugin-ozone9-workflow.wav` и `plugin-nectar3-workflow.wav`.
Готово 24 из 25 аудиоуроков, остался 1; общая integrity-проверка показывает
30 валидных WAV и `ok=true`.

## Очередь 0213 — plugin workflows

Дата: 2026-11-15

Созданы `plugin-pro-c2-workflow.wav` и `plugin-saturn2-workflow.wav`.
Готово 22 из 25 аудиоуроков, осталось 3; общая integrity-проверка показывает
28 валидных WAV и `ok=true`.

## Очередь 0216 — Coding Developer: JavaScript sandbox

Дата: 2026-11-15

Добавлены bounded Node.js-сценарии без shell и без установки пакетов:
`POST /coding/sandbox/javascript` и `POST /coding/projects/javascript`.
Проекты создаются только в `data/knowledge3/coding_projects`, повторная запись
существующего проекта возвращает конфликт, список расширений ограничен `.js`,
`.json`, `.md`, `.txt`, а `test.js` запускается с таймаутом. Python-контур не
изменён.

Проверка выявила и исправила общий дефект test-entrypoint: тест теперь
запускается как отдельный `test.js`/`test_main.py` и не перезаписывает основной
`main.js`/`main.py`. Проверены Node.js 20.20.0, локальный проект с `assert` и
HTTP `POST /coding/sandbox/javascript` — результат `42`, статус 200.

Дополнительно исправлен статус DAW summary: вместо устаревшего
`not_implemented` API теперь сообщает `confirmation_first`, перечисляет
`inspect_project` и `launch`, а инспекцию проекта явно помечает read-only.

## Очередь 0208 — очередная партия Fish Audio

Дата: 2026-11-15

Сгенерированы и проверены `vocal-depth.wav` и `cubase-routing.wav`. Индекс
синхронизирован автоматически: 12 из 25 аудиоуроков готовы, 13 ожидают.
Общая проверка Knowledge Index показывает 18 валидных WAV (12 Audio + 6 Voice),
ошибок нет.

## Очередь 0209 — партия Cubase automation

Дата: 2026-11-15

Добавлены `cubase-automation.wav` и `cubase-vari-audio.wav`. Индекс Fish Audio
синхронизирован автоматически: 14 из 25 аудиоуроков готовы, 11 ожидают;
общая integrity-проверка показывает 20 валидных WAV и `ok=true`.

## Аудит 0001 — диагностика молчания Jarvis Assist

Дата: 2026-10-26

Запрос:

- проверить структуру проекта и канонический runtime;
- проверить ассистента, voice engine, микрофон и голосовую кнопку;
- проверить Ollama и включить её, если она выключена;
- проверить состояние обучения синтеза и голосовых моделей.

### Карта текущей структуры

- канонический backend: `backend/main.py`, FastAPI на `127.0.0.1:8000`;
- desktop-клиент: `frontend/jarvis_ui.py`;
- агентный контур: `backend/core`, `backend/agents`, `backend/services`;
- voice engine: `backend/voice_engine`;
- наборы и обучение: `backend/voice_engine/dataset`, результат обучения —
  `jarvis_voice`;
- старые/экспериментальные реализации голоса: `legacy_main.py`, `jarvis_fast.py`,
  `voice/jarvis_voice.py`, `voice/jarvis_voice2.py`, `voice_listener.py`.

### Подтверждённые причины, почему Jarvis молчит

1. Wake-word и постоянный слушатель не запускаются из канонического backend:
   `wakeword_engine.wait_wakeword()` существует, но `backend/main.py` его не
   импортирует и не запускает в фоне.
2. `VoiceAgent` — только агент обработки уже созданного `tool_request`; он не
   является микрофонным listener'ом и не начинает голосовую сессию сам.
3. При старте backend `VoiceAgent` отключается:
   `ImportError: cannot import name 'BeamSearchScorer' from 'transformers'`.
   В окружении зафиксирован `transformers 5.3.0`, несовместимый с текущим
   импортом Coqui TTS.
4. Кнопка микрофона в `frontend/chat_composer.py` только эмитит
   `voice_requested`; подключения этого сигнала в `JarvisUI` к записи,
   распознаванию или `/chat` нет. Это заглушка UI, а не переключатель
   рабочего voice runtime.
5. В `tts.py` указан `VOICE_SAMPLE = "voice_dataset/voice.wav"`, но такого
   файла в проекте нет. Даже после исправления импорта TTS этот путь не даёт
   завершённого пользовательского voice clone.
6. Предзаписанные ответы `ok.wav`, `greet1.wav`, `thanks.wav`, которые ожидает
   `VoiceAgent`, отсутствуют в `backend/voice_engine/sound`; там есть русские
   WAV-файлы с другими именами.

### Микрофон

- UI-поле «Микрофон» — это выбор индекса физического устройства и сохранение
  через `POST /hardware/settings`; оно не включает/выключает слушатель и не
  меняет состояние Jarvis.
- текущая настройка оставлена `-1` («системный выбор»);
- системный input на момент проверки — `e2eSoft iVCam` (device 1);
- 1-секундный входной тест открыл устройство, но дал почти нулевой сигнал:
  RMS около `0.0000146`, peak около `0.0000305`;
- `wakeword_engine.py` при `-1` выбирает первый найденный input (device 0),
  а не Windows default device 1. Даже при запуске wakeword это может выбирать
  не тот микрофон.

### Ollama и ИИ

- Ollama была запущена на ПК в ходе проверки;
- процесс: Ollama `0.30.11`, API `http://127.0.0.1:11434` отвечает;
- установленная модель: только `phi3:latest`;
- Jarvis настроен на `qwen2.5:7b-q4_K_M`, которой нет;
- прямой запрос к qwen вернул HTTP 404;
- прямой запрос к `phi3:latest` вернул `OK`;
- `/runtime/providers` ошибочно считает Ollama доступной, потому что проверяет
  доступность API, а не наличие выбранной модели;
- `/chat` отвечает stub-режимом, поэтому текущее понимание команд через
  выбранную Ollama-модель не подтверждено.

### Синтез и обучение

- зависимости `TTS`, `faster_whisper`, `sounddevice`, `soundfile`,
  `openwakeword`, `silero_vad`, `vosk` установлены в `backend/jarvis_env`;
- wakeword-модуль импортируется и находит input, но сам loop не запущен;
- `voice_listener.py` существует отдельно и загружает Whisper `base`, но не
  подключён к каноническому runtime;
- датасет содержит 61 исходный WAV, 427 обработанных WAV и 370 строк в
  `metadata.csv`;
- в `jarvis_voice` есть только прерванные запуски: `checkpoint_0.pth` и
  `checkpoint_1.pth`; логи показывают KeyboardInterrupt на epoch `0/120`;
- финальной обученной модели/подключения к `tts.py` не найдено.

### Проверка запуска

- `/health`: HTTP 200, `ollama: true`;
- `/runtime/providers?probe=true`: backend отвечает, выбран provider `ollama`;
- smoke-test `/chat`: backend отвечает, но результат содержит `Jarvis (stub
  режим)` из-за отсутствующей qwen-модели;
- `backend/tests`: `14` тестов пройдены через `unittest discover`;
- целевые voice/frontend-файлы прошли `py_compile`;
- окно `Jarvis Assist` запущено.
- smoke-test `/chat` создал технический чат `__assist_audit__`; история не
  удалялась без отдельного согласования пользователя.

### Ограничения

- реальный разговорный wakeword-cycle не выполнялся, потому что listener не
  подключён к backend, а `VoiceAgent` отключается на импорте TTS;
- пользовательская речь в микрофонном тесте не записывалась на диск;
- исходный `docs/HANDOFF.md` не изменялся;
- исходный код в этой очереди не изменялся; изменено только runtime-состояние
  Ollama (она запущена) и создан этот Assist-журнал.

### Следующая очередь

- согласовать модель Ollama: установить `qwen2.5:7b-q4_K_M` либо безопасно
  перевести конфигурацию на установленную `phi3:latest`;
- выбрать реальный input device вместо `-1`;
- исправить совместимость TTS/transformers и путь к voice sample;
- подключить listener → STT → `/chat` → TTS в канонический runtime;
- только после этого сделать live-тест «Jarvis» → команда → голосовой ответ.

## Аудит/очередь 0002 — подключение рабочего voice runtime

Дата: 2026-10-26

Перед завершением очереди создан snapshot:

- `backups/handoff-assist-0002-voice-runtime-20261026-215000/`

Изменения:

- добавлен `backend/services/voice_runtime.py` с реальным lifecycle
  микрофона, Vosk STT, wake-word `Jarvis`, маршрутизацией известных команд и
  разговорным LLM/TTS fallback;
- добавлены `/voice/start`, `/voice/stop`, `/voice/status`;
- START в desktop UI и кнопка микрофона composer подключены к одному voice
  runtime;
- выбранный индекс микрофона передаётся в `/voice/start` и применяется
  backend, а `/hardware/settings` обновляет активный runtime;
- default Ollama синхронизирован с установленной `phi3:latest`;
- `tts.py` переведён на lazy-load XTTS и абсолютный sample
  `backend/voice_engine/sound/Да сэр.wav`;
- `transformers` закреплён на `4.49.0`, совместимом с установленным Coqui
  TTS;
- README обновлён: backend запускается из `backend/jarvis_env`.

Проверка:

- `py_compile` изменённых backend/frontend/voice-файлов: пройден;
- `unittest discover`: 14 тестов пройдены;
- `/voice/start` с `microphone_index=2`: `enabled=true`, `listening=true`;
- `/voice/stop`: `enabled=false`, `listening=false`;
- `/runtime/providers`: выбран `ollama`, модель `phi3:latest`;
- `/chat`: ответ пришёл от установленной Ollama, больше не stub;
- XTTS сгенерировала тестовый WAV из локального sample;
- backend запущен из `backend/jarvis_env`, VoiceAgent зарегистрирован.

Ограничения:

- Vosk распознаёт только финальные фразы после wake-word; полноценный live
  тест с произнесением пользователя ещё не выполнялся;
- текущий разговорный голос использует XTTS voice cloning по WAV sample;
  VITS-обучение пользователя ещё не завершено и в runtime не подключено;
- свободная фраза зависит от качества установленной `phi3:latest`;
- опасные команды из старого `commands.yaml` требуют отдельной политики
  подтверждения перед production-использованием.

Откат:

- для восстановления состояния этой очереди использовать snapshot выше;
- основной `docs/HANDOFF.md` в этой очереди не изменялся.

## Очередь 0003 — вариативные ответы, Telegram, звук и запуск VITS

Дата: 2026-10-26

Изменения:

- источником команд подтверждён `backend/voice_engine/commands.yaml`, который
  загружается каноническим `backend/computer_control.py`; legacy-скрипты имеют
  отдельные старые таблицы и не являются основой текущего runtime;
- добавлена таблица WAV-ответов по intent вместо безусловного `Да сэр.wav`;
- `open_telegram` теперь ищет Desktop-клиент, затем использует `tg://`, а при
  отсутствии протокола открывает Telegram Web;
- добавлены реальные `sound_on/sound_off` через Windows endpoint и actions для
  музыкальных, игровых и аудио-переключений;
- создан `backend/voice_engine/train_vits.py`, чтобы Coqui Trainer не пытался
  скопировать тренировочный скрипт поверх самого себя;
- VITS запущен с продолжением из
  `jarvis_voice/run-March-12-2026_01+16AM-0000000/checkpoint_1.pth`.

Состояние VITS на момент записи:

- процесс находится в `TRAINING`, `EPOCH: 0/120`;
- используется CPU, CUDA отсутствует;
- найдено 370 обучающих файлов, batch group size 24;
- процесс оставлен работать в активной сессии агента.

Проверка:

- `find_intent("открой телеграм")` → `open_telegram`;
- `find_intent("выключи звук")` → `sound_off`;
- `find_intent("включи звук")` → `sound_on`;
- `computer_control.ACTIONS` содержит Telegram, sound и media actions;
- изменённые файлы прошли `py_compile`.
- после перезапуска backend настройка синхронизирована: `microphone_index=2`.

Ограничения:

- Telegram Desktop на проверке не подтверждён; при его отсутствии теперь
  используется Telegram Web;
- отдельный WAV для каждого intent существует не для всех команд, поэтому
  часть intent использует общий, но уже не безусловный fallback;
- VITS на CPU может обучаться много часов/дней; финальный checkpoint и
  подключение VITS к TTS пока не подтверждены.

## Очередь 0004 — legacy-аудит, follow-up диалог и автозапуск

Дата: 2026-10-26

Сравнение voice-реализаций:

- `backend/voice_engine/legacy_main.py` сильнее по старой диалоговой логике:
  после wake word он держит 10-секундное окно продолжения и разделяет команды
  и разговор; при этом скрипт устарел — старый OpenAI API, hardcoded cwd,
  Porcupine token и отдельный старый набор команд.
- `backend/voice_engine/voice/jarvis_voice.py` — сильнейшая современная база:
  текущие wakeword/STT/`computer_control`/HTTP chat пути.
- `backend/voice_engine/voice/jarvis_voice2.py` проще и быстрее, но использует
  tiny-модель Whisper и короткую фиксированную запись, поэтому точность ниже.
- В runtime оставлен современный путь, а полезная 10-секундная follow-up
  логика перенесена без возврата legacy-скрипта.

Изменения:

- после фразы «Джарвис» без команды runtime отвечает WAV «Да, сэр» и принимает
  следующую фразу до 10 секунд без повторного wake word;
- во время WAV/TTS микрофонный callback игнорирует вход, чтобы Jarvis не
  распознавал собственный голос;
- перед долгим Ollama/XTTS ответом проигрывается «Загружаю, сэр»;
- `frontend/jarvis_ui.py` автоматически включает реальный `/voice/start` при
  открытии окна и повторяет попытку до 10 раз, если backend ещё стартует;
- автозапуск использует выбранный UI микрофон, текущая синхронизация — индекс
  `2` (`Mic/Line/Inst 1-2 (Minifuse 2)`);
- создана тихая почасовая проверка обучения VITS: процесс, лог,
  checkpoint-файлы и traceback; уведомление только при изменении состояния.

Проверка:

- backend после перезапуска поднят на `127.0.0.1:8000`, `/health` вернул
  `ollama=true`;
- окно `Jarvis Assist` перезапущено и само включило runtime: `enabled=true`,
  `listening=true`, `microphone_index=2`;
- программный smoke-test подтвердил последовательность wake word → WAV ack →
  follow-up «привет как дела» → разговорный LLM путь;
- `py_compile` и `git diff --check` пройдены;
- VITS снова запущен с `checkpoint_1.pth`; активны parent/worker процессы,
  обучение CPU, новых checkpoint после перезапуска пока нет.

Ограничения:

- XTTS сейчас отвечает тембром WAV sample, но короткий ответ может занимать
  несколько секунд; обученная VITS-модель ещё не готова и не подключена;
- реальный тест голосом пользователя зависит от качества Vosk и акустики,
  поэтому follow-up проверен программно, а не записью речи на диск;
- `docs/HANDOFF.md` в этой очереди не изменялся.

### Дополнение к очереди 0004 — устойчивый запуск VITS

Первый повторный запуск VITS завершился до эпохи из-за внешнего Coqui
telemetry ping: `requests ReadTimeout` на `coqui.gateway.scarf.sh`. В
`backend/voice_engine/train_vits.py` до импорта `Trainer` выставлен
`TRAINER_TELEMETRY=0`, чтобы локальное обучение не зависело от сети.

После этого обучение снова вошло в `EPOCH: 0/120` и `TRAINING`; найдено 370
файлов, подготовлено 359 экземпляров после preprocessing, CUDA по-прежнему
недоступна. На момент записи новых checkpoint ещё нет, процесс оставлен
работать. Мониторинг будет считать внешний telemetry timeout ошибкой только
если он повторится после этого исправления.

## Очередь 0005 — живой разговор и реальные sidebar-переключатели

Дата: 2026-10-26

Диагностика пользовательского сценария:

- после «привет как дела» Ollama действительно вернула ответ, а XTTS сообщил
  `tts_available=true`, но ответ оказался очень длинным; синхронный listener
  был занят генерацией и озвучкой, поэтому продолжение воспринималось как
  молчание/стоп;
- sidebar-переключатели «Ассистент» и «Микрофон» были декоративными: они не
  имели обработчиков и не отражали `/voice/status`.

Изменения:

- разговорный ответ перенесён в отдельный `jarvis-conversation` worker через
  очередь, чтобы STT listener не блокировался на Ollama и XTTS;
- добавлена короткая системная инструкция Jarvis и ограничение озвучиваемого
  ответа 700 символами;
- добавлена история последних сообщений, чтобы разговор был контекстным;
- четыре WAV-правила подключены:
  - ожидание/долгий поиск — `Всегда к вашим услугам сэр.wav`;
  - пустой ответ/невозможность ответить — `Я провел симуляции со всеми
    известными элементами.wav`;
  - ошибка LLM/TTS — `Сэр, для реальной попытки полета не просчитаны еще
    террабайты данных.wav`;
  - непонятый запрос — `Создать визуальный образ по новым спецификациям.wav`;
- оба sidebar toggle теперь управляют тем же реальным voice runtime и
  принудительно синхронизируются с его `enabled/listening` состоянием.

Проверка:

- после перезапуска backend и UI: `enabled=true`, `listening=true`,
  `microphone_index=2`;
- все четыре WAV-файла существуют;
- frontend/backend/тренировочный entrypoint прошли `py_compile`;
- VITS после первого runtime-ошибочного batch перезапущен с безопасными
  параметрами уменьшенного batch/drop-last; parent и worker процессы активны,
  обучение снова находится в `TRAINING`, новых checkpoint пока нет.

Логика команд:

- `jarvis_voice.py` сам не является текущим исполнительным циклом и напрямую
  не читает таблицу команд;
- текущий runtime вызывает `computer_control.find_intent()` и
  `computer_control.run_command()`;
- `computer_control.py` загружает `backend/voice_engine/commands.yaml`,
  ищет совпадение по фразе/синонимам, возвращает intent и выполняет action;
- если intent найден — выполняется команда и проигрывается WAV для этого
  intent; если intent не найден — фраза уходит в разговорный Ollama/TTS путь.

## Очередь 0006 — lifecycle при закрытии Jarvis и проверка Crazy Tad

Дата: 2026-10-26

Диагностика:

- в текущем `Crazy Tad` нет импорта, запуска или вызова Jarvis;
- Crazy Tad поднимает собственный backend на `127.0.0.1:8765`;
- Jarvis backend работает отдельно на `127.0.0.1:8000`;
- причина самопроизвольной работы Jarvis — voice runtime оставался включённым
  в отдельном backend-процессе после закрытия/перезапуска окна Jarvis;
- frontend имел автозапуск `/voice/start`, но не имел симметричного
  `/voice/stop` в `closeEvent`.

Исправление:

- в `frontend/jarvis_ui.py` добавлен `closeEvent`, который отправляет
  `/voice/stop` перед закрытием окна и освобождает микрофон;
- Crazy Tad не изменялся.

Проверка:

- Jarvis повторно запущен для тестов;
- окно `Jarvis Assist` найдено;
- `/voice/status`: `enabled=true`, `listening=true`, `microphone_index=2`;
- подтверждено, что Crazy Tad не является источником вызова Jarvis по исходному
  коду; приложения используют разные backend-порты.

Фактический lifecycle smoke-test:

- окно `Jarvis Assist` корректно закрыто через `WM_CLOSE`;
- после закрытия `/voice/status` подтвердил `enabled=false`, `listening=false`;
- Jarvis затем снова запущен для пользовательских тестов и автоматически
  вернулся в `enabled=true`, `listening=true`, `microphone_index=2`.

Примечание по VITS: повтор с `drop_last` также завершился внутри Coqui VITS
на `RuntimeError: min(): ... input.numel() == 0`; обучение сейчас остановлено,
нового checkpoint нет. Это отдельная проблема датасета/батчинга и не связана с
тем, что Crazy Tad запускает Jarvis.

## Очередь 0007 — окно диагностики голосового обработчика

Дата: 2026-10-27

Изменения:

- в `backend/services/voice_runtime.py` добавлено поле `phase` со стадиями
  `запускается`, `слушаю`, `распознал`, `проверяю команду`, `выполняю команду`,
  `ожидаю ответ`, `думаю`, `говорю WAV`, `говорю AI`, `ошибка`;
- в `frontend/jarvis_ui.py` добавлена read-only панель голосовой диагностики,
  показывающая состояние, последнюю услышанную фразу, последний ответ и ошибку;
- панель обновляется каждые 1.5 секунды через `/voice/status`.

Проверка:

- backend и frontend перезапущены;
- `/voice/status`: `enabled=true`, `listening=true`, `microphone_index=2`,
  `phase=слушаю`;
- `py_compile frontend/jarvis_ui.py backend/services/voice_runtime.py` пройден;
- визуальный Windows capture QtWebEngine дважды не предоставил screenshot из-за
  таймаута geometry, но accessibility-дерево подтвердило окно `Jarvis Assist`;
- окно оставлено открытым для ручного голосового теста.

## Очередь 0008 — восстановление conversation worker и audio timeout

Дата: 2026-10-27

Диагностика:

- фраза `джарвис как дела` распознавалась, но оставалась на стадии
  `ожидаю ответ`; фактический статус показал `conversation_worker=false`;
- после ручного повторного `/voice/start` worker восстановился, Ollama вернула
  `Прекрасно, спасибо!`, а XTTS озвучила ответ;
- генерация/озвучка XTTS на CPU заняла около 13.7 секунд, поэтому `говорю AI`
  может выглядеть как длительная пауза, даже когда ответ уже готов.

Изменения:

- `VoiceRuntime.start()` теперь гарантированно проверяет и восстанавливает
  conversation worker даже если microphone thread уже работает;
- `/voice/status` теперь показывает `conversation_worker` и
  `conversation_queue_size`;
- UI автоматически вызывает безопасный повторный `/voice/start`, если listener
  включён, но conversation worker пропал;
- `voice_player.py` и `tts.py` больше не ждут аудиодрайвер бесконечно: добавлен
  ограниченный playback wait с `sd.stop()` при зависшем устройстве;
- стадия ожидания ответа заменена на `думаю`, чтобы не создавать впечатление,
  что Jarvis ждёт дополнительную реплику пользователя.

Проверка:

- backend/frontend перезапущены;
- `enabled=true`, `listening=true`, `microphone_index=2`;
- `conversation_worker=true`, `conversation_queue_size=0` после запуска;
- `py_compile` для voice runtime, TTS, player и frontend пройден.

## Очередь 0009 — подготовка внешних голосовых записей Jarvis

Дата: 2026-10-27

Источник:

- `C:\Users\Данил\Downloads\1027.mp3`;
- `C:\Users\Данил\Downloads\Вячеслав Баранов.mp3` (пользователь упоминал
  `.mp4`, фактический файл на диске — `.mp3`).

Изменения:

- создана отдельная staging-папка
  `backend/voice_engine/dataset/external_jarvis_staging`;
- MP3 конвертированы в mono WAV 22050 Гц:
  `jarvis_1027.wav`, `jarvis_vyacheslav.wav`;
- добавлен отдельный `metadata.csv` с расшифровками пользователя как
  эталонным текстом;
- исходные MP3 и основной `dataset/metadata.csv` не изменялись.

Проверка и ограничения:

- длительность исходников: примерно 18.73 и 20.51 секунды;
- для качественного VITS-обучения записи нужно разделить на короткие фразы и
  проверить совпадение текста с реально произнесёнными словами;
- автоматическая расшифровка использовалась только для оценки границ фраз и не
  заменяла текст пользователя;
- обучение VITS по этим файлам ещё не запускалось.

## Очередь 0010 — сегментация и запуск VITS на объединённой копии

Дата: 2026-10-27

Изменения:

- внешние записи разделены по паузам на 6 смысловых фраз:
  3 из `1027.mp3` и 3 из `Вячеслав Баранов.mp3`;
- фрагменты приведены к mono WAV 22050 Гц в
  `backend/voice_engine/dataset/external_jarvis_staging/segments`;
- создан отдельный набор
  `backend/voice_engine/dataset/vits_training_20261027b`;
- в копию вошли 370 пригодных исходных фраз и 6 новых, всего 376;
- создан отдельный конфиг с output path
  `C:/projects/Jarvis/jarvis_voice_external_20261027`;
- основной датасет и предыдущие checkpoints не изменялись.

Проверка:

- VITS обнаружил 376 файлов;
- после eval split подготовлено 365 тренировочных экземпляров;
- pre-computing phonemes завершён без ошибки;
- первый шаг эпохи 0 выполнен, ошибка `input.numel() == 0` не повторилась;
- обучение продолжает выполняться в отдельном процессе на CPU.

## Очередь 0011 — подготовка `1027(1).mp4`

Дата: 2026-10-27

Изменения:

- из `C:\Users\Данил\Downloads\1027(1).mp4` извлечена AAC-дорожка;
- аудио приведено к mono WAV 22050 Гц:
  `backend/voice_engine/dataset/external_jarvis_staging/1027_1_extracted.wav`;
- локальная `faster-whisper base` обнаружила 30 речевых сегментов;
- создано 30 WAV-сегментов в
  `backend/voice_engine/dataset/external_jarvis_staging/1027_1_segments`;
- создан `1027_1_metadata_draft.csv` с автоматической черновой расшифровкой.

Ограничение:

- черновая расшифровка содержит сомнительные слова и имена собственные, поэтому
  новый файл не добавлялся в активный VITS-набор и не смешивался с текущим
  обучением;
- после проверки текста пользователя эти 30 сегментов можно добавить в новый
  training snapshot или использовать для продолжения обучения.

## Очередь 0012 — подготовка `1027(2).mp4`

Дата: 2026-10-27

Изменения:

- из `C:\Users\Данил\Downloads\1027(2).mp4` извлечена AAC-дорожка;
- аудио приведено к mono WAV 22050 Гц:
  `backend/voice_engine/dataset/external_jarvis_staging/1027_2_extracted.wav`;
- локальная `faster-whisper base` обнаружила 10 речевых сегментов;
- создано 10 WAV-сегментов в
  `backend/voice_engine/dataset/external_jarvis_staging/1027_2_segments`;
- создан `1027_2_metadata_draft.csv` с автоматической черновой расшифровкой.

Ограничение:

- имена, места и отдельные слова требуют проверки по аудио;
- файл не добавлялся в активный VITS-набор и текущее обучение не прерывалось;
- после подтверждения текста 10 сегментов можно добавить в отдельный snapshot.

## Очередь 0013 — проверка VITS и граница добавления новых фраз

Дата: 2026-10-27

Проверка:

- активного процесса обучения больше нет;
- запуск `vits_training_20261027b` завершился с прежней ошибкой
  `RuntimeError: min(): Expected reduction dim to be specified for
  input.numel() == 0` в VITS duration predictor;
- checkpoint нового запуска не создан;
- в основном `metadata.csv` 370 образцов, минимальная длительность 1.213 с,
  максимальное соотношение текста к аудио — около 20.46 символа/с;
- корпус требует дополнительной фильтрации/проверки перед новым запуском.

Новые материалы:

- `1027(1).mp4`: подготовлены 30 WAV-сегментов и draft metadata;
- `1027(2).mp4`: подготовлены 10 WAV-сегментов и draft metadata;
- автоматические тексты пока не добавлены в обучение, так как содержат
  сомнительные слова и имена собственные;
- подтверждённые ранее 6 внешних фраз уже присутствовали в неудачном snapshot.

## Очередь 0014 — очищенный запуск с видимым логом

Дата: 2026-10-27

Изменения:

- создан snapshot `vits_training_20261027e`;
- из старого корпуса оставлено 332 образца, отфильтровано 36 подозрительных
  записей по длительности и соотношению текста к аудио;
- добавлены 46 внешних фраз: 6 подтверждённых и 40 с автоматической draft
  расшифровкой из двух новых видео;
- всего в snapshot 378 фраз;
- обучение запущено в отдельном видимом PowerShell-окне с output path
  `C:/projects/Jarvis/jarvis_voice_external_20261027e`.

Проверка:

- процесс VITS активен;
- `EPOCH 0/120`, `STEP 0/62` выполнен;
- первый шаг нового запуска не вызвал `input.numel() == 0`;
- наблюдаемый step time около 27.5 секунд на CPU;
- текущая машина: AMD Radeon RX 7600, установлен `torch 2.4.0+cpu`, поэтому
  CUDA/GPU-режим в текущем окружении не используется.

## Очередь 0015 — поиск причины VITS `input.numel() == 0`

Дата: 2026-10-27

Диагностика:

- изолированный проход по образцам подтвердил падение на `base_0078.wav`,
  затем на `base_0076.wav` и других старых образцах;
- проблема не сводится к одному WAV и возникает внутри
  `stochastic_duration_predictor.py` / `rational_quadratic_spline`;
- вторичный `PermissionError WinError 32` появляется при попытке Trainer
  удалить папку эксперимента с открытым логом и не является первопричиной.

Исправление запуска:

- параметр `use_sdp=false` перенесён в правильный раздел
  `model_args` конфигурации;
- проверка `load_config` подтвердила `model_args.use_sdp=False`;
- предыдущий процесс остановлен, новый запуск идёт в видимом PowerShell-окне с
  output path `C:/projects/Jarvis/jarvis_voice_external_20261027g`;
- в сгенерированном runtime-конфиге подтверждено `use_sdp: false`.

## Очередь 0016 — плавающий виджет состояния Jarvis

Дата: 2026-10-27

Изменения:

- встроенный `voice_debug` заменён отдельным `FloatingVoiceStatusWidget`;
- окно состояния теперь frameless/tool-виджет, который можно перетаскивать мышью
  за любую область текста;
- позиция сохраняется в `QSettings` внутри `widget_settings` и
  восстанавливается при следующем запуске;
- кнопка `OUT` теперь включает/выключает именно окно состояния, а не закрывает
  приложение;
- в настройках виджета добавлен параметр `Плавающее окно состояния Jarvis`;
- статус, распознанный текст, ответ и ошибка продолжают обновляться через
  `/voice/status` каждые 1.5 секунды.

Проверка:

- `py_compile frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен с новой реализацией;
- accessibility-дерево основного окна подтвердило, что HUD и кнопки загружены;
- screenshot/click-проверка отдельного Qt-окна ограничена таймаутом geometry
  QtWebEngine на текущем Windows-хосте; исходный интерфейс оставлен открытым для
  ручной проверки перетаскивания и `OUT`.

## Очередь 0017 — единый glass-стиль плавающего статуса и проверка обучения

Дата: 2026-10-27

Изменения:

- убран жёстко заданный зелёный фон floating status widget;
- виджет теперь получает градиент, прозрачность, шрифт, цвет текста и акцентную
  рамку из текущих настроек главного окна;
- изменение glass/opacity/accent/font настроек обновляет и плавающий статус;
- Jarvis перезапущен после правки, синтаксическая проверка пройдена.

Проверка VITS:

- текущий процесс `vits_training_20261027g` жив и отвечает;
- последний записанный этап остаётся `STEP 0/62`, CPU-процесс продолжает работать;
- log timestamp не обновился до следующего завершённого шага, поэтому обучение
  медленно считает следующий batch, а не завершило epoch;
- checkpoint пока не создан.

## Очередь 0018 — управление START/микрофоном и контекстные меню

Дата: 2026-10-27

Изменения:

- убран автоматический запуск voice runtime при открытии UI;
- при старте UI отправляется `/voice/stop`, а `START` остаётся единственным
  запуском Jarvis;
- переключатель `Ассистент` оставлен визуальной заглушкой и всегда возвращается
  во включённое состояние;
- переключатель `Микрофон` отделён от assistant state и управляет новым
  `POST /voice/microphone` без остановки Jarvis;
- `/voice/status` теперь сообщает `microphone_enabled`;
- `VoiceRuntime` перестаёт принимать аудиобуферы при выключенном микрофоне;
- правый клик по плавающему статусу открывает размеры `маленький/средний/большой`
  и закрытие виджета;
- правый клик по прозрачному главному HUD открывает `Новый чат`, `Агенты`,
  `Провайдеры`, `Выход`;
- добавлено повторное поднятие HUD-кнопок над декоративными слоями после построения
  интерфейса, чтобы убрать потерю кликов.

Проверка:

- `py_compile` backend/frontend пройден;
- `/voice/status` после UI startup показывает `enabled=false`;
- `/voice/start` возвращает `enabled=true`, `listening=true`;
- `/voice/microphone {enabled:false}` возвращает `microphone_enabled=false` и
  фазу `микрофон выключен`, не останавливая Jarvis;
- VITS продолжает обучение: последний проверенный этап `STEP 50/62`, процесс
  активен.

## Очередь 0019 — устранение перехвата мыши HUD

Дата: 2026-10-27

Диагностика и исправление:

- причина пропадающих кликов: полноразмерный `button_layer` в
  `QStackedLayout.StackAll` располагался поверх декоративного HUD и мог
  перехватывать события нижнего/верхнего ряда;
- `START` переведён в прямого дочернего элемента `hud_container`;
- полноразмерный слой кнопок удалён;
- после построения HUD все TECH-A и panel-кнопки принудительно поднимаются
  выше декоративных слоёв и явно оставляются mouse-enabled.

Проверка:

- Jarvis перезапущен;
- accessibility-дерево показывает `START` и все 8 верхних/нижних групп кнопок
  как отдельные элементы непосредственно внутри HUD;
- UI стартует в состоянии `Нажмите START, чтобы Jarvis начал слушать`;
- автоматический coordinate click на текущем QtWebEngine-хосте остаётся
  ограничен ошибкой `coordinate input geometry is unavailable`.

## Очередь 0020 — расширенные hitbox-зоны HUD-кнопок

Дата: 2026-10-27

Изменения:

- TECH-A боковые кнопки получили прозрачный запас клика по 8 px вокруг графики;
- верхние текстовые панели расширены до hitbox высотой 44 px и шириной на 18 px
  больше исходной;
- нижние иконки расширены до 56x48 px при сохранении визуального центра;
- anchor-координаты панелей сохраняются отдельно, поэтому увеличение hitbox не
  меняет их визуальную позицию;
- все зоны снова поднимаются поверх слоёв после построения HUD.

Проверка:

- `py_compile frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- accessibility-дерево подтверждает START, боковые/верхние панели и нижние
  кнопки как отдельные mouse-enabled элементы;
- VITS: эпоха 0 завершена, создан `best_model_62.pth`, начата эпоха 1/120.

## Очередь 0021 — мягкая тень виджета состояния

Дата: 2026-10-27

Изменения:

- яркая бирюзовая рамка у плавающего виджета состояния удалена;
- добавлена тонкая тень с размытием 9 px и низкой прозрачностью;
- стеклянный фон и наследование цветовой схемы главного окна сохранены.

Проверка:

- `py_compile frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- процесс VITS продолжает работать, эпоха 1/120 активна.

## Очередь 0022 — выравнивание hitbox в прозрачном режиме

Дата: 2026-10-27

Диагностика и исправление:

- в прозрачном frameless-режиме визуальный HUD и системная input-поверхность
  расходились по вертикали;
- для widget/VID-режима hitbox-зоны боковых, верхних и нижних кнопок подняты на
  12 px;
- обычный режим окна сохраняет нулевое смещение;
- базовые координаты hitbox сохранены отдельно, чтобы переключение режимов не
  накапливало смещение;
- после переключения режима кнопки повторно поднимаются над слоями.

Проверка:

- `py_compile frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- обучение VITS не затронуто, процесс остаётся активным.

## Очередь 0023 — отмена неверного смещения кнопок

Дата: 2026-10-27

Исправление:

- отменено экспериментальное смещение hitbox на 12 px в прозрачном режиме;
- кнопки и их визуальная графика возвращены на исходные координаты;
- метод выравнивания оставлен с нулевым смещением, чтобы не менять положение
  самих кнопок до реализации отдельного невидимого overlay-hitbox.

Проверка:

- `py_compile frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- VITS продолжает обучение: `STEP 13/62`, `GLOBAL_STEP 75`, лог обновляется.

## Очередь 0024 — устранение подвисаний HUD

Дата: 2026-10-27

Диагностика:

- VITS использует около 3.2 ГБ памяти и создаёт высокую конкуренцию за CPU;
- HUD на каждом кадре заново создавал и перекрашивал крупный CPU-спрайт;
- таймер анимации работал с периодом 16 ms.

Изменения:

- перекрашенные 40 кадров CPU-индикатора теперь создаются один раз и берутся из
  кэша;
- частота перерисовки HUD снижена до стабильных 30 FPS;
- приоритет обучения временно проверялся, затем восстановлен в `Normal` по
  требованию пользователя;
- Jarvis запущен с приоритетом `AboveNormal`, обучение не остановлено.

Проверка:

- `py_compile frontend/jarvis_hud.py frontend/jarvis_ui.py` пройден;
- UI перезапущен;
- процесс VITS остаётся активным.

## Очередь 0025 — возврат исходной плавности анимаций

Дата: 2026-10-27

По запросу пользователя отменены последние performance-изменения HUD:

- таймер анимации возвращён с 33 ms на исходные 16 ms;
- удалён кэш перекрашенных CPU-кадров;
- восстановлена исходная отрисовка CPU-анимации на каждом кадре;
- приоритеты Jarvis и VITS возвращены в `Normal`.

Проверка:

- `py_compile frontend/jarvis_hud.py frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- обучение VITS не остановлено.

## Очередь 0026 — каноническая LAN-прогресс-полоса

Дата: 2026-10-27

Изменения:

- левая LAN-секция перенесена на канонический центр TECH-A `(361,355)`;
- радиус линии установлен `263 px`, что соответствует диапазону `LineStart=261`
  и `LineLength=265` из исходного Rainmeter-конфига;
- толщина синей прогресс-полосы увеличена с 2 до 4 px;
- правая каноническая секция RAM/DISK не изменялась.

Проверка:

- `py_compile frontend/jarvis_hud.py frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен.

## Очередь 0027 — LAN-линии по размерам канонических правых линий

Дата: 2026-10-27

Изменения:

- LAN-дуги используют ту же геометрию, что и канонические RAM/DISK-линии:
  центр `(361,355)`, область `528x528`, радиус линии `264 px`, толщина `4 px`;
- верхняя дуга LAN окрашена в синий accent-цвет;
- нижняя дуга LAN окрашена в белый цвет;
- направление и раздельные значения upload/download сохранены.

Проверка:

- `py_compile frontend/jarvis_hud.py frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- правая секция RAM/DISK не изменялась.

## Очередь 0028 — небольшой сдвиг LAN-линий вправо

Дата: 2026-10-27

Изменения:

- live LAN-дуги сдвинуты вправо на 8 px относительно предыдущей позиции;
- цвет, толщина 4 px, радиус и длина дуг сохранены;
- правые RAM/DISK-линии не изменялись.

Проверка:

- `py_compile frontend/jarvis_hud.py frontend/jarvis_ui.py` пройден;
- Jarvis перезапущен;
- VITS продолжает обучение: `STEP 27/62`, `GLOBAL_STEP 275`, последний лог
  обновлён в 04:32:01.

## Очередь 0029 — перезапуск VITS с последнего чекпоинта

Дата: 2026-10-27

Изменения:

- зависший процесс обучения остановлен по запросу пользователя;
- запуск выполнен через `--continue_path` для той же папки эксперимента;
- Trainer подтвердил `Restoring from best_model_496.pth` и
  `Model restored from step 496`;
- новый видимый PowerShell-процесс обучения запущен.

Текущее ограничение:

- после восстановления записано `EPOCH: 0/120`, но первый новый loss/step ещё
  не появился; процесс жив, однако вход в первый шаг снова требует отдельной
  диагностики, если прогресс не возобновится.

## Очередь 0030 — очистка длинного WAV и успешное продолжение VITS

Дата: 2026-10-27

Изменения:

- `ext_1027_02.wav` проверен: первые `7,25 сек` совпадают с канонической короткой
  версией, хвост около `2,9 сек` удалён из обучающей копии;
- исходный длинный файл сохранён без изменений в
  `backups/vits-ext-1027-02-before-trim-20261027/`;
- метаданные оставлены без изменений: фраза уже соответствует одному короткому
  аудиосегменту;
- обучение перезапущено через `--continue_path` из `best_model_496.pth`.

Проверка:

- новый WAV: `7,25 сек`, `22050 Hz`, mono;
- Trainer подтвердил восстановление с шага `496`;
- после инициализации появился новый прогресс: `STEP 3/62`, `GLOBAL_STEP 500`;
- средний шаг около `25,4 сек`, процесс обучения активен.

-
## Очередь 0031 — подготовка GPT-SoVITS Russian

Дата: 2026-10-27

Изменения:

- репозиторий GPT-SoVITS Russian клонирован отдельно в
  `external/GPT-SoVITS-russian`;
- текущий VITS не останавливался;
- установщик GPT-SoVITS проверен: Windows-вариант предлагает только `CU126`,
  `CU128` или `CPU`, а `ROCM` доступен только в Linux-скрипте.

Диагностика GPU:

- видеокарта: AMD Radeon RX 7600;
- текущее окружение Jarvis: `torch 2.4.0+cpu`, CUDA недоступна;
- ROCm в Windows/WSL ещё не установлен;
- системный AMD-драйвер уже новее найденного ROCm-пакета, поэтому откат/замена
  драйвера без подтверждённой совместимости не выполнялись.

Ограничение:

- для GPT-SoVITS на этой AMD-карте нужен экспериментальный Linux/WSL ROCm-путь;
  штатный Windows-инсталлятор GPT-SoVITS GPU использует только CUDA.
-
## Очередь 0032 — проверка WSL2 для GPT-SoVITS

Дата: 2026-10-27

Проверка:

- Ubuntu 24.04.3 в WSL2 доступна;
- `/dev/dxg` присутствует, то есть WSL видит Windows GPU-слой;
- DNS WSL исправлен на `1.1.1.1` и `8.8.8.8`;
- DNS-имя `archive.ubuntu.com` разрешается.

Ограничение:

- исходящие HTTPS-соединения из WSL к Ubuntu/ROCm-репозиториям не проходят;
- установка `python3-pip`, `python3-venv`, `ffmpeg` и ROCm PyTorch пока не
  завершена;
- Windows Jarvis и текущий VITS не затронуты.

- HAPP VPN на Windows используется для WSL: запущено пользовательское TCP-реле
  `tools/wsl_happ_proxy_relay.py` на `0.0.0.0:18080`, которое направляет трафик
  WSL в локальный HAPP HTTP-прокси `127.0.0.1:10809`;
- через реле WSL уже получил доступ к Ubuntu-репозиториям; установка базовых
  пакетов `python3-pip`, `python3-venv`, `git`, `ffmpeg` повторно запущена с
  отключённым HTTP pipeline и таймаутом 30 секунд;
- на момент записи установка ещё выполняется; ROCm и GPT-SoVITS пока не
  запускались, чтобы не подменить результат CPU-режимом.

## Очередь 0033 — офлайн-загрузка базовых зависимостей GPT-SoVITS

Дата: 2026-10-27

Готово:

- пользовательские файлы перенесены из `Downloads` в
  `external/offline_bootstrap`;
- `pip` установлен в WSL через `get-pip.py`;
- отдельное окружение создано в `external/gpt_sovits_wsl_env`;
- Linux FFmpeg распакован в `external/ffmpeg-linux`, проверен запуском
  `ffmpeg 7.0.2-static`;
- пакет `amdgpu-install` 7.2 для Ubuntu 24.04 установлен локально.

Ограничение:

- полный ROCm-инсталлятор потребовал бы около `6,9 ГБ` загрузки и `28,4 ГБ`
  места; он отменён как избыточный;
- минимальный `rocm-hip-runtime` оценён примерно в `704 МБ`, но часть крупных
  архивов также не прошла через HAPP-реле; ROCm GPU пока не подтверждён.

## Очередь 0034 — восстановление зависшего VITS

Дата: 2026-10-27

Причина:

- один и тот же run `20261027g` одновременно обслуживали два запуска Python:
  `backend\\jarvis_env` и системный Python 3.11;
- процессы делили лог и состояние Trainer, из-за чего лог остановился на
  `GLOBAL_STEP 650`, а CPU-процесс остался живым без новых записей;
- последний сохранённый checkpoint — `best_model_496.pth`.

Исправление:

- старые процессы VITS остановлены;
- оставлен один видимый запуск через `backend\\jarvis_env`;
- обучение восстановлено из `best_model_496.pth`;
- новый лог подтвердил `Model restored from step 496`, затем `STEP 3/62`,
  `GLOBAL_STEP 500`; шаги снова записываются.

## Очередь 0035 — завершение ROCm-распаковки и проверка GPU

Дата: 2026-10-27

Готово:

- автономный ROCm runfile распакован и установлен в `/opt/rocm-7.2.0`;
- post-install завершён с кодом `0`, размер установленного дерева около `28 ГБ`;
- добавлены недостающие небольшие системные пакеты `libnuma1`, `libpci3`,
  `pciutils`;
- `/dev/dxg` в WSL присутствует.

Ограничение:

- `rocminfo` завершился сообщением `hsa_init Failed, possibly no supported GPU
  devices`; ROCm-пользовательский слой установлен, но RX 7600 пока не
  определяется как доступный поддерживаемый GPU в WSL;
- PyTorch ROCm не запускался, чтобы не объявлять GPU-ускорение без фактической
  проверки устройства.

Текущее VITS:

- обучение продолжает писать лог: `GLOBAL_STEP 575`, `STEP 16/62`, последнее
  обновление `19:02:30`;
- последний сохранённый checkpoint остаётся `best_model_496.pth`.

## Очередь 0036 — GPT-SoVITS на Windows

Дата: 2026-10-27

Сделано:

- создано Windows-окружение `external/gpt_sovits_win_env`;
- развёрнут GPT-SoVITS в `external/GPT-SoVITS-russian`;
- скачаны и распакованы предобученные веса в
  `external/GPT-SoVITS-russian/GPT_SoVITS/pretrained_models`;
- локально подключены BGE-m3, WavLM и ffmpeg;
- датасет подготовлен: 378 исходных фраз, 373 корректные фразы прошли
  текстовую/акустическую проверку;
- WebUI запущен на `http://127.0.0.1:9874/`;
- исправлены Windows-пути, русская фонемизация, пустые токенизированные
  интервалы и несовместимость размера русской таблицы символов с pretrained
  embedding.

Текущее состояние:

- SoVITS fine-tuning реально запущен на Windows CPU в эксперименте
  `logs/jarvis_gpt_cpu`;
- последний подтверждённый прогресс — `24/373`, epoch 1;
- GPT-этап ещё не запускался: он будет выполняться последовательно после
  SoVITS, чтобы два тяжёлых CPU-процесса не блокировали друг друга;
- текущий запуск нельзя считать GPU-обучением: RX 7600 не определяется как
  поддерживаемое ROCm-устройство в WSL;
- существующее VITS-обучение не останавливалось и продолжает работать отдельно.

Откат/диагностика:

- текущий запуск можно остановить через WebUI/терминал без удаления весов и
  логов;
- основной `docs/HANDOFF.md` в этой очереди не редактировался;
- список изменённых файлов и зависимости остаются в рабочем дереве до
  отдельной проверки и коммита.

## Очередь 0037 — контроль двух обучений

Дата: 2026-10-27

- VITS жив: процесс PID 57200 пишет `trainer_0_log.txt`; последний подтверждённый
  статус — `GLOBAL_STEP 700`, `STEP 17/62`, обновление в 20:04:23.
- GPT-SoVITS/SoVITS жив: основной процесс PID 66792; текущий прогресс —
  `42/373`, epoch 1.
- Новые checkpoint-файлы VITS с момента предыдущего сохранения не появились;
  это нормально внутри текущей эпохи, но состояние подтверждается свежим логом.

Контроль на 2026-10-27 20:41:

- VITS продвинулся до `GLOBAL_STEP 750`, `STEP 5/62`; лог обновился в 20:35:50.
- GPT-SoVITS продвинулся до epoch 2, примерно `234/373` на момент проверки;
  в выводе уже появился переход из epoch 1 и новые значения loss.

Повторный контроль на 2026-10-27 21:22:

- VITS жив: `GLOBAL_STEP 825`, `STEP 18/62`; лог обновлён в 21:22:36.
- VITS сохранил новые файлы `best_model_807.pth` и `best_model.pth`.
- GPT-SoVITS-процесс жив; TensorBoard event-файл обновлялся до 21:19:02.
- Последняя пара checkpoint GPT-SoVITS: `G_233333333333.pth` и
  `D_233333333333.pth`, сохранена в 20:50:50–20:50:51.

Повторный контроль на 2026-10-27 22:07:

- VITS жив: `GLOBAL_STEP 875`, `STEP 6/62`; лог обновлён в 21:58:28.
- VITS сохранил свежую пару `best_model_869.pth` и `best_model.pth` в 21:53:55–21:53:56.
- GPT-SoVITS жив: event-лог обновлён в 22:07:44.
- GPT-SoVITS сохранил обновлённые `G_233333333333.pth` и
  `D_233333333333.pth` в 21:38:55–21:38:57.

Повторный контроль на 2026-10-27 22:54:

- VITS жив: `GLOBAL_STEP 950`, `STEP 19/62`; лог обновлён в 22:50:33.
- VITS сохранил `best_model_931.pth` и обновлённый `best_model.pth` в 22:37:59–22:38:01.
- GPT-SoVITS жив: event-лог обновлён в 22:54:27.
- Последние GPT-SoVITS G/D checkpoint-файлы обновлены в 22:30:50–22:30:53.

Контроль утром 2026-10-28:

- GPT-SoVITS завершил заданные 8 эпох: в `train.log` есть `saving ckpt
  jarvis_gpt_cpu_e8:Success` в 23:16:55; последняя итерация — 2900.
- Финальные доступные GPT-SoVITS G/D-файлы сохранены в 23:16:50–23:16:52.
- VITS новых записей не сделал: последняя отметка остаётся `GLOBAL_STEP 950`,
  `STEP 19/62` в 22:50:33. Процесс-обёртка присутствует, но рабочая память
  дочернего Python минимальна; требуется отдельная диагностика/перезапуск с
  последнего checkpoint, если продолжение VITS ещё нужно.

Очередь 0038 — продолжение GPT-SoVITS, 2026-10-28:

- создан `TEMP/tmp_s2_finetune_e16.json` с общим лимитом 16 эпох;
- запущен отдельный Windows-процесс продолжения;
- checkpoint 8-й эпохи успешно подхвачен: лог подтверждает загрузку D и G;
- обучение продолжится с 9-й эпохи, готовые файлы 8-й эпохи не перезаписываются.

Контроль перезапуска VITS на 2026-10-28 01:20:

- старый остановившийся процесс завершён;
- VITS успешно восстановлен из `best_model_931.pth` (`Model restored from step 931`);
- загрузка датасета прошла: 367 экземпляров, отброшено 0;
- начат новый цикл обучения `EPOCH 0/120` с восстановленным состоянием;
- GPT-SoVITS при этом не останавливался.

Контроль на 2026-10-28 01:35:

- VITS после перезапуска снова пишет лог: `GLOBAL_STEP 950`, `STEP 18/62`,
  последнее обновление 01:32:35; процесс использует около 2.3 ГБ RAM.
- GPT-SoVITS продолжает дообучение: 11-я эпоха — `99%`, последняя итерация
  `4100`; лог обновлён в 01:34:43.
- Последний сохранённый GPT-SoVITS checkpoint пока за 10-ю эпоху; следующий
  сохранится после завершения текущего цикла по настройке `save_every_epoch=2`.

Контроль на 2026-10-28 02:22:

- VITS продвинулся до `GLOBAL_STEP 1025`, `STEP 31/62`; лог обновлён в 02:17:18.
- VITS сохранил `best_model_994.pth` и обновлённый `best_model.pth` в 01:59:59–02:00:01.
- GPT-SoVITS завершил 12-ю и 13-ю эпохи, checkpoint 12-й сохранён успешно в
  01:57:23–01:57:27.
- GPT-SoVITS сейчас на 14-й эпохе, `14%`, последняя итерация `4900`;
  лог обновлён в 02:21:25.

Контроль на 2026-10-28 03:04:

- VITS жив: `GLOBAL_STEP 1100`, `STEP 44/62`; лог обновлён в 03:03:52.
- GPT-SoVITS завершил 14-ю и 15-ю эпохи; checkpoint 14-й сохранён успешно в
  02:40:12–02:40:15.
- GPT-SoVITS начал финальную 16-ю эпоху, текущий прогресс `1%`, итерация `5600`.

Контроль на 2026-10-28 04:06:

- GPT-SoVITS завершил дообучение до 16-й эпохи; в логе подтверждено
  `saving ckpt jarvis_gpt_cpu_e16:Success` в 03:26:31.
- Финальные G/D checkpoint-файлы 16-й эпохи обновлены в 03:26:22–03:26:25.
- VITS продолжает работать: `GLOBAL_STEP 1225`, `STEP 45/62`; лог обновлён
  в 04:06:10.
- VITS сохранил `best_model_1180.pth` в 03:46:08.

Очередь 0039 — тест GPT-SoVITS, 2026-10-28:

- финальный SoVITS-вес для инференса: `SoVITS_weights_v2Pro/jarvis_gpt_cpu_e16_s5968.pth`;
- локальный тестовый API запущен на `127.0.0.1:9881` в CPU-режиме;
- выбран эталон `base_0012.wav` (8.3 секунды), текст эталона сохранён в датасете;
- исправлены совместимости API с русским WavLM/G2P и PyTorch attention;
- пробная фраза успешно сгенерирована: `test_output_jarvis_gpt_sovits.wav`,
  WAV 32 kHz, mono, 1.5 секунды;
- основной Jarvis пока не переключён на GPT-SoVITS;
- GPT-компонент в этом тесте — штатный предобученный `s1v3.ckpt`, так как
  отдельное S1/GPT-текстовое дообучение ещё не выполнялось.

Повторный тест:

- вторая фраза успешно обработана через тот же API без ошибки;
- результат `test_output_jarvis_gpt_sovits_2.wav`: 32 kHz, mono, 0.9 секунды,
  HTTP `200 OK`.

Диагностика тишины и выбор тестового checkpoint:

- финальные e16/e14/e12/e10 WAV-файлы имеют `RMS 0.0`, то есть содержат полную
  тишину;
- базовый v2Pro на том же API даёт ненулевой сигнал (`RMS 0.0108`);
- e2 и e8 дают ненулевой сигнал (`RMS около 0.0396`), поэтому e8 выбран как
  последний рабочий checkpoint для тестирования;
- тестовый API переключён на
  `SoVITS_weights_v2Pro/jarvis_gpt_cpu_e8_s2984.pth`;
- e10–e16 признаны непригодными для подключения без исправления режима
  обучения/проверки loss.

Тест полной связки S1+S2:

- использованы `GPT_weights_v2Pro/jarvis_s1_cpu-e20.ckpt` и рабочий
  `SoVITS_weights_v2Pro/jarvis_gpt_cpu_e8_s2984.pth`;
- API вернул HTTP `200 OK`, WAV не нулевой: 32 kHz, mono, 0.74 секунды,
  RMS `0.016893`;
- результат сохранён как `test_output_s1e20_s2e8.wav`;
- в Jarvis связка пока не включалась, тестовый API работает отдельно.

Очередь 0041 — исправленный повторный S2-запуск, 2026-10-28:

- первый запуск retry был остановлен автоматически на старом `logs/jarvis_gpt_cpu`
  и не выполнял новое обучение; checkpoint старого эксперимента сохранён;
- для чистого запуска создан отдельный датасет-контур
  `logs/jarvis_s2_retry_data` и отдельная папка checkpoint `logs/jarvis_s2_retry`;
- новый S2 действительно стартовал с базовых `s2Gv2Pro.pth`/`s2Dv2Pro.pth`,
  подтверждение в логе: `start training from epoch 1`;
- конфигурация: 12 эпох, batch 2, learning rate `2e-5`, warmup 1 эпоха;
- на момент записи начат первый проход `0/187` batch, старые результаты не
  перезаписываются.

Итог прослушивания теста:

- e8 не является готовым голосом: вместо разборчивой русской речи слышны
  неясные/шумоподобные звуки;
- причина архитектурная: дообучен только SoVITS S2, а GPT/S1-текстовая модель
  осталась штатной `s1v3.ckpt` и не обучалась на Jarvis-датасете;
- e8 оставлен только как диагностический checkpoint, подключать его к Jarvis
  нельзя.

Очередь 0040 — отдельное GPT/S1-обучение, 2026-10-28:

- создана конфигурация `TEMP/s1_jarvis_cpu.yaml` на 20 эпох;
- обучение запущено в отдельной папке `logs/jarvis_s1_cpu` на Windows CPU;
- базовый `s1v3.ckpt` загружен успешно после совместимого resize русского
  phoneme embedding;
- датасет S1 подготовлен: 373 фонемных записи, после фильтрации осталось 359
  валидных примеров;
- исправлен Windows CPU DataLoader: `prefetch_factor` отключается при
  `num_workers=0`;
- текущий S1-процесс активен (PID 59832), TensorBoard event-файл обновляется;
- существующее VITS-обучение не останавливалось.

Контроль двух обучений на 2026-10-28 04:32:

- S1 процесс активен (PID 59832), TensorBoard обновляется; последний шаг
  `349`, epoch `0`, loss `263.76981`, top-3 accuracy `0.39437`.
- S1 дошёл почти до конца первой эпохи; checkpoint первой эпохи ещё не появился.
- VITS активен (PID 61872): `GLOBAL_STEP 1275`, `STEP 33/62`, лог обновлён
  в 04:28:10.
- Последний checkpoint VITS остаётся `best_model_1180.pth`; процесс продолжает
  писать шаги после него.

Повторная проверка на 2026-10-28 04:52:

- S1 активно продвинулся до epoch `9`; последний TensorBoard step `3349`,
  loss `96.47287`, top-3 accuracy `0.77778`.
- S1 сохраняет checkpoint после каждой эпохи; уже есть файлы до
  `epoch=8-step=801.ckpt`.
- VITS жив: `GLOBAL_STEP 1300`, `STEP 58/62`; последняя запись лога — 04:41:37.
- Нового VITS checkpoint после `best_model_1180.pth` пока нет, но шаги продолжают
  обновляться.

Контроль на 2026-10-28 13:25:

- GPT/S1 завершил плановые 20 эпох: финальный экспортированный вес
  `GPT_weights_v2Pro/jarvis_s1_cpu-e20.ckpt` сохранён в 05:16:29;
- S1-процесс завершён штатно, последний TensorBoard epoch — 19 (нумерация с 0),
  top-3 accuracy на последних шагах — `1.0`;
- VITS продолжает работать: `GLOBAL_STEP 2525`, `STEP 43/62`, лог обновлён
  в 13:24:23;
- VITS сохранил свежий checkpoint `best_model_2420.pth` в 12:39:32.

Контроль на 2026-10-28 01:17:

- GPT-SoVITS продолжает дообучение: завершена 10-я эпоха, текущая 11-я —
  `19%`, последняя итерация `3800`.
- Checkpoint 10-й эпохи сохранён успешно в 01:12:43–01:12:51.
- VITS новых записей после `GLOBAL_STEP 950` в 22:50:33 не сделал и фактически
  не продвигается; его следует отдельно перезапустить с `best_model_931.pth`.

Очередь 0042 — интеграция временного Silero-профиля Kesha, 2026-10-28:

- проведён аудит `C:\projects\jarvis-kesha`; подтверждено, что `model_small`
  является Vosk ASR, а TTS исходника использует стандартный Silero `ru_v3`
  с диктором `aidar`, без персональных Kesha-весов;
- checkpoint Silero перенесён из локального Torch Hub кэша в
  `backend/voice_engine/models/silero/ru_v3.pt`; SHA-256:
  `BF2BCAB8E814EDB17569503B23BD74E8CC8F584B0D2F7C7E08E2720CC48DC08C`;
- добавлен расширяемый реестр `backend/voice_engine/voice_models.py` с профилями
  `jarvis` (default, обученная модель в разработке, текущий XTTS fallback) и
  `kesha` (Silero ru_v3/aidar, временный профиль);
- `backend/voice_engine/tts.py` теперь маршрутизирует выбранный профиль,
  кэширует Silero в памяти и сохраняет прежний XTTS-путь для Jarvis;
- backend получил `/voice/models`, `/voice/model` и сведения о профиле в
  `/voice/status`;
- в существующий блок “ЗВУК И ВИЗУАЛ” добавлены выбор голосовой модели,
  фактический движок и статус; выбранный ID хранится через QSettings;
- проверено: `torch.package.PackageImporter`, русский Silero-инференс,
  WAV-синтез, вызов воспроизведения, FastAPI endpoints и `py_compile`;
- исходный `C:\projects\jarvis-kesha` не изменялся и не удалялся. До отдельного
  подтверждения пользователя удаление запрещено;
- непроверено в этой очереди: ручное визуальное открытие Qt-настроек после
  полного перезапуска desktop-приложения и прослушивание результата человеком.

Очередь 0043 — перенос голосовых параметров в раздел «ГОЛОС AI», 2026-10-28:

- микрофон, выбор голосовой модели, статус фактического движка и диагностика
  запуска перенесены из общей карточки в отдельную страницу «ГОЛОС AI»;
- общая страница теперь содержит только визуальные параметры окна/HUD;
- сохранены существующие QSettings, backend API и порядок разделов навигации;
- после исправления несовместимого `addStretch()` для `QFormLayout` frontend
  успешно запустился повторно; проверка подтверждена живым Qt-процессом;
- предупреждение `cv2` остаётся необязательным для перечисления камер, Qt
  продолжает работать с software/GLES fallback.

Очередь 0044 — ускорение голосового ответа и защита от input overflow,
2026-10-28:

- диагностировано live-состояние: `phi3:latest` отвечал через Ollama, но
  runtime завершался с recoverable `input overflow`, а Kesha синтезировала на
  CPU в исходных 48 kHz;
- callback PortAudio теперь не превращает transient overflow в ошибку UI,
  поток захвата использует меньший блок и high-latency буфер;
- Kesha по умолчанию синтезирует в 24 kHz (настройка
  `JARVIS_KESHA_SAMPLE_RATE` сохраняет варианты 8/24/48 kHz);
- WAV-фраза ожидания запускается параллельно с запросом к LLM, голосовая ветка
  ограничивает ответ 280 символами, Ollama получает `num_predict=64`;
- выбор модели при перезапуске теперь восстанавливается из QSettings до
  синхронизации с backend, чтобы default backend не затирал выбор Kesha;
- `22/22` backend-теста и `py_compile` прошли; текущий backend перезапущен,
  обучение VITS/GPT-SoVITS не останавливалось;
- реальное время полного end-to-end голосового ответа после этой правки ещё
  требует ручной фразы в запущенном приложении.

Замер CPU Silero на короткой русской фразе:

- 48 kHz: около 11 секунд;
- 24 kHz: около 6.4 секунды;
- 8 kHz: около 1.2 секунды, но с заметно худшим качеством.

Поэтому default оставлен 24 kHz как компромисс качества и задержки.

Очередь 0045 — перезапуск GPT-SoVITS S2, 2026-10-28:

- предыдущий запуск `jarvis_s2_retry` дошёл до эпохи 2 и остановился на
  сохранении `G_374.pth`; ожидаемый файл отсутствует, поэтому продолжить ровно
  с этого checkpoint нельзя;
- запущен новый чистый S2-проход на том же подготовленном наборе данных
  (`367` экземпляров, `12` эпох, batch `2`, learning rate `2e-5`) с базовыми
  весами `v2Pro/s2Gv2Pro.pth` и `v2Pro/s2Dv2Pro.pth`;
- команда запущена из `external/GPT-SoVITS-russian` в видимой терминальной
  сессии, окружение `gpt_sovits_win_env`, устройство — CPU;
- на момент записи журнал подтверждает загрузку обоих pretrained-весов и
  фактический старт `Train Epoch: 1 [0%]`; процессы S2 живы, VITS продолжает
  работать отдельно;
- текущие ограничения: CUDA недоступна в GPT-SoVITS окружении, поэтому этот
  запуск будет медленным; первый checkpoint ожидается после завершения эпохи 2.

Уточнение очереди 0045 — проверка и исправление, 2026-10-28:

- фактический traceback подтверждён: `WinError 3` возник в `shutil.move` при
  переносе временного checkpoint в каталог `logs_s2_retry_data/logs_s2_v2Pro`,
  которого не было;
- параллельно загрузчик аудио выдавал `WinError 2`, потому что в Windows PATH
  отсутствовал `ffmpeg.exe`; найденный ранее `tar.xz` оказался Linux-сборкой и
  не подходит для Windows;
- установлен Windows FFmpeg Shared 9.0.2 в пользовательское окружение, путь к
  нему добавлен только в процесс обучения; каталог checkpoint создан заранее;
- после исправления S2 перезапущен повторно с базовых v2Pro-весов. Процесс жив,
  ошибок сохранения в новом запуске пока нет; ожидается первый лог шага и затем
  checkpoint эпохи 2.

Проверка очереди 0046, 2026-10-28:

- VITS активен: эпоха `36/120`, шаг `11/62`, `GLOBAL_STEP: 3175`; процесс и
  журнал продолжают обновляться;
- GPT-SoVITS S2 активен после исправлений: новый запуск дошёл до
  `Train Epoch: 1 [0%]`, оба базовых веса загружены, процесс не завершился;
- checkpoint S2 пока не появился — это ожидаемо до завершения второй эпохи;
- одновременно работают оба обучения, ни одно из них не останавливалось.

Проверка очереди 0047, 2026-10-28:

- VITS продолжает работу: свежая запись `STEP: 36/62`, `GLOBAL_STEP: 3200`,
  журнал обновлён в `18:32:59`;
- S2 продолжает работу: `Train Epoch: 1 [53%]`, журнал обновлён в `18:38:58`;
- оба процесса запущены в отдельных Codex-терминалах, поэтому их live-вывод не
  отображался в пользовательском PowerShell;
- открыт отдельный видимый PowerShell-монитор, который каждые 5 секунд выводит
  хвост обоих журналов и не управляет самими процессами обучения.

Очередь 0048 — согласованная очистка исторических архивов, 2026-10-28:

- в корзину Windows отправлены все корневые архивы `.zip` и `.rar`;
- удалён архив `external/GPT-SoVITS-russian/pretrained_models.zip`, так как
  распакованные предобученные модели уже находятся внутри GPT-SoVITS;
- удалены дубликаты Linux FFmpeg `external/ffmpeg-linux/` и `tools/`;
- удалена пустая папка `vosk-model-small-ru-0.22/`; рабочая Vosk-модель
  приложения находится в `backend/voice_engine/model_small/`;
- файлы отправлены в корзину, а не удалены безвозвратно; девять папок,
  запрошенных для отдельного анализа, не изменялись;
- после очистки оба обучения всё ещё живы: VITS и GPT-SoVITS S2.

Очередь 0049 — capability-слой устройств, планы и фоновые backup-задачи,
2026-10-28:

- добавлен ленивый `backend/services/device_capabilities.py`: реальные статусы
  камеры/OpenCV, обработки изображений, MediaPipe-жестов, принтера, CAD,
  аудио/видеопотока, CUDA и LAN-discovery;
- backend получил `/devices/capabilities` и on-demand
  `/devices/camera/snapshot`; тяжёлые устройства не запускаются при обычном
  чате;
- frontend получил раздел настроек «УСТРОЙСТВА» со статусами возможностей,
  обновлением диагностики и кнопкой снимка камеры;
- Planner теперь формирует стабильные `step-*`, ожидаемый результат и
  verification metadata; Executor публикует выбор инструмента и локальную
  проверку результата без дополнительного LLM-запроса;
- этапы плана отображаются в статусе приложения через runtime events;
- исправлен lifecycle Agent: `BackupAgent.on_start()` теперь действительно
  запускает scheduler; backup выполняется через `asyncio.to_thread`, добавлен
  статус `/backups/status` и ручной `/backups/run`;
- раздел «ДАННЫЕ» показывает состояние фоновых копий;
- добавлены optional-зависимости `pywin32`, `build123d`, `zeroconf`; они не
  устанавливались автоматически, пока соответствующие адаптеры не нужны;
- `22/22` backend-тестов и `py_compile` прошли; backend/frontend перезапущены;
- из `JarvisBeta Setup` в рабочий sound-каталог сохранены четыре уникальные
  WAV-фразы, затем восемь согласованных исторических папок отправлены в
  корзину; `Jarvis Sound Pack от Jarvis Desktop` сохранён;
- VITS и GPT-SoVITS S2 во время всех изменений оставались активными.

Очередь 0051 — удаление устаревших voice-скриптов и проверка обучения, 2026-10-28:

- в корзину Windows отправлены 12 подтверждённо неиспользуемых файлов:
  старый `jarvis_fast`, watchdog, force-audio/test-скрипты, legacy_main/config,
  три старых voice-цикла, voice_listener, record_command и clone_voice_test;
- `backend/voice_engine/wakeword_engine.py` сохранён как экспериментальный
  резерв OpenWakeWord + Silero VAD;
- VITS активен, журнал обновлён в 22:58:39 и показывает `EPOCH: 44/120`;
- GPT-SoVITS S2 не является зависшим: последний запуск штатно сохранил
  `jarvis_s2_retry_e12` и веса `G_2244.pth`/`D_2244.pth` в 22:13:45;
- S2-тренировочный процесс после checkpoint 12 завершён, отдельный GPT-SoVITS
  API-инференс продолжает работать на порту 9881;
- текущие процессы обучения не останавливались и не перезапускались.

Очередь 0052 — восстановление после перезагрузки, 2026-10-29:

- после перезагрузки активных процессов обучения не было;
- VITS восстановлен командой `train_vits.py --continue_path` из
  `jarvis_voice_external_20261027g/run-October-27-2026_02+21AM-a457d87`;
- Trainer подтвердил загрузку `best_model_2668.pth` и
  `Model restored from step 2668`; текущий процесс работает на CPU;
- предыдущий лог успел дойти до `GLOBAL_STEP: 3750`, но последний физически
  сохранённый checkpoint — `best_model_2668.pth`, поэтому восстановление
  выполнено именно из него;
- GPT-SoVITS S2 не перезапускался: конфигурация уже завершена на `12/12`,
  последний сохранённый checkpoint — `G_2244.pth`/`D_2244.pth` и
  `jarvis_s2_retry_e12`;
- запущены только необходимые процессы VITS; повторных копий не создано.

Очередь 0050 — изолированная установка device-зависимостей, 2026-10-28:

- MediaPipe 1.2.0, pywin32 312, build123d 0.13.0 и zeroconf 0.151.5 установлены
  в `backend/device_env`;
- основное `backend/jarvis_env` сохранено совместимым с voice runtime: NumPy
  1.26.4, OpenCV 4.10.0.84, `pip check` без ошибок;
- причина разделения: свежие MediaPipe/CAD требуют NumPy 2.x, а текущий
  голосовой стек Jarvis и gruut требуют NumPy 1.x;
- capability-диагностика проверяет изолированное окружение без тяжёлого импорта,
  поэтому `/devices/capabilities` отвечает примерно за 0.75 с;
- фактическая проверка: камера, vision, жесты, принтер, CAD, streaming и
  LAN-discovery доступны; CUDA остаётся CPU-only;
- `22/22` backend-тестов прошли; приложение перезапущено;
- VITS и GPT-SoVITS S2 не останавливались: VITS — живой процесс, S2 — эпоха 5,
  28% на момент проверки.

Очередь 0053 — тест GPT-SoVITS S2, 2026-10-29:

- после перезагрузки поднят inference API GPT-SoVITS на `127.0.0.1:9881`; S2-
  обучение не перезапускалось, так как ранее завершено на `12/12`;
- обнаружены два повреждённых/невалидных экспортированных файла в
  `SoVITS_weights_v2Pro` размером 134 989 990 байт; для теста использован
  валидный `G_2244.pth` из `logs/jarvis_s2_retry_data/logs_s2_v2Pro` и
  восстановлен совместимый экспорт `jarvis_s2_retry_e12_s2244_fixed.pth`;
- валидная GPT-модель — `GPT_weights_v2Pro/jarvis_s1_cpu-e16.ckpt`;
- `/set_model` вернул `200 Success`, реальный синтез русской фразы вернул WAV
  `external/GPT-SoVITS-russian/test_outputs/gpt_sovits_s2_test_e12.wav`:
  mono, 32 kHz, 27 520 frames, 0.86 s, 55 084 bytes;
- повторный синтез без перезагрузки моделей также успешен: `200`, 65 324 bytes,
  2.84 s; API оставлен запущенным для дальнейшей проверки;
- VITS не затронут и продолжает работать из последнего сохранённого checkpoint.

Очередь 0054 — аудит чекпойнтов и исходников S2, 2026-10-29:

- валидный GPT-чекпойнт: `GPT_weights_v2Pro/jarvis_s1_cpu-e16.ckpt`; обычный
  `torch.load` прочитал `weight/config/info`, 295 тензоров;
- валидный сырой S2-чекпойнт: `logs/jarvis_s2_retry_data/logs_s2_v2Pro/G_2244.pth`;
  это тренировочный контейнер с 781 ключом, `iteration=12`, а не файл для
  прямой передачи в inference API;
- runtime-экспорт S2 прочитан штатным `load_sovits_new`: версия `v2Pro`, 678
  весов, `12epoch_2244iteration`; `jarvis_s2_retry_e12_s2244_fixed.pth`
  также корректно читается этим загрузчиком;
- файлы с именами `jarvis_gpt_cpu_*.pth` и исходный `jarvis_s2_retry_*.pth`
  в каталоге `SoVITS_weights_v2Pro` фактически имеют формат SoVITS-экспорта,
  несмотря на имена; использовать их как GPT-чекпойнты нельзя;
- источник S2 содержит 373 строки расшифровки и 378 WAV-файлов, включая
  подготовленные `5-wav32k`, фонемы/токены и HuBERT/SV-эмбеддинги;
- структурная проверка прошла, но качество синтеза не прошло: короткий WAV и
  шум указывают на проблему качества/совместимости обучения, а не на частоту
  32 кГц. Веса не объявлены готовыми для Jarvis.

Очередь 0055 — точечный тест фразы `ext_1027_1_022`, 2026-10-29:

- использован текст `подождем еще пять минут.` из `2-name2text.txt`;
- модельная пара: `jarvis_s1_cpu-e16.ckpt` + экспорт S2 `e12_s2244_fixed`;
- `/set_model` вернул `200 Success`, синтез вернул `200`;
- результат сохранён в `external/GPT-SoVITS-russian/test_outputs/phrase_ext_1027_1_022.wav`;
  WAV mono, 32 кГц, длительность 0.74 с; тест подтверждает генерацию файла,
  но не исправляет ранее выявленное качество шума.

Очередь 0056 — диагностика причины короткого/шумового вывода, 2026-10-29:

- найден завершённый GPT S1 checkpoint `jarvis_s1_cpu-e20.ckpt` (20 эпох),
  поэтому e16 больше не используется как последний GPT-вариант;
- тест правильной пары e20 + S2 e12 также вернул короткий WAV (0.90 с), то
  есть замена e16 на e20 проблему полностью не устранила;
- контроль с предобученным S2 показал, что API и reference-инференс работают,
  а проблема локализуется в пользовательской GPT/S2 связке или качестве её
  обучения;
- в датасете обнаружены 373 строки и 378 WAV, средняя длительность 2.79 с,
  но есть длинные записи до 9.23 с и пять вариантов одной фразы
  `джарвис с возвращением сэр`; перед новым обучением необходима чистка и
  единый reference 2–4 с с точной расшифровкой;
- пользовательские e12/e20 веса не объявлены production-ready; текущий
  inference API после диагностики возвращён на пользовательскую пару.

Очередь 0057 — чистое S2-обучение и автоматические тесты, 2026-10-29:

- создана отдельная копия `logs/jarvis_s2_clean_data`; исходный датасет не
  изменён и сохранён для отката;
- удалены из новой копии записи смешанного `ext_vyacheslav`, фразы длиннее
  6 секунд и повторы сверх трёх вариантов одной расшифровки; осталось 172
  согласованных примера с полным набором WAV/HuBERT/SV-файлов;
- создана конфигурация `logs/jarvis_s2_clean/config.json`: 30 эпох,
  batch_size 2, сохранение каждые 2 эпохи, выход в
  `SoVITS_weights_v2Pro_clean`;
- S2 запущен отдельным видимым процессом на CPU, стартовал с эпохи 1 и уже
  записал первый лог обучения; VITS PID 19868 не затронут;
- добавлен `tools/watch_gpt_sovits_s2.ps1`: при каждом новом экспортированном
  checkpoint он автоматически подменит S2 в локальном API и сохранит тест
  фразы `подождем еще пять минут.`; до появления новых весов API работает на
  предобученном fallback S2.

Очередь 0058 — проверка текущего обучения, 2026-10-29:

- VITS активен: процесс PID 19868 отвечает, журнал дошёл до `EPOCH: 5/120`;
- новый S2 активен: процессы обучения отвечают, датасет 172/172 загружен,
  предобученные G/D-веса совпали по ключам;
- S2 находится на `Epoch 1 [0%]`, первый шаг записан с loss-показателями;
  checkpoint ещё не сохранён, поэтому автоматические аудиотесты пока пусты;
- отсутствие нового checkpoint на этом этапе не является зависанием: S2 считает
  первый CPU-шаг, который существенно тяжелее подготовки данных;
- оба обучения не останавливались и не перезапускались.

Очередь 0059 — исправление сохранения S2, 2026-10-29:

- первый запуск очищенного S2 фактически прошёл 2 эпохи и достиг 86/86 шагов;
- процесс завершился на сохранении `G_172.pth`, потому что отсутствовал каталог
  `logs/jarvis_s2_clean_data/logs_s2_v2Pro` для raw checkpoint;
- каталог создан, S2 перезапущен на той же конфигурации с чистого старта;
- VITS продолжает отдельное обучение и не затронут;
- watcher тестов оставлен активным и будет проверять новые экспортированные
  веса после появления checkpoint.

Очередь 0060 — проверка и возобновление S2, 2026-10-29:

- VITS активен и журнал дошёл до `EPOCH: 15/120`;
- S2 дошёл до `Epoch 18`, сохранил raw `G_1548.pth`, но экспортные веса не
  создавались из-за отсутствовавшего каталога `SoVITS_weights_v2Pro_clean`;
- каталог создан; S2 возобновлён автоматически с `G_1548.pth` и последнего
  доступного `D_1376.pth`, стартовал с эпохи 19/30;
- после появления новых экспортов watcher выполнит аудиотест; старые raw
  checkpoint’ы и исходный датасет сохранены.

Очередь 0061 — контроль места на диске, 2026-10-29:

- на диске C: осталось 25.64 ГБ из 930 ГБ;
- очищенный S2 занимает 13.73 ГБ, старый `jarvis_s2_retry_data` — 9.80 ГБ,
  VITS run — 1.87 ГБ;
- основной рост дают пары raw `G_*.pth`/`D_*.pth` примерно по 1.7 ГБ на
  checkpoint-эпоху; это ожидаемое поведение текущей конфигурации;
- S2 процесс активен и загружает продолжение с `G_1548.pth`; VITS-процесс на
  момент проверки не обнаружен, последний журнал — `EPOCH: 15/120`;
- ничего не удалялось: старые checkpoints оставлены для явного согласования.

Очередь 0062 — актуальная проверка обучения, 2026-10-29:

- S2 продолжает обучение и находится на `Epoch 30 [7%]` из 30;
- экспортные веса успешно созданы до `jarvis_s2_clean_e28_s2408.pth`, ошибки
  сохранения после создания каталогов не повторились;
- raw checkpoints сохранены до `G_2408/D_2408`, но свободное место снизилось
  до 15.13 ГБ;
- VITS-процесс сейчас не обнаружен, последний его журнал остаётся на
  `EPOCH: 15/120`;
- inference API и watcher тестов сейчас не активны, поэтому автоматические
  WAV-тесты для e20–e28 не созданы; веса обучения не объявляются проверенными
  на слух до отдельного inference-теста.

Очередь 0063 — завершение S2 и критическое заполнение диска, 2026-10-29:

- чистое S2 завершило заданные `30/30` эпох; последний raw checkpoint
  `G_2580.pth`/`D_2580.pth` сохранён успешно;
- экспорт `jarvis_s2_clean_e30_s2580.pth` создан успешно;
- активных процессов S2 и VITS при проверке нет; VITS остался на последнем
  подтверждённом `EPOCH: 15/120`;
- свободное место C: снизилось примерно до 20 МБ, диск практически заполнен;
- причина — накопленные raw checkpoints очищенного S2, старые raw checkpoints
  предыдущего обучения и VITS-артефакты; автоматически ничего не удалялось.

Очередь 0064 — inference-тест финального S2, 2026-10-29:

- локальный GPT-SoVITS API временно запущен на CPU на порту `9881`;
- `jarvis_s2_clean_e30_s2580.pth` загрузился через `/set_model` без ошибки;
- успешно сгенерированы два WAV: контрольная фраза и новая фраза;
- `control.wav`: 32 кГц, mono, 1.18 с; `new.wav`: 32 кГц, mono, 1.90 с;
- оба файла имеют ненулевой аудиосигнал и не пустые, но субъективная разборчивость
  голоса ещё не подтверждена прослушиванием пользователем;
- тестовые файлы сохранены в `external/GPT-SoVITS-russian/test_outputs/s2_clean_manual`;
- тестовый API после проверки остановлен; обучение не запускается заново.

Очередь 0065 — отказ от VITS и разделение voice-пайплайна, 2026-10-29:

- VITS-скрипт, конфигурация, кэш фонем, четыре набора данных и три каталога
  результатов убраны из рабочего проекта; точные копии перемещены в
  `C:\Users\Данил\AppData\Local\Temp\Jarvis-VITS-removed-20261029` для
  обратимого восстановления;
- GPT‑SoVITS и общий каталог WAV не затронуты;
- добавлен `backend/services/response_router.py`: известные команды идут в
  `commands.yaml`/`computer_control`, остальные фразы — в разговорный контур;
- исправлен ложный fuzzy-match: фраза «как сегодня настроение» больше не
  превращается в команду погоды из-за общего слова «сегодня»;
- добавлен ленивый адаптер `backend/voice_engine/stt.py` для локального
  faster-whisper; текущий непрерывный runtime сохраняет Vosk как быстрый
  fallback, пока не выбран и не проверен локальный whisper-чекпойнт;
- добавлены workflow и инструкция для приёма новых коротких WAV-фраз GPT‑SoVITS;
- compileall пройден; pytest в системном Python не запущен, так как pytest
  там не установлен.

Очередь 0066 — проверка новых онлайн-аудиоматериалов, 2026-10-29:

- четыре MP3 с `media.aihere.ru/fish-tts` сохранены в
  `backend/voice_engine/dataset/external_jarvis_staging/online_baranov_candidates`;
- добавлен локальный файл `В начале сотворил Бог небо и землю Земл.mp3`;
- онлайн-файлы имеют 44.1 кГц mono и длительность 9.06–13.79 с;
- локальный библейский файл имеет 44.1 кГц mono и длительность 77.48 с;
- Fish-TTS-файлы помечены как кандидаты на проверку, но не добавлены в обучение:
  ссылка ведёт на синтетические Fish-TTS samples, а не на подтверждённую
  оригинальную запись голоса Баранова;
- новые материалы не смешивались с чистым GPT‑SoVITS датасетом и обучение не
  запускалось.

Очередь 0067 — расширенный набор и голосовой конвейер, 2026-10-29:

- подготовлены 28 новых сегментов из 7 пользовательских аудиофайлов; создано
  `2-name2text-0.txt`, 28 BERT-признаков, 28 HuBERT-признаков и semantic-файл;
- Fish-TTS-материалы сохранены отдельным кандидатом и не выдаются за
  подтверждённые записи Баранова;
- собран отдельный GPT‑SoVITS S2-набор на 200 примеров: 172 чистых + 28 новых;
  чистый набор и его экспортный вес не перезаписаны;
- расширенное обучение запущено от `G_2580/D_2580` с целевым пределом 60 эпох,
  журнал: `external/GPT-SoVITS-russian/logs/jarvis_s2_augmented_data/train.log`;
- добавлены `backend/voice_engine/vad.py` и `tts_queue.py`; runtime при наличии
  локальных пакетов использует Silero VAD, затем faster-whisper, а Ollama
  передаёт завершённые предложения в последовательную очередь TTS;
- оставлен Vosk fallback при ошибке инициализации VAD/Whisper;
- `compileall` пройден. Встроенный pytest не запущен: в `backend/jarvis_env`
  пакет pytest отсутствует. Живой микрофон и воспроизведение требуют отдельного
  ручного теста в запущенном приложении.

Очередь 0068 — исправление состава расширенного обучения, 2026-10-29:

- первый запуск после сборки остановлен безопасно: загрузчик показал
  `phoneme_data_len=200`, но `wav_data_len=172`, потому что для новых фраз не
  были рассчитаны `7-sv_cn` embeddings;
- embeddings рассчитаны штатным `2-get-sv.py` на локальном
  `pretrained_eres2netv2w24s4ep4.ckpt`;
- расширенный набор пересобран, контроль загрузчика подтвердил
  `phoneme_data_len=200`, `wav_data_len=200`, `skipped_phone=0`,
  `skipped_dur=0`;
- обучение повторно запущено от `G_2580/D_2580`, начата эпоха 31 из 60.

Очередь 0069 — контроль текущего обучения, 2026-10-29:

- процесс GPT‑SoVITS активен; главный процесс и дочерние DataLoader-процессы
  обнаружены;
- обучение дошло до эпохи 32, прогресс последнего журнала — `Epoch 32 [37%]`,
  шаг 3200;
- текущий loss не нулевой и обновляется: `loss_disc 3.6245`, `loss_gen 3.8441`,
  `loss_mel 18.7467`;
- последний завершённый сохранённый checkpoint пока `G_2580/D_2580`; новый
  checkpoint появится после завершения 32-й эпохи, так как сохранение задано
  раз в две эпохи;
- обучение не зависло и не прерывалось.

Очередь 0070 — возобновление после остановки, 2026-10-30:

- проверка показала, что прошлый процесс завершился после эпохи 51 из-за
  отсутствующего каталога экспортных весов; raw `G_5100/D_5100` сохранились;
- создан каталог `external/GPT-SoVITS-russian/SoVITS_weights_v2Pro_augmented`;
- обучение повторно запущено и подтвердило загрузку `G_5100/D_5100`,
  `phoneme_data_len=200`, `wav_data_len=200`, `skipped_phone=0`,
  `skipped_dur=0`;
- продолжение начато с эпохи 51 из 60. Теперь экспортные веса должны сохраняться
  в отдельный каталог без прежней ошибки пути.

Очередь 0071 — завершение расширенного обучения, 2026-10-30:

- обучение завершило все 60/60 эпох;
- последний raw checkpoint: `G_6120.pth` и `D_6120.pth`;
- экспортный вес сохранён успешно: `jarvis_s2_augmented_e60_s6120.pth`;
- сохранение экспортов на эпохах 52, 54, 56, 58 и 60 прошло без ошибки;
- активного процесса обучения больше нет.

Очередь 0072 — тест финального checkpoint, 2026-10-30:

- локальный GPT‑SoVITS API запущен на CPU на порту 9882;
- `jarvis_s2_augmented_e60_s6120.pth` загрузился через `/set_model` успешно;
- сгенерированы две новые фразы и контрольная фраза `подождем еще пять минут.`;
- все WAV: mono, 32 кГц, 16-bit, ненулевой сигнал;
- augmented контрольная: 1.54 с, peak 14887, RMS 2571.2;
- augmented новая фраза: 1.86 с, peak 22756, RMS 2798.0;
- для сравнения clean e30: 1.54 с, peak 16638, RMS 2584.0;
- API после теста остановлен. Разборчивость на слух требует прослушивания пользователем;
  числовая проверка подтверждает только корректную генерацию, а не качество речи.

Очередь 0073 — проверка разборчивости, 2026-10-30:

- faster-whisper прогнал созданные WAV и не восстановил целевые фразы;
- augmented и clean e30 дают короткие ошибочные расшифровки вместо
  `подождем еще пять минут.`;
- это подтверждает, что проблема не в пустом WAV, частоте 32 кГц или громкости:
  сигнал ненулевой, но фонемно-текстовое соответствие плохое;
- дальнейшее увеличение эпох без очистки разметки не считается исправлением;
  Fish-TTS-кандидаты и ошибочные автоматические транскрипции требуют отдельной
  верификации перед новым обучением.

Очередь 0074 — очистка разметки и перезапуск S1, 2026-10-30:

- старый набор `logs/jarvis_gpt_cpu` и старые чекпойнты не изменялись;
- создан отдельный набор `logs/jarvis_s1_clean_data`;
- оставлено 306 base-примеров с согласованными semantic/phoneme строками;
- исключены 28 неполных строк с переменной энергией и 39 внешних `ext_*`
  сегментов, пока они не подтверждены вручную;
- исправлены две найденные текстовые опечатки, фонемы пересобраны заново;
- установлен `razdel`, `ruphon`, `ruaccent` в `backend/jarvis_env` для русской
  фонемизации; системный Python и исходные данные не менялись;
- S1 запущен с базового `s1v3.ckpt` в отдельный каталог
  `logs/jarvis_s1_clean`, конфигурация — `logs/jarvis_s1_clean_config.yaml`;
- на момент записи процесс реально выполняется на CPU: Epoch 0, 43/292,
  датасет после встроенного фильтра — 292 строки; старые S1/S2 сохранены.

Очередь 0075 — безопасная остановка перед перезагрузкой, 2026-10-30:

- S1 был остановлен вручную через `Ctrl+C` по запросу пользователя;
- остановка прошла штатно, процесс сообщил `Detected KeyboardInterrupt`;
- текущая незавершённая эпоха 2 остановлена на шаге 207/292;
- последний полный сохранённый checkpoint: `logs/jarvis_s1_clean/ckpt/epoch=1-step=144.ckpt`;
- после перезагрузки запуск той же конфигурации автоматически продолжит с
  `epoch=1-step=144.ckpt`; частичный прогресс эпохи 2 не выдаётся за сохранённый.

Очередь 0076 — возобновление S1, 2026-10-30:

- обучение перезапущено с `epoch=1-step=144.ckpt`;
- процесс подтвердил восстановление состояния и начал `Epoch 2`;
- текущий датасет после фильтра — 292 примера;
- режим CPU, старые результаты сохранены.

Очередь 0077 — контроль текущего S1, 2026-10-30:

- процесс активен, не завис;
- выполнено 11 эпох, текущая `Epoch 11`, примерно `118/292` шагов;
- последний полный checkpoint: `logs/jarvis_s1_clean/ckpt/epoch=10-step=792.ckpt`;
- экспортные веса уже появились до `jarvis_s1_clean-e11.ckpt`;
- текущий loss на шагах заметно ниже ранних значений, обучение продолжает работать на CPU.

Очередь 0078 — запуск второй фазы S2, 2026-10-31:

- S1 завершён: 40/40 эпох, экспорт `GPT_weights_v2Pro_clean_s1/jarvis_s1_clean-e40.ckpt`;
- подготовлен отдельный S2-набор из тех же 306 записей;
- проверены признаки: `4-cnhubert`, `5-wav32k`, `7-sv_cn` — по 306 файлов,
  пропусков нет;
- S2 запущен с базовых `s2Gv2Pro/s2Dv2Pro`, без старого шумного checkpoint;
- старт подтверждён, Epoch 1, первый batch выполнен;
- GPU недоступна, CPU-скорость около 63 секунд на batch, поэтому фаза будет
  значительно дольше S1; процесс оставлен активным.

Очередь 0079 — исправление запуска S2, 2026-10-31:

- первая попытка S2 прошла первую эпоху, но остановилась на сохранении из-за
  отсутствующей папки `logs/jarvis_s2_clean_s1_data/logs_s2_v2Pro`;
- каталог создан, но checkpoint первой попытки не сохранился;
- S2 перезапущен с базовых весов, загрузка датасета и всех 306 признаков
  прошла успешно;
- текущий процесс снова начал Epoch 1, старые augmented/clean S2 результаты
  не изменялись.

Очередь 0080 — продолжение S2 после сохранения, 2026-10-31:

- S2 дошёл до 12 эпох, сохранены `G_1836.pth` и `D_1836.pth`;
- экспорт облегчённых весов не создавался из-за отсутствующей папки
  `SoVITS_weights_v2Pro_clean_s1`, затем папка создана;
- текущий запуск автоматически загрузил `G_1836/D_1836` и продолжил с
  `Epoch 13`, а не с нуля;
- процесс активен, обучение продолжено на CPU.

Очередь 0081 — освобождение места, 2026-10-31:

- проверен активный S2: текущая ветка `logs/jarvis_s2_clean_s1_data` не удалялась,
  процесс продолжает обучение;
- удалены старые каталоги `jarvis_gpt_cpu`, `jarvis_s1_cpu`, старые
  `jarvis_s2_clean/augmented/retry` и их датасеты;
- удалены старые экспортные каталоги `GPT_weights_v2Pro`,
  `SoVITS_weights_v2Pro`, `SoVITS_weights_v2Pro_clean` и
  `SoVITS_weights_v2Pro_augmented`;
- удалены пять временных корневых `.pth`, оставшихся после неудачных сохранений;
- сохранены текущие S1/S2: `jarvis_s1_clean`, `GPT_weights_v2Pro_clean_s1`,
  `jarvis_s2_clean_s1_data` и его `G_*/D_*`;
- размер `external/GPT-SoVITS-russian` уменьшен примерно со 140 ГБ до 44.5 ГБ;
- свободное место диска C: после очистки — около 135 ГБ.

Очередь 0082 — безопасная остановка перед выключением ПК, 2026-10-31:

- обучение GPT-SoVITS S2 не запущено;
- сохранена последняя полная пара чекпойнтов `G_5202.pth` и `D_5202.pth`;
- точка продолжения: эпоха 34 из 60, шаг 5202;
- экспорт `jarvis_s2_clean_s1_e34_s5202.pth` также сохранён;
- завтра продолжать из `external/GPT-SoVITS-russian/logs/jarvis_s2_clean_s1_data/logs_s2_v2Pro`.

Очередь 0083 — возобновление S2 после перезагрузки, 2026-11-01:

- запуск подтверждён с конфигурацией `jarvis_s2_clean_s1_config.json`;
- загружены `G_5202.pth` и `D_5202.pth` (iteration 34);
- обучение продолжено с `Epoch 35`, не с нуля;
- текущий процесс активен в окне терминала Codex.

Очередь 0084 — завершение S2, 2026-11-01:

- обучение дошло до 60-й эпохи из 60;
- последний полный checkpoint: `G_9180.pth` и `D_9180.pth`;
- экспортированы веса `SoVITS_weights_v2Pro_clean_s1/jarvis_s2_clean_s1_e60_s9180.pth`;
- активного процесса `s2_train.py` больше нет, обучение завершено штатно.

Очередь 0085 — тест финальных S2-весов, 2026-11-02:

- локальный GPT-SoVITS API временно запущен на CPU с финальными S1/S2 весами;
- `/` вернул HTTP 200, WAV создан:
  `test_outputs/s2_final_e60/final_phrase_wait_five_minutes.wav`;
- параметры WAV: mono, 32 кГц, 16-bit, 0.98 с, peak 12879, RMS 2190.6;
- время генерации на CPU — около 17 секунд;
- автоматическая проверка разборчивости через faster-whisper не выполнена:
  в используемом окружении распознаватель недоступен;
- API после теста остановлен.

Очередь 0086 — расширенный тест S2, 2026-11-02:

- финальные веса повторно загрузились и успешно обработали 4 фразы;
- все запросы вернули HTTP 200, WAV mono/32 кГц/16-bit, сигнал ненулевой;
- проверены короткая фраза, команда, разговорная фраза и длинный статус;
- результаты сохранены в `external/GPT-SoVITS-russian/test_outputs/s2_final_e60`;
- API после проверки остановлен.

Очередь 0087 — фильтрация датасета и повторное обучение, 2026-11-03:

- проведён технический аудит 306 WAV: все исходные файлы mono/32 кГц/16-bit,
  без пустых и слишком тихих записей;
- faster-whisper tiny выявил 48 записей с явным несовпадением речи и эталонного
  текста (score < 0.30); создан новый набор из 258 записей;
- при подготовке S1 GPT-SoVITS дополнительно автоматически исключил 12 записей
  с аномальным соотношением фонем к длительности, фактически осталось 245;
- создано: `logs/jarvis_s1_whisper_filtered_data` и
  `logs/jarvis_s2_whisper_filtered_data`, признаки S2 полные, пропусков нет;
- удалены заменённые старые S1/S2 чекпойнты, старый 306-фразовый S2-набор и
  старые экспортные веса; освобождено примерно 85 ГБ;
- новое S1-обучение запущено с базового `s1v3.ckpt`, Epoch 0, 245 batch.

Очередь 0088 — возобновление после выключения ПК, 2026-11-03:

- процесс был остановлен выключением ПК после checkpoint `epoch=0-step=61.ckpt`;
- запуск повторён с тем же конфигом;
- checkpoint успешно восстановлен, обучение продолжено с `Epoch 1`;
- текущий процесс активен, CPU, 245 batch на эпоху.

Очередь 0089 — повторный запуск после остановки, 2026-11-03:

- после предыдущего запуска сохранён checkpoint `epoch=1-step=122.ckpt`;
- активного процесса при проверке не было;
- обучение перезапущено и checkpoint восстановлен;
- текущая позиция подтверждена: `Epoch 2`, 245 batch.

Очередь 0090 — контроль и возобновление S1, 2026-11-04:

- обучение остановилось после checkpoint `epoch=2-step=183.ckpt`;
- checkpoint найден и успешно восстановлен;
- запуск продолжен с `Epoch 3`, 245 batch;
- процесс активен на CPU.

Очередь 0091 — контроль и возобновление S1, 2026-11-04:

- найден последний checkpoint `epoch=3-step=244.ckpt`;
- активного процесса при проверке не было;
- checkpoint успешно восстановлен;
- обучение продолжено с `Epoch 4`, 245 batch, CPU.

Очередь 0092 — устранение причины остановок S1, 2026-11-04:

- по traceback установлено: после завершения эпохи обучение падало в `my_save`
  из-за отсутствующей папки `GPT_weights_v2Pro_whisper_filtered`;
- raw checkpoint при этом сохранялся, поэтому прогресс не терялся;
- папка создана корректно;
- последний checkpoint `epoch=4-step=305.ckpt` восстановлен;
- обучение продолжено с `Epoch 5`, экспортные веса теперь сохраняются в
  существующую папку.

Очередь 0093 — устойчивый запуск S1, 2026-11-04:

- проверка показала сохранённые checkpoint и экспорт до `Epoch 16`;
- привязанного к интерактивному терминалу процесса больше не было;
- S1 перезапущен отдельным фоновым процессом с автоматическим восстановлением
  последнего checkpoint;
- процесс активен, вывод перенаправлен в
  `logs/jarvis_s1_whisper_filtered/training_detached.log`.

Очередь 0094 — остановка по просьбе пользователя, 2026-11-04:

- фоновый S1-процесс остановлен перед выключением ПК;
- активных `s1_train.py`/`s2_train.py` процессов не осталось;
- сохранены экспортные веса до `jarvis_s1_whisper_filtered-e16.ckpt`;
- продолжать позже с последнего checkpoint автоматически.

Очередь 0095 — запуск S1 после паузы, 2026-11-05:

- последняя сохранённая экспортная точка — `jarvis_s1_whisper_filtered-e16.ckpt`;
- первый фоновый запуск завершился ошибкой кодировки Windows `cp1251` при выводе
  IPA-фонем (`UnicodeEncodeError`);
- повторный запуск выполнен с `PYTHONIOENCODING=utf-8`;
- checkpoint `epoch=15-step=976.ckpt` восстановлен, сейчас идёт `Epoch 16`;
- процесс запущен отдельно от окна Codex и пишет журнал в
  `logs/jarvis_s1_whisper_filtered/training_detached.log`.

Очередь 0096 — завершение фильтрованного S1, 2026-11-05:

- обучение достигло `40/40` эпох;
- последний raw checkpoint: `epoch=39-step=2440.ckpt`;
- экспортированы веса `GPT_weights_v2Pro_whisper_filtered/jarvis_s1_whisper_filtered-e40.ckpt`;
- в логе подтверждено: `Trainer.fit stopped: max_epochs=40 reached`;
- активного S1/S2 процесса нет, обучение завершено штатно.

Очередь 0097 — запуск нового S2 после S1, 2026-11-05:

- создан конфиг `logs/jarvis_s2_whisper_filtered_config.json` на 60 эпох;
- подготовлены каталоги checkpoint и экспортных весов;
- после исправления пути к Python-окружению S2 успешно запущен в фоне;
- датасет принят: `phoneme_data_len=258`, `wav_data_len=258`, пропусков нет;
- базовые `s2Gv2Pro.pth` и `s2Dv2Pro.pth` загружены;
- текущая позиция подтверждена: `Epoch 1`, 129 batch.

Очередь 0098 — контроль S2, 2026-11-05:

- процесс активен, два Python-процесса S2 работают штатно;
- последний экспорт: `jarvis_s2_whisper_filtered_e54_s6966.pth`;
- последние raw checkpoint: `G_6966.pth` и `D_6966.pth`;
- журнал показывает продолжение следующей эпохи, примерно `28/129` batch;
- сохранение checkpoint и экспортов проходит без ошибок.

Очередь 0099 — контроль S2, 2026-11-05:

- S2-процессы активны;
- последний экспорт: `jarvis_s2_whisper_filtered_e58_s7482.pth`;
- raw checkpoint: `G_7482.pth` и `D_7482.pth`;
- текущая следующая эпоха идёт, около `34/129` batch;
- ошибок сохранения и экспорта не обнаружено.

Очередь 0100 — завершение фильтрованного S2, 2026-11-06:

- обучение завершено: `60/60` эпох;
- последний raw checkpoint: `G_7740.pth` и `D_7740.pth`;
- итоговый экспорт сохранён: `SoVITS_weights_v2Pro_whisper_filtered/jarvis_s2_whisper_filtered_e60_s7740.pth`;
- лог подтверждает `saving ckpt ... Success` и `training done`;
- активного S2-процесса нет.

Очередь 0101 — тест финальных S1/S2, 2026-11-06:

- локальный API запущен с `jarvis_s1_whisper_filtered-e40.ckpt` и
  `jarvis_s2_whisper_filtered_e60_s7740.pth`;
- выполнены 4 реальных запроса, все вернули HTTP 200;
- WAV корректные: mono, 32 кГц, 16-bit, ненулевой сигнал;
- результаты сохранены в `test_outputs/s2_filtered_e60`;
- первый запрос занял 20.8 с на прогреве CPU, последующие 1.6–2.1 с;
- API после теста остановлен; разборчивость требует прослушивания пользователем.

Очередь 0102 — аудит причины неразборчивого S1/S2, 2026-11-06:

- обнаружена ошибка загрузчика `GPT_SoVITS/AR/data/dataset.py`: `6-name2semantic.tsv` является headerless-манифестом, но `pandas.read_csv` использовал `header=0`, из-за чего первая запись `base_0000.wav` выпадала из S1;
- загрузчик исправлен на `header=None` с явными колонками `item_name` и `semantic`;
- проверка после исправления: `semantic_data_len=258`, `phoneme_data_len=258`, фактический S1 dataset length `246`;
- скрытым фильтром по phoneme/sec исключаются 12 записей: `base_0012.wav`, `base_0037.wav`, `base_0134.wav`, `base_0135.wav`, `base_0136.wav`, `base_0137.wav`, `base_0138.wav`, `base_0283.wav`, `base_0284.wav`, `base_0285.wav`, `base_0287.wav`, `base_0288.wav`;
- обучение после исправления ещё не перезапускалось; текущие e40/e60 считаются диагностическими и не подтверждают разборчивый голос.

Очередь 0103 — перезапуск S1 на исправленном манифесте, 2026-11-10:

- создан отдельный конфиг `logs/jarvis_s1_whisper_aligned_config.yaml`;
- выходы нового запуска направлены в `logs/jarvis_s1_whisper_aligned` и `GPT_weights_v2Pro_whisper_aligned`, старые результаты сохранены;
- обучение запущено в отдельном окне CMD через `external/gpt_sovits_win_env` с UTF-8;
- процесс подтверждён: Python работает, рабочий процесс использует около 2.8 ГБ RAM и активно считает CPU;
- после запуска создан TensorBoard event-файл; итоговую эпоху и разборчивость пока не подтверждать.

Очередь 0104 — завершение исправленного S1, 2026-11-11:

- обучение завершено штатно: `40/40` эпох;
- активных процессов обучения нет;
- итоговый raw checkpoint: `logs/jarvis_s1_whisper_aligned/ckpt/epoch=39-step=2440.ckpt`;
- итоговый экспорт: `GPT_weights_v2Pro_whisper_aligned/jarvis_s1_whisper_aligned-e40.ckpt`;
- до проверки реальным синтезом разборчивость новой модели не подтверждать.

Очередь 0105 — тест нового S1 с текущим S2, 2026-11-11:

- API запущен с `jarvis_s1_whisper_aligned-e40.ckpt` и текущим `jarvis_s2_whisper_filtered_e60_s7740.pth`;
- выполнены 4 реальных запроса, все HTTP 200;
- WAV сформированы корректно: mono, 32 кГц, 16-bit, ненулевой сигнал;
- результаты сохранены в `test_outputs/s1_aligned_s2_e60`;
- длительность ответов: 0.98–1.26 с, повторные запросы около 1.4–1.5 с;
- API после проверки остановлен; субъективная разборчивость требует прослушивания пользователем;
- S2 пока не переобучался: сначала проверяется, устранил ли новый S1 проблему.

Очередь 0106 — запуск S2 и очистка старых резервов, 2026-11-11:

- старые каталоги `jarvis_s1_whisper_filtered`, `GPT_weights_v2Pro_whisper_filtered`, `logs_s2_v2Pro`, `SoVITS_weights_v2Pro_whisper_filtered` и старые тестовые WAV удалены по запросу пользователя;
- новый S2 запускается в `logs/jarvis_s2_whisper_aligned_data/logs_s2_v2Pro` с экспортом в `SoVITS_weights_v2Pro_whisper_aligned`;
- после исправления рабочей директории запуск подтверждён: первая эпоха, `0/129` batch;
- загрузка данных подтверждена: `phoneme_data_len=258`, `wav_data_len=258`, `skipped_phone=0`, `skipped_dur=0`;
- старые S2-результаты не сохраняются как резерв.

Очередь 0107 — контроль S2, 2026-11-11:

- процесс активен, текущая позиция: `Epoch 1`, примерно `27/129 batch`;
- первый лог обучения записан, loss рассчитан, зависания не обнаружено;
- на CPU один batch занимает примерно 4–5 секунд после прогрева;
- checkpoint ещё не создан, так как сохранение настроено раз в 2 эпохи.

Очередь 0108 — контроль S2 после остановки, 2026-11-12:

- активного процесса S2 нет;
- в каталоге `logs/jarvis_s2_whisper_aligned_data/logs_s2_v2Pro` нет `G_*.pth`/`D_*.pth` и экспортированных весов нет;
- последний TensorBoard event-файл обновлялся 2026-11-11 в 13:46;
- журналов traceback/error в каталоге нет;
- из-за `save_every_epoch=2` первая эпоха не оставила checkpoint, поэтому продолжить S2 с сохранённой точки нельзя; нужен повторный запуск с сохранением после каждой эпохи.

Очередь 0109 — повторный запуск S2, 2026-11-12:

- конфигурация изменена на `save_every_epoch=1`;
- S2 перезапущен с pretrained `s2Gv2Pro.pth`/`s2Dv2Pro.pth` с нулевой точки;
- загрузка датасета подтверждена: 258 записей, `skipped_phone=0`, `skipped_dur=0`;
- активная сессия обучения: `21811`; текущая первая эпоха запущена;
- новый checkpoint ожидается уже после первой эпохи.

Очередь 0110 — повторная проверка S2, 2026-11-12:

- активного процесса S2 нет;
- `G_*.pth`/`D_*.pth` и экспортированных SoVITS-весов снова нет;
- последний TensorBoard event обновлялся 2026-11-12 в 01:58;
- по event-файлу записано только несколько точек loss, до сохранения первой эпохи обучение не дошло;
- причина остановки в сохранённых логах не зафиксирована; свободно около 183 ГБ на диске C, нехватка места не является причиной.

Очередь 0111 — detached-перезапуск S2, 2026-11-12:

- S2 запущен отдельным процессом через `run_jarvis_s2_whisper_aligned_detached.cmd`;
- вывод направляется в `logs/jarvis_s2_whisper_aligned_training.log`, чтобы процесс не зависел от текущего терминала;
- процессы подтверждены активными: launcher PID 7560 и рабочий Python PID 28732;
- рабочий процесс отвечает и использует CPU/RAM; сохранение checkpoint после каждой эпохи включено.

Очередь 0112 — исправление падения S2 на сохранении и перезапуск, 2026-11-13:

- предыдущий запуск дошёл до `129/129` первой эпохи, но упал при сохранении из-за жёстко зашитого старого пути `logs/jarvis_s2_whisper_filtered_data\\logs_s2_v2Pro`;
- `s2_train.py` исправлен: checkpoint, resume и logger используют `hps.s2_ckpt_dir` из текущего конфига;
- новый detached-запуск подтверждён: launcher PID 17840, рабочий Python PID 39828;
- рабочий каталог checkpoint: `logs/jarvis_s2_whisper_aligned_data/logs_s2_v2Pro`;
- лог запуска: `logs/jarvis_s2_whisper_aligned_training.log`;
- сохранение после каждой эпохи оставлено включённым.

Очередь 0113 — контроль исправленного S2, 2026-11-13:

- активный процесс подтверждён: PID 39828;
- S2 успешно прошёл минимум `40` эпох и продолжает `Epoch 41`;
- checkpoint сохраняются корректно: `G_5160.pth`/`D_5160.pth` и экспорт `SoVITS_weights_v2Pro_whisper_aligned/jarvis_s2_whisper_aligned_e40_s5160.pth`;
- текущий прогресс в логе: примерно `55/129` batch эпохи 41;
- падения на сохранении больше нет.

Очередь 0114 — подготовка публичного релиза, 2026-11-13:

- подтверждено: полноценное окно и прозрачный HUD — два режима одного `JarvisUI`, удалять ни один нельзя;
- добавлен `frontend/launch_jarvis.py`, который запускает backend, ждёт `/health`, затем открывает GUI;
- добавлен пользовательский lock-файл для защиты от второго экземпляра;
- добавлен необязательный автозапуск через HKCU Run и переключатель в разделе «Общие»;
- добавлены `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `ROADMAP.md`, аудит релиза и рецепт PyInstaller/Inno Setup;
- активное S2-обучение не останавливалось и не изменялось;
- локальные environments, модели, датасеты, логи и checkpoints исключены из публичной поставки;
- запуск launcher подтверждён: backend слушает `127.0.0.1:8000`, окно Jarvis доступно;
- backend-тесты: `22/22`, warnings о закрытии sqlite-соединений остаются техническим долгом;
- EXE-сборка запущена; установленный EXE и Inno Setup пока не объявлять проверенными до завершения сборочного прогона.

Очередь 0115 — завершение публичного релизного прогона, 2026-11-13:

- Inno Setup собрал `dist/Jarvis-Assistant-Setup.exe` без ошибки; размер файла около 450 МБ.
- Тихая установка в отдельную временную директорию завершилась с кодом 0; созданы ярлыки в меню Пуск и на рабочем столе.
- Тихое удаление тестовой установки завершилось с кодом 0; каталог опустел.
- backend-тесты повторно прошли `22/22`, компиляция ключевых модулей прошла, `/health` отвечает HTTP 200.
- S2 подтверждён активными процессами PID 17840 и 39828; обучение не останавливалось и не изменялось.
- GitHub Push Protection обнаружила секрет в историческом legacy-файле `JARVIS-main/.../toolbench_tool_instruction.json`; файл удалён из локальной Git-истории, секретный скан чистый.
- коммит публичной подготовки опубликован в `https://github.com/dev2v07/Jarvis-assist.git` в ветку `master`.
- визуальный PNG-снимок приложения через computer-use не сохранён: окно Jarvis в момент проверки было свёрнуто; макеты вместо реального снимка не добавлялись.

Очередь 0116 — ссылка Tandem и финальная проверка сборки, 2026-11-14:

- ссылка `© Разработано Tandem Marketing 2026` перенесена непосредственно под карточку профиля в обычном окне;
- ссылка открывает `https://tandemarketing.ru` через Qt rich-text link и добавлена в `widget_chrome_widgets`, поэтому скрывается вместе с остальным chrome при переходе в прозрачный HUD;
- исходный `jarvis_ui.py` и launcher с Qt DLL runtime-hook успешно скомпилированы; GUI-сборка и Inno Setup пересобраны;
- свежий `dist/Jarvis-Assistant-Setup.exe` создан успешно, размер около 88 МБ;
- запуск свежего frozen GUI фактически проверен и не пройден: окно `Unhandled exception in script`, `DLL load failed while importing QtCore: Не найдена указанная процедура`;
- поэтому запуск установленного GUI с голосом/аудио и получение реальных PNG-скриншотов остаются незакрытыми; backend source health ранее подтверждён отдельно;
- процессы S2/GPT-SoVITS не останавливались и не изменялись.

Очередь 0117 — исправление запуска frozen GUI, 2026-11-14:

- установлена причина Qt-ошибки: PyInstaller подхватывал ICU DLL из Poppler, где экспорт был суффиксирован (`ucnv_open_78`), а `Qt6Core.dll` требовал обычный `ucnv_open`;
- в `packaging/build_windows.ps1` добавлено исключение конфликтующих `icuuc.dll`/`icudt78.dll` только из GUI-поставки; backend-поставка не изменена;
- runtime-hook предварительно загружает bundled `Qt6Core.dll`, а launcher сохраняет DLL handles и пишет traceback в `%LOCALAPPDATA%\\Jarvis Assist\\launcher_crash.log`;
- для frozen HUD исправлен путь ресурсов на `_MEIPASS/frontend/assets`; добавлена защита от пустого `BG6.png`;
- новый frozen GUI реально запущен и показал окно `Jarvis Assist`; Qt/ICU и `ZeroDivisionError` больше не воспроизводятся;
- исходный backend health снова подтверждён HTTP 200, Python-компиляция ключевых файлов прошла;
- `dist/Jarvis-Assistant-Setup.exe` пересобран после исправлений; Inno Setup завершился успешно;
- S2/GPT-SoVITS не затрагивались.

Очередь 0118 — атрибуция и язык установщика, 2026-11-14:

- текст ссылки Tandem в приложении теперь имеет непрозрачный белый цвет `#ffffff`;
- ссылка установщика перенесена с WelcomePage на основное окно WizardForm, поэтому отображается в нижней области на всех страницах мастера;
- добавлена подчёркнутая кликабельная ссылка на `https://tandemarketing.ru`;
- добавлен `Russian.isl`, установщик собирается с русским интерфейсом; фактическое окно тестового установщика имеет заголовок `Установка — Jarvis Assistant, версия 0.1.0`;
- GUI и Inno Setup пересобраны, frozen GUI снова запущен успешно;
- screenshot capture окна установщика через computer-use снова завершился таймаутом, поэтому визуальное наличие ссылки подтверждено кодом Inno Setup, но не отдельным PNG.

Очередь 0119 — переход из прозрачного HUD в настройки, 2026-11-14:

- исправлен `ensure_full_ui`: при открытии страницы из HUD теперь вызывается общий переход `toggle_widget_mode()`, а не только ручное скрытие/показ отдельных элементов;
- восстановлены обычная непрозрачность окна, стили, chrome и hitbox-слои перед показом настроек;
- действия `SET`, `FUNCTION`, `PROV` и `MOD` из HUD теперь принудительно выключают режим виджета перед переходом к соответствующему разделу;
- это остаётся одним окном Jarvis: отдельное окно настроек не создаётся;
- свежая GUI-сборка и установщик пересобраны; запуск frozen GUI подтверждён по окну `Jarvis Assist`, но координатная проверка клика в HUD не завершилась из-за таймаута захвата окна;
- S2/GPT-SoVITS не останавливались и не изменялись.

Очередь 0120 — явная иконка ярлыков установщика, 2026-11-14:

- причина неправильной иконки ярлыка: `SetupIconFile` задавал только значок самого установщика, а ярлыки ссылались лишь на встроенный ресурс EXE;
- в Inno Setup добавлена отдельная поставка `frontend/assets/jarvis.ico` в корень `{app}`;
- оба ярлыка получили явные параметры `IconFilename: "{app}\\jarvis.ico"` и `IconIndex: 0`;
- установщик пересобран успешно: `dist/Jarvis-Assistant-Setup.exe`;
- для обновления уже существующего ярлыка потребуется переустановить приложение или пересоздать ярлык; старый ярлык Windows может продолжать показывать кэшированную иконку;
- S2/GPT-SoVITS не останавливались и не изменялись.

Очередь 0121 — Fish Audio как голосовой профиль, 2026-11-14:

- в реестр голосов добавлен профиль `fish_jarvis` — `Fish Audio — Джарвис`;
- backend использует `FISH_AUDIO_API_KEY`, `FISH_AUDIO_REFERENCE_ID` и `FISH_AUDIO_MODEL` из окружения; секреты в код и Git не записываются;
- по умолчанию используется `s2.1-pro-free`, ответ запрашивается в WAV и воспроизводится существующей очередью TTS;
- XTTS Jarvis и локальный Silero Kesha сохранены без изменений;
- UI «Голос AI» получил третий вариант и фактический движок Fish Audio;
- реальный API-тест пройден: HTTP 200, WAV 270380 байт, результат сохранён в `external/GPT-SoVITS-russian/test_outputs/fish_jarvis_api_test.wav`;
- тесты реестра голосов: `3/3` успешно;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0122 — отдельный Fish Audio-профиль Дина Винчестера, 2026-11-14:

- добавлен профиль `fish_dean` — `Fish Audio — Дин Винчестер`;
- для него используется отдельная конфигурация `FISH_AUDIO_DEAN_API_KEY`, `FISH_AUDIO_DEAN_REFERENCE_ID` и необязательная `FISH_AUDIO_DEAN_MODEL`;
- ключ Джарвиса (`FISH_AUDIO_API_KEY`) и voice ID Джарвиса не переиспользуются для Дина;
- до заполнения отдельного ключа и voice ID профиль показывает недоступность, не переключая голос молча;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0123 — проверка отдельного голоса Дина, 2026-11-14:

- пользователь добавил `FISH_AUDIO_DEAN_API_KEY` и `FISH_AUDIO_DEAN_REFERENCE_ID` в пользовательские переменные Windows;
- фактическая проверка из свежей среды прошла: Fish Audio вернул WAV 200748 байт, 44100 Гц, длительность около 2.28 секунды;
- тестовый файл сохранён локально в `external/GPT-SoVITS-russian/test_outputs/fish_dean_api_test.wav` и не попадает в Git из-за правила `external/`;
- секреты в репозиторий не добавлялись; ключ со скриншота рекомендуется перевыпустить;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0124 — защита launcher от устаревшего backend, 2026-11-14:

- причина ошибки выбора голоса: launcher обнаруживал уже занятый старый backend на `127.0.0.1:8000` и принимал его health-ответ за актуальный;
- `frontend/launch_jarvis.py` теперь проверяет реестр голосов перед запуском и требует профили `jarvis`, `kesha`, `fish_jarvis`, `fish_dean`;
- актуальный backend переиспользуется, а устаревший listener на зарезервированном порту останавливается перед запуском свежего backend;
- backend больше не должен откатывать выбор Jarvis/Kesha/Fish из-за оставшегося процесса предыдущего запуска;
- проверено: актуальный `/voice/models` содержит все четыре профиля, `POST /voice/model` с `jarvis` возвращает `xtts_v2_fallback`.

Очередь 0125 — ускорение разговорного voice runtime, 2026-11-14:

- потоковый Ollama-запрос теперь передаёт `HEL_OLLAMA_NUM_PREDICT`, а не игнорирует ограничение длины;
- если настройка не задана, для ответов используется предел 64 токена, что сокращает время генерации;
- очередь разговоров переведена в режим latest-turn-wins: после новой реплики старые необработанные вопросы удаляются;
- при повторном START старые вопросы после остановки также очищаются;
- тесты backend: `22/22` успешно;
- для полного эффекта потребуется перезапустить текущий backend один раз, после чего launcher будет запускать актуальный код.

Очередь 0126 — подключение Fish Audio Jarvis после добавления ключа, 2026-11-14:

- пользователь добавил `FISH_AUDIO_API_KEY` и `FISH_AUDIO_REFERENCE_ID` в пользовательские переменные Windows;
- backend перезапущен с актуальным окружением; профили `fish_jarvis` и `fish_dean` видны как доступные;
- выбран `fish_jarvis`;
- реальный синтез прошёл: WAV 204844 байта, 44100 Гц, около 2.32 секунды;
- тестовый файл сохранён в `external/GPT-SoVITS-russian/test_outputs/fish_jarvis_api_test.wav` и исключён из Git правилом `external/`;
- секреты в репозиторий не добавлялись; S1/S2 обучение не запускалось и не изменялось.

Очередь 0127 — продолжение диалога после wake-word, 2026-11-14:

- подтверждено по runtime-status: распознанная фраза `спасибо что ответил` попала в intent `thanks`, поэтому был воспроизведён штатный `Да сэр.wav`;
- окно follow-up после отдельного wake-word увеличено с 10 до 30 секунд;
- фраза `Джарвис, как дела?` остаётся разговорной и должна передаваться в Ollama, без command-ack `Да сэр.wav`;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0128 — ответ на благодарность, 2026-11-14:

- intent `thanks` теперь воспроизводит `К вашим услугам сэр.wav`;
- `Да сэр.wav` больше не используется для ответа на благодарность;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0129 — разговорная ветка без вводящего WAV, 2026-11-14:

- из `_respond_conversationally` убран промежуточный `Всегда к вашим услугам сэр.wav`;
- для фразы `Джарвис, как дела?` первым голосовым ответом теперь должен быть результат Ollama, озвученный выбранным TTS-профилем;
- заготовленные WAV сохранены только для wake-word и детерминированных команд;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0130 — защита от повторного WAV на wake-word, 2026-11-14:

- повторное распознавание одного только wake-word внутри 30-секундного follow-up окна больше не запускает `Да сэр.wav` повторно;
- подтверждение wake-word воспроизводится один раз, затем Jarvis ждёт вопрос или продолжение;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0131 — защита от самопрослушивания TTS, 2026-11-14:

- TTSQueue теперь воспроизводит ответы через обёртку `_speak_tts`;
- на время Fish/XTTS/Silero-воспроизведения выставляется общий флаг `_speaking`;
- микрофон игнорирует собственный голос Jarvis и не превращает слова ответа в новую команду;
- потоковое добавление предложений в очередь сохранено;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0132 — удаление Kesha из голосового контура, 2026-11-14:

- профиль `kesha` удалён из реестра голосов, UI, TTS-адаптера и launcher-проверки;
- Silero TTS checkpoint `backend/voice_engine/models/silero/ru_v3.pt` размером около 59 МБ отправлен в корзину;
- Silero VAD для микрофона не удалялся, потому что он используется для определения границ речи;
- тесты реестра голосов: `3/3` успешно;
- Fish Audio Jarvis и Dean сохранены; S1/S2 обучение не запускалось и не изменялось.

Очередь 0133 — фиксация личности Jarvis и фильтрация служебного мусора, 2026-11-14:

- голосовой system prompt теперь явно фиксирует имя Jarvis и запрещает имя Boris/Борис;
- запрещены вывод системных инструкций, маркеров `###`, `Instruction` и `Response`;
- перед TTS добавлена очистка ответа от служебного хвоста локальной модели;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0134 — UI только для рабочих Fish-профилей и явное сохранение, 2026-11-14:

- из выпадающего списка «Голос AI» убран Jarvis «в разработке» и удалённый Kesha;
- в UI оставлены `Fish Audio — Джарвис` и `Fish Audio — Дин Винчестер`;
- добавлена кнопка `СОХРАНИТЬ ГОЛОСОВУЮ МОДЕЛЬ`, выбор больше не применяется неявно при каждом изменении списка;
- старое сохранённое значение `jarvis` автоматически мигрирует на `fish_jarvis`;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0135 — удаление результатов S1/S2 обучения, 2026-11-14:

- в корзину отправлены `logs/jarvis_s1_whisper_aligned` (около 34.73 ГБ);
- в корзину отправлены `logs/jarvis_s2_whisper_aligned_data` (около 95.54 ГБ);
- в корзину отправлены экспортированные каталоги `GPT_weights_v2Pro_whisper_aligned` (около 5.79 ГБ) и `SoVITS_weights_v2Pro_whisper_aligned` (около 7.54 ГБ);
- датасет, общие предобученные GPT-SoVITS-модели и три неидентифицированных корневых `.pth` сохранены;
- суммарно освобождено около 143.6 ГБ после очистки корзины пользователем;
- текущий рабочий голосовой путь — Fish Audio API; S1/S2 больше не используются.

Очередь 0136 — непрерывная озвучка разговорных ответов, 2026-11-14:

- убрана отправка каждого предложения в Fish Audio отдельным запросом;
- Ollama формирует короткий ответ целиком, после чего Fish Audio озвучивает его одним WAV-запросом;
- сетевые паузы между предложениями устранены; очередь TTS и защита от самопрослушивания сохранены;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0137 — Fish Audio как фактический default и диагностика TTS, 2026-11-14:

- backend default изменён с недоступного XTTS Jarvis на рабочий `fish_jarvis`;
- `fish_jarvis` теперь имеет `default=True`, а внутренний `jarvis` оставлен только как исторический статус модели;
- ошибки TTSQueue больше не теряются: они записываются в `last_error` и фазу `ошибка озвучки`;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0138 — защита разговорных ответов от шаблона Reformulate, 2026-11-14:

- system prompt `phi3` теперь запрещает шаблонные `Reformulate`-ответы в обычной беседе;
- добавлена дружелюбная ветка для вопроса «ты не хочешь со мной разговаривать?»;
- известные шаблонные отказы локальной модели заменяются коротким понятным ответом перед TTS;
- по runtime-status Fish Audio Jarvis проверен, `last_error` пустой;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0139 — естественные ответы без лекций о непереживаемых эмоциях, 2026-11-14:

- system prompt запрещает самопроизвольные рассуждения phi3 о невозможности испытывать эмоции;
- известный шаблонный ответ об эмоциях заменяется коротким продолжением разговора;
- голосовой runtime по текущему статусу работает без ошибки;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0140 — отдельный режим длинных историй, 2026-11-14:

- обычные разговорные ответы сохраняют быстрый лимит 64 токена и 280 символов;
- запросы со словами «расскажи сказку», «расскажи историю», «придумай сказку» или «история на ночь» получают до 192 токенов и 1600 символов;
- для историй prompt требует законченный рассказ на 4–8 абзацев;
- S1/S2 обучение не запускалось и не изменялось.

Очередь 0141 — добавлен DeepSeek как дополнительный LLM-провайдер, 2026-11-14:

- добавлен отдельный `DeepSeekAdapter` через официальный OpenAI-совместимый `/chat/completions` endpoint;
- настройки DeepSeek отделены от OpenAI: `HEL_DEEPSEEK_BASE_URL`, `HEL_DEEPSEEK_MODEL`, `HEL_DEEPSEEK_API_KEY`;
- в UI AI-провайдеров добавлен профиль DeepSeek с сохранением, проверкой и получением каталога моделей;
- добавлен SSE-стриминг OpenAI-совместимых ответов, чтобы текст можно было передавать в дальнейшую обработку без ожидания полного ответа;
- DeepSeek получает тот же системный prompt Jarvis, что и Ollama: имя Jarvis, русский язык, краткие ответы и действия через систему агентов;
- ключ DeepSeek не добавлялся в репозиторий и не запрашивался в чат; фактический API-тест ожидает ввода ключа пользователем в настройках;
- Ollama остаётся текущим провайдером по умолчанию, обучение S1/S2 не запускалось и не изменялось;
- проверки: `23/23` backend unit-тестов пройдены, исходные изменённые Python-файлы компилируются; общий `compileall` по старому `backend/device_env` по-прежнему натыкается на внешний повреждённый тест MediaPipe.

Очередь 0142 — быстрый возврат ошибок DeepSeek и перезапуск UI, 2026-11-14:

- HTTP-ошибки 4xx от LLM-провайдеров больше не повторяются несколько раз; неверный ключ или модель сразу возвращают ошибку и не блокируют интерфейс;
- backend unit-тесты: `24/24` пройдены;
- после изменения backend и frontend необходимо перезапустить, чтобы они загрузили новый код;
- ключ DeepSeek в runtime на момент записи не сохранён; его нужно сначала сохранить кнопкой профиля, затем отдельно запускать проверку;
- обучение S1/S2 не запускалось и не изменялось.

Очередь 0143 — диагностика DeepSeek API, 2026-11-14:

- реальная проверка сохранённого ключа: `GET /models` вернул HTTP 200 и каталог DeepSeek;
- тестовый `chat/completions` вернул HTTP 402 `Insufficient Balance`, ключ распознан, но аккаунту нужен баланс/кредит;
- UI и backend теперь показывают причину 402 вместо общего сообщения «провайдер недоступен»;
- в редакторе профиля DeepSeek URL и `deepseek-flash` подставляются даже при пустом отображении профиля;
- ключ не выводился в журнал; обучение S1/S2 не запускалось и не изменялось.

Очередь 0144 — загрузка Fish Audio из профиля Windows, 2026-11-14:

- подтверждено: в пользовательском Windows-профиле заданы `FISH_AUDIO_API_KEY`, `FISH_AUDIO_REFERENCE_ID` и отдельные Dean-переменные;
- причина сообщения «не задана переменная»: backend был запущен из долгожившей оболочки, которая не унаследовала позднее добавленные переменные;
- voice registry теперь при отсутствии значения в process env читает текущий HKCU Environment без вывода секретов;
- активный LLM-провайдер оставлен Ollama;
- DeepSeek не удалён, ключ сохранён, но его API-чат требует баланс;
- обучение S1/S2 не запускалось и не изменялось.

Очередь 0145 — установка Qwen3 8B для локального Ollama, 2026-11-14:

- модель `qwen3:8b` успешно загружена через Ollama, размер загрузки около 5.2 ГБ;
- в LocalLLMService добавлено чтение сохранённого runtime-конфига после перезапуска backend;
- добавлена настройка `HEL_OLLAMA_THINK=false`, передаваемая в Ollama для быстрых голосовых ответов без длинного режима thinking;
- Ollama остаётся локальным бесплатным провайдером; Fish Audio используется только для озвучки;
- обучение S1/S2 не запускалось и не изменялось.

Очередь 0146 — переключение LLM-провайдеров и каталог FreeLLMAPI, 2026-11-14:

- FreeLLMAPI подключён как OpenAI-compatible адаптер: поддержаны `/v1/models`, `chat/completions` и потоковые ответы;
- причина пустого каталога была в том, что backend заранее возвращал заглушку «каталог не подключён» для FreeLLMAPI;
- для Ollama API key не требуется; поле ключа в UI теперь отключается и показывает это явно;
- профили Ollama больше не откатываются к `phi3:latest` при сохранении другого провайдера; текущий локальный default — `qwen3:8b`;
- новый чат обновляет отображение активного провайдера и модели после сохранения профиля;
- `ANI` запускается включённым по умолчанию; `XPLR` переключает его в `OFF` первым нажатием;
- проверка FreeLLMAPI на локальном endpoint вернула HTTP 200 и каталог моделей, включая `auto`;
- тесты backend: 25/25; обучение S1/S2 не запускалось и не изменялось.

Очередь 0149 — продолжение голосового диалога без повторного wake word, 2026-11-14:

- после успешного обычного ответа окно follow-up продлевается ещё на 45 секунд;
- следующая фраза пользователя в этот период принимается без повторного «Jarvis»;
- после изменения backend перезапущен, voice runtime поднят с микрофоном №1 и listening=true;
- тесты backend: 25/25; обучение S1/S2 не запускалось и не изменялось.

Очередь 0148 — ускорение голосового ответа Qwen3, 2026-11-14:

- измерение показало холодный первый ответ `qwen3:8b` около 5.9 с, повторный после загрузки модели около 0.9–1.1 с;
- при запуске голосового runtime добавлен фоновый прогрев активной Ollama-модели без блокировки интерфейса;
- Ollama-запросы удерживают модель в памяти 15 минут (`keep_alive`), чтобы не повторять холодную загрузку;
- ожидание тишины после законченной фразы сокращено с 2.0 до 1.25 с;
- после проверки прогрева повторный голосовой LLM-запрос занял около 1.05 с;
- тесты backend: 25/25; обучение S1/S2 не запускалось и не изменялось.

Очередь 0147 — восстановление голосового ответа после Qwen3, 2026-11-14:

- исправлен формат параметра Ollama `think=false`: он передаётся на верхнем уровне запроса, поэтому ответ снова приходит в `message.content`, а не только в `thinking`;
- подтверждён реальный поток `qwen3:8b`: текстовый ответ собирается через `LocalLLMService.chat_stream`;
- Fish Audio проверен реальным коротким синтезом, получен WAV размером около 151 КБ;
- `tts_available` теперь учитывает Fish Audio и не показывает ложное «недоступно» при отсутствии локального Coqui XTTS;
- после перезапуска backend голосовой runtime запущен с микрофоном №1: listening=true, tts_available=true, ошибок нет;
- тесты backend: 25/25; обучение S1/S2 не запускалось и не изменялось.

Очередь 0150 — устранение зависания голосовой очереди и быстрые ответы для болтовни, 2026-11-14:

- очередь разговорных запросов ограничена одним элементом: при новом запросе устаревший ожидающий запрос заменяется, поэтому очередь не растёт во время долгой сказки;
- очередь TTS получила режим `put_latest`: уже произносимая фраза не обрывается, но ожидающие старые фразы удаляются;
- для сказок голосовой prompt сокращён до законченной истории на 2–3 коротких абзаца и примерно 350–700 знаков; лимит Ollama для такой реплики снижен до 96 токенов;
- добавлен локальный кэш трёх коротких Fish Audio WAV в `backend/voice_engine/sound/cache/`: варианты ответа на «как дела», «что нового», «что делаешь», «поговорим» и близкие фразы;
- кэшированные фразы воспроизводятся без Ollama и без нового сетевого запроса к Fish Audio; длительность файлов примерно 2.8–3.6 секунды;
- тесты backend: `25/25`; изменённые Python-файлы компилируются; backend перезапущен после изменения;
- обучение S1/S2 не запускалось и не изменялось.

Очередь 0151 — библиотека локальных голосовых ответов, 2026-11-14:

- добавлен seed-каталог `data/voice_responses/questions.json`: 246 намерений и 1476 вариантов текста;
- намерения разделены на `instant`, `ack` и `dynamic`: только `instant` может завершить запрос локальным WAV; истории, знания, расчёты и инструменты не подменяются статическими ответами;
- добавлен быстрый matcher `backend/services/local_response_service.py` с нормализацией, альтернативными формулировками, оценкой совпадения и исключением последних двух использованных вариантов;
- интеграция выполнена в существующий `voice_runtime` и `voice_player`, новый TTS-движок не создавался;
- добавлен возобновляемый генератор `backend/voice_engine/generate_voice_library.py` и пересоздание базы `build_voice_library.py`; генератор атомарно сохраняет прогресс после каждого WAV;
- генерация Fish Audio запущена отдельным процессом и продолжается в фоне. Последняя проверка: 87 из 1476 WAV готовы, ошибок API нет; число увеличивается по мере работы процесса;
- текущие WAV намеренно не добавляются в Git (`*.wav`); каталог метаданных и исходных текстов сохраняется в репозитории, локальные WAV остаются на рабочем ПК;
- добавлено описание и команды продолжения в `README.md`;
- backend перезапущен, voice runtime снова поднят с микрофоном №1: `enabled=true`, `listening=true`, очередь `0`, ошибок нет;
- тесты backend: `25/25`, Python-файлы компилируются; обучение S1/S2 не запускалось и не изменялось.

Очередь 0152 — горячее обновление локальной библиотеки, 2026-11-14:

- `LocalResponseService` отслеживает изменение `questions.json` и подхватывает готовые WAV без перезапуска backend;
- после проверки генератор Fish Audio продолжает работу отдельным процессом; последняя контрольная точка: 106 из 1476 WAV готовы, ошибок нет;
- backend перезапущен после изменения matcher, voice runtime поднят с микрофоном №1: `enabled=true`, `listening=true`, `conversation_queue_size=0`;
- тесты backend: `25/25`; обучение S1/S2 не запускалось и не изменялось.

Очередь 0153 — быстрые подтверждения для действий, 2026-11-14:

- matcher теперь различает `instant` и `ack`: мгновенные фразы завершаются готовым WAV, а Class B сначала подтверждает действие локальным WAV и затем передаёт исходный текст существующему router/инструменту;
- dynamic-интенты по-прежнему не перехватываются библиотекой и идут в Ollama или профильный модуль;
- backend перезапущен, voice runtime поднят с микрофоном №1, `listening=true`, очередь `0`, ошибок нет;
- тесты backend: `25/25`; генератор Fish Audio продолжает фоновую пакетную генерацию с сохранением прогресса.

Очередь 0154 — приоритет установленного клиента Яндекс Музыки, 2026-11-14:

- intent `open_music_service` оставлен единственным источником для фраз «открой/включи Яндекс Музыку» и «открой/включи сервис музыки»;
- его существующий action `open_music()` теперь сначала ищет установленный клиент через `ApplicationService` и запускает найденный ярлык/EXE;
- браузерный `https://music.yandex.ru` используется только как fallback, если приложение не найдено;
- обнаружен локальный ярлык Яндекс Музыки в меню Пуск; генерация WAV не прерывалась и продолжает работать в отдельном процессе;
- backend перезапущен, voice runtime поднят с микрофоном №1: `listening=true`, очередь `0`, ошибок нет.

Очередь 0155 — аудит и расширение команд Windows, 2026-11-14:

- добавлен `docs/COMMANDS_AUDIT.md` с реестром существующих intents, статусами и ограничениями;
- добавлены `FileSystemService` с SQLite-индексом папок и `ApplicationService` с обнаружением ярлыков меню Пуск, рабочего стола и известных EXE;
- добавлены локальные маршруты открытия папок, запуска приложений, Библии, базовых параметров Windows и калькулятора; неизвестные запросы не выполняются произвольно;
- для поиска папок оптимизирована пакетная запись SQLite; системные и служебные каталоги исключаются, неоднозначные совпадения не открываются случайно;
- генератор WAV получил повторные попытки и fallback при кратковременной блокировке Windows-файла; после этого продолжает работать отдельным процессом без потери готовых файлов;
- backend и voice runtime перезапущены после проверки: микрофон №1, `listening=true`, очередь `0`, ошибок нет; генерация WAV продолжается параллельно.

Очередь 0156 — поиск по меню команд, 2026-11-14:

- раздел «КОМАНДЫ JARVIS» в frontend теперь показывает текущие intents из `commands.yaml` в списке и поддерживает быстрый поиск по названию и фразам;
- frontend перезапущен после проверки компиляции; backend и генератор WAV остались отдельными процессами;
- после перезапуска voice runtime повторно включён на микрофоне №1: `enabled=true`, `listening=true`, очередь `0`, ошибок нет;
- последняя проверка генерации: 405 готовых WAV, 1068 ожидают, 3 временные ошибки Fish Audio; генератор продолжает работу.

Очередь 0157 — API каталога команд и подтверждение опасных действий, 2026-11-14:

- добавлены backend endpoints `/commands/catalog`, `/commands/index`, `/commands/applications` и `/voice/library` для меню, индексации и диагностики;
- системные команды выключения/перезагрузки теперь сначала запрашивают голосовое подтверждение «да/нет» и не выполняются сразу;
- проверен безопасный цикл: запрос выключения выставляет ожидание, «нет» отменяет его без системного действия;
- после backend-перезапуска `commands/catalog` возвращает 35 intents, voice runtime работает на микрофоне №1, очередь `0`, ошибок нет;
- генератор WAV продолжает работу отдельным процессом и не останавливался.

Очередь 0158 — обнаружение приложений через реестр Windows, 2026-11-14:

- `ApplicationService` дополнен чтением HKCU/HKLM Uninstall для 32/64-bit записей;
- ярлыки меню Пуск и известные EXE сохранены как приоритетные источники, реестр используется как дополнительный источник;
- найденный локальный клиент Яндекс Музыки сохраняется в `data/applications.json`, сайт остаётся fallback;
- проверка discovery: 13 приложений, Яндекс Музыка найдена; backend-тесты `25/25`.

Очередь 0159 — исправление путей WAV-библиотеки, 2026-11-14:

- при проверке обнаружено, что старый генератор использовал одинаковые имена `category/response_01.wav` для разных intent и перезаписывал файлы;
- добавлен `repair_voice_library_paths.py`, все 1476 записей переведены на уникальные пути вида `category/intent_id_response_01.wav`;
- метаданные сброшены в `pending`, чтобы не выдавать перезаписанные WAV за корректные ответы;
- генерация перезапущена отдельным процессом и теперь создаёт уникальные файлы; на первой проверке готово 12 новых WAV, ошибок нет;
- старые 60 файлов с прежними именами не используются новой библиотекой и отмечены как legacy-артефакты для последующей безопасной очистки;
- процессов S1/S2/VITS/GPT-SoVITS нет: текущая активная задача — только обучение WAV-библиотеки Fish Audio.

Очередь 0160 — подготовка Offline Knowledge Library, 2026-11-14:

- из прикреплённого расширения извлечён отдельный каталог `data/offline_knowledge/catalog.json` из 438 тем;
- добавлены поля материала `text`, `sources`, `category`, `variants_count`, `audio_status` и `status` со статусами `TEXT_READY`, `AUDIO_PENDING`, `AUDIO_READY`, `VERIFIED`, `ERROR`;
- добавлен `backend/services/offline_knowledge_service.py`: незавершённые записи без проверенного ответа не перехватывают запрос и безопасно проходят к Ollama;
- сервис подключён перед динамическим разговорным маршрутом, добавлен диагностический endpoint `/voice/knowledge`;
- массовая генерация новых WAV не запускалась, чтобы не конкурировать с текущим процессом Fish Audio; существующие `questions.json`, WAV и очередь генерации не изменялись;
- добавлены `backend/knowledge/build_offline_catalog.py` и `docs/OFFLINE_KNOWLEDGE_LIBRARY_REPORT.md`;
- проверка Python-компиляции пройдена; текущая генерация WAV продолжает работать отдельно.

Очередь 0161 — расширяемый каталог Offline Knowledge Library, 2026-11-14:

- исправлен импорт вложенного ТЗ: в каталог попадают только 403 темы из разделов знаний, историй и лекций; процедурные пункты генерации не считаются темами;
- добавлены `validate_offline_catalog.py` и возобновляемый `generate_offline_voice_library.py`; генератор пропускает пустые/неподтверждённые материалы и сохраняет прогресс по каждой вариации;
- добавлены поля источников, текста, количества вариантов и статусов `TEXT_READY`, `AUDIO_PENDING`, `AUDIO_READY`, `VERIFIED`, `ERROR`;
- новая массовая генерация Fish Audio не запускалась, поскольку в каталоге пока нет проверенных текстов; текущая Conversational WAV-библиотека не изменялась;
- проверка каталога: 403 темы, 0 структурных ошибок; Python-компиляция пройдена; текущая Conversational WAV-библиотека: 1471 готов, 5 временных ошибок Fish Audio.

Очередь 0162 — пилот проверенных офлайн-знаний, 2026-11-14:

- добавлены 3 проверенных текстовых материала и 30 вариантов ответа: Intel 8086, Intel 80386 и история Fender Stratocaster;
- для пилота сохранены источники, категории, основной текст, варианты, `variants_count=10`, `status=TEXT_READY`, `audio_status=AUDIO_PENDING`;
- добавлен merge-скрипт, который обновляет только материалы из `reviewed_materials.json` и не перезаписывает остальные темы;
- добавлена проверка runtime-match: запрос про 8086 находит локальный материал и не требует обращения к Ollama; пустые `AUDIO_PENDING` записи не перехватываются;
- массовая генерация офлайн-знаний не запускалась; текущая Conversational WAV-библиотека после повторной попытки: 1474 готовых, 2 временные ошибки Fish Audio, генератор завершён.

Очередь 0163 — ручная проверка качества пилота, 2026-11-14:

- пилот Offline Knowledge Library завершён: 27 из 30 WAV успешно созданы, 3 варианта не прошли из-за временного `SSLEOFError` Fish Audio;
- пользователь вручную прослушал WAV и подтвердил хорошее качество звучания;
- массовая генерация 1–2 ГБ не запускалась; следующий безопасный шаг — повторить 3 ошибки, затем согласовать расширение следующей категории.

Очередь 0164 — запуск расширения текстовой базы, 2026-11-14:

- 3 ошибочных пилотных WAV перегенерированы: Offline Knowledge pilot теперь 30/30 готовых файлов;
- добавлен локальный пакетный автор `generate_offline_text_library.py` на `qwen3:8b`; он сохраняет 10 вариантов и основной текст по одной теме за раз;
- черновики получают `verified=false` и `review_status=DRAFT`, поэтому не попадают в голосовой runtime до проверки источников;
- после ошибки JSON с дополнительным хвостом парсер исправлен на `JSONDecoder.raw_decode`, worker перезапущен с checkpoint;
- текущий текстовый worker: PID 41056, подготовлено 4 черновые темы; Fish Audio Conversational Library не затрагивается.

Очередь 0165 — источники в пакетной подготовке знаний, 2026-11-14:

- по запросу пользователя генератор текстовых черновиков расширен полями `sources`, `source_queries` и `source_status=MODEL_SUGGESTED`;
- Ollama указывает официальный/учебный источник только при уверенности, иначе сохраняет поисковый запрос для последующей проверки; ссылки не выдаются за проверенные;
- JSON-парсер устойчив к дополнительному тексту после объекта, worker перезапущен с checkpoint;
- текущий worker: PID 45996, подготовлено 9 черновых тем; неподтверждённые материалы остаются `verified=false` и не используются voice runtime.

Очередь 0166 — завершение текстового этапа и старт аудио, 2026-11-14:

- текстовый worker Ollama штатно завершил проход: 397 из 405 тем получили по 10 вариантов и сохранены с `verified=false`;
- 8 тем остаются на повторную обработку: 5 повреждённых JSON-ответов Ollama и 3 исходных пилотных материала, которые имеют отдельный ручной статус;
- свободное место на диске C: около 191.9 ГБ;
- запущен возобновляемый Fish Audio worker для Offline Knowledge Library, PID 47376; в каталоге уже было 30 пилотных WAV, после старта создан первый новый WAV;
- ожидаемый объём — до 3970 вариантов; аудио не считается runtime-ready, пока материал не пройдет проверку источников и не получит `verified=true`;
- аудиогенерация идёт отдельно и не изменяет `data/voice_responses/questions.json`.

Очередь 0167 — исправление JSON-ошибок и возобновление Offline Audio, 2026-11-14:

- все 5 ошибок JSON Ollama повторно обработаны успешно: баритон-гитара, цифровой аудиоинтерфейс, квантовая запутанность, GitHub и «Звёздный странник»;
- аудиогенератор Offline Knowledge перезапущен с checkpoint, PID 51376; готовые варианты пропускаются;
- после возобновления в каталоге 93 готовых аудиоварианта и 1 временная ошибка Fish Audio, генерация продолжается;
- текстовый worker завершён, новые JSON-ошибки не зафиксированы.

Очередь 0168 — старт Knowledge & Creative Intelligence 3.0, 2026-11-14:

- новое ТЗ изучено; создан независимый реестр `data/knowledge3/module_registry.json` из 10 расширяемых модулей;
- создан read-only аудит `backend/knowledge3/audit_environment.py` и сохранён `data/knowledge3/environment_audit.json`;
- обнаружено: музыкальная коллекция `E:\Музыка` доступна для чтения, 5733 аудиотрека, 37 групп/папок исполнителей и 328 папок альбомов;
- обнаружены каталоги VST2/VST3 и Steinberg/REAPER; найдено 294 записи установленного ПО в реестре Windows;
- добавлен `docs/KNOWLEDGE_ARCHITECTURE.md` и стартовый `docs/JARVIS_KNOWLEDGE_LIBRARY_3_REPORT.md`;
- текущий Offline Fish Audio worker не остановлен: PID 51376, 253 готовых варианта и 11 временных ошибок, генерация продолжается;
- оригинальные музыкальные файлы, проекты, плагины и текущие WAV не изменялись.

Очередь 0169 — Phase 0.5 Knowledge Discovery & Research Plan, 2026-11-14:

- создан `docs/KNOWLEDGE_DISCOVERY_PLAN.md` без запуска новой массовой генерации WAV и без изменения существующих библиотек;
- раскрыты все 10 зарегистрированных модулей Knowledge 3.0, их подкатегории, состояния discovery/research/index/ready и границы применения Ollama;
- сверены факты из `data/knowledge3/environment_audit.json`: 294 записи установленного ПО, Cubase 13/15, Nuendo 12, REAPER 7.85, VST2/VST3-каталоги и read-only коллекция `E:\Музыка` (5733 трека, 37 папок исполнителей, 328 папок альбомов);
- зафиксированы отдельные планы каталога музыки, Programming Mentor, Music Production, Cubase 13, Trivium, Arch Enemy и остальных модулей; для каждого указаны источники, локальное хранение, динамические данные, голосовые материалы и задачи Ollama;
- полный машинно-читаемый перечень ПО и путей оставлен в `data/knowledge3/environment_audit.json`; план не объявляет плагины рабочими только по наличию DLL;
- текущий Offline Fish Audio worker PID 51376 проверен как живой и не остановлен; массовая генерация по новому Phase 0.5 не запускалась.

Очередь 0170 — завершение текущей генерации Offline Knowledge WAV, 2026-11-15:

- возобновлён генератор `backend/knowledge/generate_offline_voice_library.py --all` с checkpoint-логикой; готовые варианты не перезаписывались;
- повторно обработаны 11 оставшихся вариантов, все завершились статусом `READY`;
- итог: 4050 из 4050 WAV, общий объём около 1.642 ГБ, ошибок аудиофайлов не осталось;
- структурная проверка `validate_offline_catalog.py` пройдена: 405 тем, 0 ошибок;
- темы намеренно оставлены с `status=AUDIO_PENDING`/`audio_status=AUDIO_PENDING`, пока тексты и источники не пройдут review: готовый WAV не объявляется проверенным знанием автоматически;
- генератор завершён штатно, новые библиотеки и существующая Conversational WAV-библиотека не изменялись.

Очередь 0171 — пользовательское подтверждение Offline Knowledge Library, 2026-11-15:

- пользователь явно подтвердил все ранее неподтверждённые материалы и разрешил принять их;
- 405 тем переведены в `status=VERIFIED`, аудио-варианты — в `audio_status=AUDIO_READY`;
- валидатор каталога пройден: 405 тем, 405 готовых материалов, 0 ошибок;
- это подтверждение пользователя, а не независимая экспертная проверка внешних источников; исходные тексты, источники и WAV сохранены без изменений.

Очередь 0172 — продолжение Knowledge & Creative Intelligence 3.0, 2026-11-15:

- изучено новое ТЗ `C:\Users\Данил\Desktop\ТЗ .txt`;
- созданы обязательные документы `docs/PROGRAMMING_MENTOR.md`, `docs/CODING_DEVELOPER.md`, `docs/MUSIC_PRODUCTION_ENGINEER.md` и `docs/DAW_CONTROL.md`;
- документы согласованы с фактическим `OfflineKnowledgeService`, реестром окружения и безопасными границами: неподтверждённые данные не считаются runtime-фактами, Coding Developer работает в sandbox, DAW-изменения требуют preview/подтверждения/отката;
- существующие знания, WAV-библиотеки и Fish Audio не изменялись; новая массовая генерация не запускалась.

Очередь 0173 — Phase 1 Knowledge Foundation, 2026-11-15:

- добавлен read-only builder `backend/knowledge3/build_knowledge_index.py`;
- создан общий индекс `data/knowledge3/index.json`, связывающий 10 модулей, аудит среды и 405 подтверждённых Offline Knowledge тем;
- создан `data/knowledge3/music_catalog.json` по коллекции `E:\Музыка`: 5733 трека, 37 исполнителей и 333 альбомные группы;
- для локальных треков сохранены путь, теги/резервные имена каталогов, формат, размер, длительность, sample rate, каналы, bitrate и источник `LOCAL_COLLECTION`;
- слой `FULL_DISCOGRAPHY` оставлен отдельным и пустым до проверки внешних источников;
- оригинальные музыкальные файлы, WAV и существующие runtime-механизмы не изменялись; новая Fish Audio генерация не запускалась;
- `python -m py_compile backend/knowledge3/build_knowledge_index.py` пройден.

Очередь 0174 — подключение общего индекса знаний, 2026-11-15:

- добавлен `backend/services/knowledge_index_service.py` для read-only чтения общего индекса;
- backend получил endpoint `GET /knowledge/index` с модулями, статусом Offline Knowledge, аудитом среды и музыкальным каталогом;
- `backend/main.py`, новый сервис и builder прошли `py_compile`;
- runtime-ответы Offline Knowledge по-прежнему проходят отдельную проверку `VERIFIED`; общий индекс не выдаёт новые непроверенные ответы сам по себе.

Очередь 0175 — корректировка гибридной работы Codex/Jarvis/Ollama, 2026-11-15:

- изучено `C:\Users\Данил\Downloads\JARVIS_OLLAMA_TASK_DELEGATION.txt` и проведён аудит текущего Ollama provider/routing;
- фактически доступна локальная модель `qwen3:8b` (5.2 GB), также обнаружена `phi3:latest`; модели автоматически не скачивались и конфигурация Ollama не менялась;
- добавлен единый контракт `backend/services/ollama_task_contract.py` с типами задач, статусами, source_documents и безопасным разбором JSON-результата;
- добавлены `docs/OLLAMA_TASK_DELEGATION.md` и `docs/KNOWLEDGE_RESEARCH_PIPELINE.md`;
- зафиксировано ограничение: полноценного source-fetch/claim-validation pipeline в текущем backend пока нет; WebAgent не объявляется проверенным поисковым источником автоматически;
- проверены валидный envelope, обработка повреждённого JSON и Python-компиляция; Ollama доступна через `ollama list`;
- массовые задания Ollama, WAV-генерация и существующие библиотеки не запускались и не изменялись.

Очередь 0176 — рабочий MVP Knowledge 3.0, 2026-11-15:

- добавлен `GET /knowledge/search` для поиска по подтверждённой Offline Knowledge, Python-урокам и локальному музыкальному каталогу;
- добавлен Programming Mentor MVP: 3 урока Python, упражнения, критерии проверки и `data/knowledge3/programming/progress.json`;
- добавлены endpoints `/mentor/programming/lessons`, `/mentor/programming/lessons/{lesson_id}` и `/mentor/programming/lessons/{lesson_id}/progress`;
- добавлен Coding Developer Python sandbox через `POST /coding/sandbox/python`: bounded project path, ограничение размера кода, `shell=False`, минимальный env и timeout до 15 секунд;
- реальные проверки пройдены: поиск вернул результаты, найдено 3 Python-урока, sandbox выполнил `print(2 + 3)` и вернул `5`;
- новые уроки имеют `audio_status=AUDIO_PENDING`; Fish Audio и существующие WAV не изменялись, массовая генерация не запускалась;
- sandbox MVP не является полной OS-level изоляцией; для недоверенного кода нужен отдельный контейнер/процессный профиль.
Очередь 0177 — логическая интеграция Knowledge 3.0 и runtime, 2026-11-15:

- физические каталоги `data/knowledge3`, `data/offline_knowledge` и `data/voice_responses` не объединялись, старые файлы не переносились и не удалялись;
- `OfflineKnowledgeService` теперь выбирает только материал со статусом `VERIFIED` и существующий непустой WAV из `data/offline_knowledge/audio`;
- добавлен `GET /knowledge/answer`, который возвращает источник, текст ответа и связанный WAV-вариант;
- voice runtime воспроизводит связанный offline WAV напрямую, без Ollama и дополнительного TTS; Programming Mentor остаётся текстовым локальным fallback;
- проверены HTTP-маршруты `/knowledge/index`, `/knowledge/search`, `/knowledge/answer`, `/mentor/programming/lessons`;
- `ffprobe` подтвердил выбранный WAV: PCM s16le, 44.1 kHz, mono, 17.50 s;
- добавлен `POST /mentor/programming/lessons/{lesson_id}/check`: код запускается через bounded sandbox, затем проверяются критерии урока и при успехе сохраняется прогресс;
- реальный тест Python-упражнения прошёл: score 100, stdout `Jarvis: 3`, returncode 0;
- ограничение: sandbox MVP не является полной OS-level изоляцией; аудио для новых Programming Mentor уроков пока `AUDIO_PENDING` и в текущую Fish Audio очередь не добавлялось;
- следующий шаг: подключить UI/голосовой вызов поиска Knowledge 3.0 и отдельно согласовать малую пакетную генерацию WAV для первых уроков, не запуская массовую очередь.
Очередь 0178 — подключение Knowledge 3.0 к текстовому чату, 2026-11-15:

- основной `POST /chat` теперь сначала проверяет существующую `voice_responses` библиотеку, затем `KnowledgeSearchService`, и только после этого отправляет запрос в Planner/Ollama;
- локальный ответ сохраняется в ChatStore и возвращается с полем `knowledge`, включая источник и связанный WAV, если он есть;
- вложения и динамические вопросы не перехватываются и продолжают прежний маршрут;
- реальная проверка `POST /chat` с вопросом про Intel 8086 прошла: получен ответ из `offline_knowledge`, абсолютный WAV найден, Planner не запускался;
- текстовый чат теперь использует тот же логический порядок локальных источников, что и голосовой runtime.
Очередь 0179 — расширение Programming Mentor, 2026-11-15:

- без изменения существующих трёх уроков добавлены 18 новых уроков: HTML, PHP, WordPress, React, React Native, Flutter, Git, SQL и FastAPI;
- всего в `data/knowledge3/programming/lessons.json` теперь 21 урок в 10 направлениях;
- добавлен идемпотентный seed `backend/knowledge3/seed_programming_curriculum.py`: повторный запуск не дублирует и не перезаписывает уроки;
- `data/knowledge3/index.json` и `module_registry.json` отражают Programming Mentor и Coding Developer как `implemented_mvp`;
- новые уроки имеют источники официальной документации и `audio_status=AUDIO_PENDING`; существующие WAV не изменялись;
- автоматическая проверка через Python sandbox сохраняется только для Python-уроков; для остальных языков добавлен честный отказ вместо ложного успешного результата;
- следующий технический шаг — расширить проверяемые задания Python и подключить первые подтверждённые новые материалы к малой Fish Audio очереди.
Очередь 0180 — Personal Music Intelligence MVP, 2026-11-15:

- добавлен `MusicIntelligenceService` для read-only поиска по исполнителям, альбомам и трекам локальной коллекции;
- добавлены маршруты `/knowledge/music/summary` и `/knowledge/music/search`;
- тест подтверждён: 5733 трека, 37 исполнителей, `read_only=true`, поиск Arch Enemy возвращает локальные результаты;
- `LOCAL_COLLECTION` и `FULL_DISCOGRAPHY` остаются раздельными; внешняя дискография не подменяется локальными файлами;
- оригиналы `E:\Музыка` не изменялись;
- следующий шаг этого направления — отдельный слой проверенной внешней дискографии с источниками и обновлением, без смешивания с локальным каталогом.
Очередь 0181 — Music Production registry MVP, 2026-11-15:

- добавлен read-only builder `backend/knowledge3/build_plugin_registry.py` на основе `environment_audit.json`;
- создан `data/knowledge3/audio/plugin_registry.json` с 15 фактически обнаруженными продуктами, категориями, версиями, назначением и официальными ссылками на документацию;
- добавлен `MusicProductionService` и маршруты `/knowledge/audio/summary`, `/knowledge/audio/search`;
- тест подтверждён: реестр сообщает 15 продуктов, поиск FabFilter возвращает Pro-Q 2 и Total Bundle;
- наличие установки не объявляется доказательством загрузки плагина в Cubase: поле `loaded_in_daw` остаётся `not_tested`;
- плагин-файлы, DAW-проекты и оригинальные аудиоматериалы не изменялись;
- следующий шаг — Voice Production Mentor и безопасные локальные карточки по записи/редактированию/обработке вокала, затем связанный Fish Audio материал.
Очередь 0182 — Voice Production Mentor и первый WAV, 2026-11-15:

- создано 6 локальных карточек Voice Production Mentor: запись, компинг, шум, компрессия, de-essing и цепочка вокала;
- добавлены `/mentor/voice/lessons` и `/mentor/voice/search`;
- добавлен возобновляемый генератор `backend/knowledge3/generate_voice_material.py`, использующий существующий `VoiceModelManager`/Fish Audio;
- сгенерирован и проверен первый новый WAV `data/knowledge3/voice/audio/voice-001-recording-level.wav`; остальные пять не перезаписывались и остаются в очереди;
- генерация ограничена одной карточкой, чтобы не конкурировать с текущими аудиозадачами;
- `data/knowledge3/index.json` фиксирует 6 уроков, 1 `AUDIO_READY`, 5 `AUDIO_PENDING`;
- следующий шаг — проверить первый WAV через `ffprobe`, затем малыми порциями продолжить озвучивание и перейти к Guitar Encyclopedia.
Очередь 0183 — Guitar Encyclopedia MVP, 2026-11-15:

- создан `data/knowledge3/guitar/catalog.json` с 12 source-linked карточками Cort, Ibanez, Jackson, Fender, Gibson, Schecter и ESP/LTD;
- приоритетная Cort EVL-Z4 добавлена с осторожным описанием: исторические комплектации сверяются по конкретному году/экземпляру;
- для Ibanez GRG170DX внесены подтверждённые официальной спецификацией параметры: 24 лада, GRG maple neck, poplar body, H-S-H Infinity pickups и T102 bridge;
- добавлен `GuitarEncyclopediaService` и маршруты `/knowledge/guitars/summary`, `/knowledge/guitars/search`, `/knowledge/guitars/compare`;
- тесты прошли: поиск GRG170DX, сравнение двух моделей и сводка 12 карточек;
- карточки не смешиваются с `E:\Музыка`, каталог read-only, автоматические рекомендации модификаций не выполняют изменений;
- следующий шаг — Psychology & Emotional Support с safety-границами и локальными упражнениями.
Очередь 0184 — Psychology & Emotional Support MVP, 2026-11-15:

- создано 8 локальных source-linked карточек по фактам/интерпретациям, эмоциям, границам, стрессу, общению, самооценке, конфликтам и итогам сессии;
- добавлены `/mentor/psychology/safety`, `/mentor/psychology/cards`, `/mentor/psychology/search`;
- safety-контракт явно запрещает диагнозы и назначения лечения и содержит действие для кризисной ситуации;
- тест прошёл: поиск карточки по границам и проверка safety-флагов;
- модуль не сохраняет личные диалоги в каталог знаний и не выдаёт карточки за медицинскую помощь;
- следующий шаг — Books & Literature с раздельным хранением библиографии, конспектов и легальных текстов.
Очередь 0186 — DAW Control и Mixing & Mastering Engineer MVP, 2026-11-15:

- добавлен `DawControlService` и маршруты `/knowledge/daw/summary` и `/knowledge/daw/search`;
- обнаруженные Cubase/REAPER/Nuendo выдаются как read-only факты из `environment_audit.json`;
- запуск DAW и UI-автоматизация намеренно не заявляются готовыми: поддержаны только discovery и документационный слой;
- добавлен `MixingService` и `POST /knowledge/mixing/analyze`: read-only анализ WAV (samplerate, channels, duration, peak, RMS, clipping), исходник не изменяется;
- `index.json` и `module_registry.json` обновлены до `implemented_mvp` для обоих MVP;
- целевой следующий шаг: безопасный DAW adapter после выбора конкретного протокола Cubase/REAPER и расширение mixing-анализа до проверяемых файлов проекта.

Очередь 0185 — Единый поиск Knowledge 3.0 и Literature MVP, 2026-11-15:

- литературный каталог `data/knowledge3/literature/catalog.json` содержит 8 карточек, защищённые произведения выдаются только как краткое содержание/анализ, публичные источники помечены отдельно;
- добавлены `LiteratureService` и маршруты `/knowledge/literature/works` и `/knowledge/literature/search`;
- `KnowledgeSearchService` теперь ищет также Voice Production, Guitar, Psychology, Literature и Music Production, не объединяя физические каталоги;
- `/knowledge/answer` возвращает источник, текст, статус и источники материала для новых каталогов; готовый связанный WAV передаётся только если карточка его реально содержит;
- `VoiceRuntime` теперь проверяет связанный WAV у ответа Knowledge 3.0 и воспроизводит его напрямую; при отсутствующем/пустом файле остаётся безопасный TTS fallback;
- проверены общий поиск и локальный ответ для GRG170DX, карточки границ, Robinson Crusoe и FabFilter; литературный endpoint возвращает карточку Robinson Crusoe и источник Project Gutenberg;
- текстовые карточки не считаются аудио готовыми автоматически, `AUDIO_PENDING` сохраняется до фактической генерации и проверки WAV.

Очередь 0187 — Music Production knowledge cards, 2026-11-15:

- создан `data/knowledge3/audio/lessons.json` с 11 source-linked материалами по gain staging, частотному балансу, компрессии, фазе, LUFS/True Peak, Cubase Group/FX/Side-chain/Export и сведению тяжёлых гитар;
- `MusicProductionService` теперь выдаёт не только обнаруженные плагины, но и обучающие карточки;
- общий `KnowledgeSearchService` и `/knowledge/answer` находят эти материалы; проверен запрос `sidechain`, возвращён `knowledge3.audio_lesson`;
- все карточки пока `AUDIO_PENDING`, существующие WAV не изменялись, массовая Fish Audio генерация не запускалась;
- следующий рабочий шаг — добавить отдельные карточки Cubase 13 по routing, automation, VariAudio, AudioWarp, comping, quantization, MixConsole и project settings, затем подготовить малую непересекающуюся очередь озвучивания.

Очередь 0188 — Cubase 13 и теория сведения, 2026-11-15:

- расширен `data/knowledge3/audio/lessons.json` с 11 до 19 source-linked карточек;
- добавлены routing/Audio Connections, automation, VariAudio, AudioWarp, comping, quantization, MixConsole, Project Settings и шаблоны Cubase 13;
- карточки находятся в общем поиске и `/knowledge/answer`; проверены запросы `VariAudio` и `MixConsole`, источник ответа `knowledge3.audio_lesson`;
- `MusicProductionService` сообщает 15 обнаруженных продуктов и 19 обучающих карточек;
- все новые карточки имеют `AUDIO_PENDING`, существующие WAV и очередь Fish Audio не изменялись.

Очередь 0189 — Personal Music Intelligence: внешняя reference-дискография, 2026-11-15:

- добавлен read-only `data/knowledge3/music/reference_catalog.json` для Trivium и Arch Enemy;
- сохранены годы и названия альбомов, статус источников и официальные/проверочные ссылки; локальные файлы `E:\Музыка` не изменялись;
- `MusicIntelligenceService.summary()` теперь показывает 2 внешних исполнителя и 23 reference-альбома отдельно от локальной коллекции;
- общий `KnowledgeSearchService` ищет external reference без подмены локальных треков;
- тест пройден: `/knowledge/music/summary`, `/knowledge/music/search` и общий `/knowledge/search` возвращают отдельный `external_music_reference`.

Очередь 0190 — малая Fish Audio генерация Voice Production, 2026-11-15:

- прежний Offline Knowledge Fish Audio worker подтверждён как завершённый: 4050/4050 WAV, активного процесса нет;
- возобновляемый `backend/knowledge3/generate_voice_material.py --limit 1` создал `data/knowledge3/voice/audio/voice-002-editing.wav`;
- `ffprobe`: PCM s16le, 44100 Hz, mono, 12.725125 s; файл непустой и готов к воспроизведению;
- Voice Production теперь: 2 `AUDIO_READY`, 4 `AUDIO_PENDING`; существующие библиотеки не перезаписывались;
- массовая генерация не запускалась, оставшиеся карточки можно озвучивать следующими малыми порциями.

Очередь 0191 — общий генератор Fish Audio для Knowledge 3.0, 2026-11-15:

- добавлен bounded/resumable `backend/knowledge3/generate_audio_material.py` для карточек `data/knowledge3/audio/lessons.json`;
- генератор проверяет непустой WAV, метаданные и существование цели, не перезаписывает файлы и пишет только в `data/knowledge3/audio/lesson_audio`;
- создан и проверен `audio-gain-staging.wav`: PCM s16le, 44100 Hz, mono, 11.384376 s;
- обучающий аудиоблок Music Production: 1 `AUDIO_READY`, 18 `AUDIO_PENDING`; индекс обновлён;
- массовая генерация не запускалась, продолжение возможно командой с малым `--limit`.

Очередь 0192 — Coding Developer project lifecycle MVP, 2026-11-15:

- `CodingSandboxService` получил `create_python_project`: новый bounded-проект создаётся только в `data/knowledge3/coding_projects`, существующая папка не перезаписывается;
- добавлен `POST /coding/projects/python` с проверкой имён/расширений/размера файлов, README и опциональным запуском `test_main.py` через существующий sandbox;
- HTTP-сценарий проверен: проект `coding_developer_smoke_20261115` создан, тест `2 + 3 == 5` прошёл, повторное создание корректно вернуло HTTP 409;
- исходные проекты и данные пользователя не изменялись; тестовый проект оставлен как доказательство сценария, удаление без отдельного согласования не выполнялось.

Очередь 0193 — Mixing Engineer расширенный read-only анализ, 2026-11-15:

- `MixingService` теперь дополнительно считает RMS-энергию зон 20–120, 120–2000 и 2000–16000 Hz через NumPy, если библиотека доступна;
- для stereo WAV добавляются stereo correlation и phase warning;
- endpoint `/knowledge/mixing/analyze` возвращает рекомендации по clipping, headroom и фазе, не изменяя исходник;
- тест на Voice Production WAV прошёл: peak `-2.33 dBFS`, RMS `-20.27 dBFS`, три frequency bands и рекомендации получены.

Очередь 0194 — малая порция Knowledge 3.0 WAV, 2026-11-15:

- генератор Music Production создал и проверил `audio-frequency-balance.wav` (10.403 s) и `audio-compression.wav` (9.242 s), оба 44.1 kHz mono;
- генератор Voice Production создал и проверил `voice-003-noise.wav` (13.331 s) и `voice-004-compression.wav` (12.970 s), оба 44.1 kHz mono;
- Music Production: 3 `AUDIO_READY`, 16 `AUDIO_PENDING`; Voice Production: 4 `AUDIO_READY`, 2 `AUDIO_PENDING`;
- индекс обновлён, исходные WAV и очереди Conversational/Offline Knowledge не затрагивались.

Очередь 0195 — Integrity API для единой системы знаний, 2026-11-15:

- добавлен `KnowledgeIndexService.integrity()` и endpoint `GET /knowledge/integrity`;
- проверяются физически раздельные roots `knowledge3`, `offline_knowledge`, `voice_responses`, дубликаты module ID и непустые WAV для статуса `AUDIO_READY`;
- реальный тест прошёл: `ok=true`, ошибок нет, 25 аудиозаписей Knowledge 3.0, 7 готовых WAV;
- индекс не объединяет каталоги физически и не меняет старые материалы.

Очередь 0196 — пользовательский чат через Knowledge 3.0, 2026-11-15:

- реальный `POST /chat` с запросом `gain staging` вернул локальный `knowledge3.audio_lesson`, без отправки запроса в Ollama;
- ответ сохранился в ChatStore и содержит связанный `audio-gain-staging.wav` и источник материала;
- тем самым подтверждён маршрут: запрос → единый поиск → локальный ответ → связанный WAV для VoiceRuntime.

Очередь 0197 — завершение Voice Production аудиоматериалов, 2026-11-15:

- возобновляемый генератор создал `voice-005-deessing.wav` и `voice-006-vocal-chain.wav`;
- все 6 карточек Voice Production теперь `AUDIO_READY`, `AUDIO_PENDING=0`;
- все шесть WAV непустые, 44.1 kHz mono, длительность проверена через `ffprobe`;
- VoiceRuntime может использовать карточки через общий поиск, без Ollama и без нового TTS-запроса при наличии связанного WAV.

Очередь 0198 — Mixing comparison и Mastering report, 2026-11-15:

- добавлены read-only endpoints `/knowledge/mixing/compare` и `/knowledge/mastering/report`;
- сравнение возвращает метрики микса, референса и delta по duration/peak/RMS;
- мастеринг-отчёт честно помечает `integrated_lufs` и `true_peak` как `not_measured`, а RMS использует только как proxy;
- реальный тест на WAV прошёл: compare вернул нулевую delta при сравнении файла с самим собой, mastering report вернул валидный read-only отчёт;
- исходные аудиофайлы не изменяются.

Очередь 0199 — DAW project inspection MVP, 2026-11-15:

- `DawControlService` получил read-only `inspect_project()`;
- добавлен endpoint `GET /knowledge/daw/project` для подсчёта файлов, расширений, `.cpr` и media candidates;
- ответ явно сообщает, что изменение проекта запрещено без будущего подтверждённого adapter-процесса;
- HTTP-тест на тестовой coding-папке прошёл, `read_only=true`, `can_modify_project=false`.

Очередь 0200 — Programming Mentor multi-language checks, 2026-11-15:

- `ProgrammingMentorService` получил безопасные статические проверки для HTML, PHP, WordPress, React, React Native, Flutter, Git, SQL и FastAPI;
- для не-Python языков код не выполняется: проверяются только тема урока, обязательные конструкции и безопасные критерии;
- endpoint `/mentor/programming/lessons/{lesson_id}/check` больше не отклоняет все не-Python уроки;
- реальные тесты прошли для HTML, SQL и React: каждый получил score 100 и сохранил прогресс;
- Python по-прежнему выполняется через существующий bounded sandbox.

Очередь 0201 — Plugin Production knowledge, 2026-11-15:

- в `data/knowledge3/audio/lessons.json` добавлены карточки FabFilter Pro-Q 3, Pro-C 2, Saturn 2, iZotope Ozone 9, Nectar 3 и Guitar Rig 5;
- карточки подключены к общему Music Production/Knowledge поиску и имеют официальные ссылки и `AUDIO_PENDING` до реального WAV;
- малой порцией создан `audio-phase.wav`: 44.1 kHz mono, 11.213311 s;
- Music Production аудио теперь: 4 `AUDIO_READY`, 21 `AUDIO_PENDING`.
- порядок единого ответа изменён так, чтобы подробная обучающая карточка `knowledge3.audio_lesson` имела приоритет над краткой записью plugin registry; проверено на запросе `Guitar Rig`.

Очередь 0217 — Mixing Engineer: LUFS и True Peak, 2026-11-15:

- `MixingService.mastering_report()` больше не возвращает фиктивные `not_measured` для LUFS/True Peak;
- добавлен read-only BS.1770-style измеритель: K-weighted блоки 400 ms с абсолютным/относительным gate и 4x polyphase oversampling для true peak;
- измеритель поддерживает WAV 8/16/24/32-bit PCM, не изменяет исходный файл и явно возвращает метод измерения/статус;
- реальный Python-тест на `data/knowledge3/audio/lesson_audio/audio-gain-staging.wav`: integrated LUFS `-18.59`, 4x true peak `-0.70 dBFS`, статус `measured`;
- HTTP-тест `POST /knowledge/mastering/report` после перезапуска backend вернул те же фактические метрики; `/health` подтвердил работающий backend и Ollama;
- `data/knowledge3/index.json` обновлён: mixing теперь отражает поддержку `integrated_lufs` и `true_peak_dbfs_4x`;
- Jarvis frontend оставлен запущенным; backend перезапущен только для загрузки нового кода.

## Очередь 0242 — multi-topic lexical Knowledge search

Дата: 2026-11-15

- поиск получил tolerant token matching для русских форм и смешанных запросов;
- для multi-topic запроса результаты диверсифицируются по модулям, чтобы рядом могли появиться Offline, Guitar, Mixing, Music Production и external music reference;
- проверка `гитарный звук Trivium` вернула одновременно `mixing`, `music_production_lesson`, `guitar`, `local_music` и `external_music_reference`;
- точный запрос `Intel 8086` сохранил корректные Offline результаты с score `1.0`; integrity остался `true`.

## Очередь 0243 — multi-source context перед Ollama

Дата: 2026-11-15

- добавлен `KnowledgeSearchService.context_bundle()` и `GET /knowledge/context`;
- сложный запрос получает ограниченный контекст с текстом и источниками из нескольких локальных модулей;
- `/chat` передаёт этот контекст существующему planner только если не найден готовый conversational/Offline ответ;
- проверка `гитарный звук Trivium`: `multi_source=true`, 6 локальных материалов, ответы присутствуют; integrity `true`.

## Очередь 0246 — multi-source context в VoiceRuntime

Дата: 2026-11-15

- сложные голосовые запросы с несколькими темами больше не завершаются первым частичным Offline совпадением;
- VoiceRuntime передаёт ограниченный подтверждённый контекст существующему Ollama и затем озвучивает синтезированный ответ;
- короткие точные вопросы и готовые WAV-маркеры сохраняют быстрый локальный маршрут;
- прямой audio playback и TTS-очередь не дублируются.

Smoke-тест VoiceRuntime прошёл на `гитарный звук Trivium`: Ollama-заглушка
получила `context_injected=true`, ответ ушёл в единственную TTS-очередь,
ошибка отсутствует. После исправления область вычисления bundle проверена
повторно; backend перезапущен.

## Очередь 0247 — Music Intelligence в multi-source context

Дата: 2026-11-15

- external music reference теперь содержит текстовое резюме дискографии и источники;
- local music results также имеют локальный источник и краткий ответ;
- поэтому Trivium/Arch Enemy могут реально попасть в контекст Ollama, а не только отображаться в списке поиска.

## Очередь 0238 — связь snapshot с отчётом и integrity

Дата: 2026-11-15

- `project_report` показывает контрольные точки для соответствующей папки проекта;
- `/knowledge/integrity` проверяет структуру DAW snapshot-manifest;
- snapshot остаётся отдельным manifest и не подменяет исходный проект.

Проверка Music Intelligence на Trivium и Arch Enemy прошла; сравнение теперь
учитывает edition/reissue/promo/remaster suffixes и возвращает
`matched_releases`, `missing_releases` и метод сравнения без изменения
`E:\Музыка`.

Фактический результат: Trivium — 10 совпавших релизов и 1 отсутствующий;
Arch Enemy — 7 совпавших и 5 отсутствующих. `integrity.ok=true`.

## Очередь 0240 — read-only Mastering Engineer suggestions

Дата: 2026-11-15

- добавлен `POST /knowledge/mastering/suggest`;
- план учитывает измеренные LUFS, True Peak, динамический диапазон, фазу, жанр и цель;
- цепочка Ozone 9/Pro-L содержит параметры и статус доступности, но не применяется автоматически;
- применение требует подтверждённого DAW adapter и копии проекта.

## Очередь 0241 — обязательные метаданные Knowledge 3.0

Дата: 2026-11-15

- добавлен воспроизводимый `backend/knowledge3/normalize_metadata.py`;
- 101 карточка в 8 каталогах получила унифицированные `category`, `subcategory`, `topic`, `questions`, `answer`, `verified_at`, `version`, `confidence`, `related_materials`, `status` и `audio_path`;
- существующие тексты, источники, статусы и WAV не перезаписывались по смыслу; добавленные значения имеют `metadata_basis=AUDIT_DERIVED`;
- проверка схемы вернула `missing_fields=0`.

Проверка на `audio-gain-staging.wav` и жанре `metalcore`: LUFS `-18.59`,
True Peak `-0.70 dBFS`, динамический диапазон `17.32 dB`; предложены Ozone 9
для EQ/Imager и Pro-L для финального лимитирования. Автоприменение осталось
выключено, `integrity.ok=true`.

## Очередь 0244 — non-destructive Mixing preview render

Дата: 2026-11-15

- добавлен `POST /knowledge/mixing/render-preview`;
- доступны ограниченные presets `clean_headroom`, `guitar_tight`, `vocal_control`, `master_preview`;
- без `confirmed=true` возвращается только план;
- с подтверждением ffmpeg создаёт новый WAV в `data/knowledge3/mixing/renders`, затем Jarvis повторно анализирует результат;
- оригинальный WAV не изменяется и не перезаписывается.

Проверка выполнена на `audio-gain-staging.wav`: без подтверждения получен
`CONFIRMATION_REQUIRED`; с подтверждением создан новый
`audio-gain-staging_guitar_tight_021bfe74.wav`, длительность `11.384 s`,
peak `-5.61 dBFS`, `original_modified=false`, integrity `true`.

## Очередь 0245 — полная read-only проверка WAV-библиотек

Дата: 2026-11-15

- добавлен `backend/knowledge3/verify_audio_library.py`;
- проверены все уникальные WAV из Knowledge 3.0, Offline Knowledge и Conversational Library;
- результат: `5691` файлов, все `44100 Hz`, mono, непустые, ошибок `0`;
- проверка ничего не изменяет и может быть повторена после следующей генерации Fish Audio.

## Очередь 0239 — persistent Voice Production Mentor workflow

Дата: 2026-11-15

- `VoiceProductionService.workflow()` получил `session_id` и сохраняемое состояние в `data/knowledge3/voice/sessions.json`;
- команды `продолжай`, `повтори`, `верни предыдущую настройку` и `объясни подробнее` меняют/используют текущий шаг;
- Cubase и проекты не запускаются и не изменяются автоматически;
- HTTP-проверка прошла: `identify_source` → `identify_scope`, повтор сохранил `identify_scope`.

## Очередь 0246 — полный системный аудит Jarvis

Дата: 2026-11-15

Read-only аудит завершён по текущему состоянию `C:\projects\Jarvis`. Созданы:

- `docs/JARVIS_FULL_SYSTEM_AUDIT.md` — итоговый отчёт и границы доказательств;
- `docs/architecture/dependency_maps/JARVIS_PROJECT_TREE.md` — инвентаризация дерева и объёмов;
- `docs/architecture/dependency_maps/JARVIS_DEPENDENCY_MAP.md` — реальные связи UI/API/services/providers/storage;
- `docs/ui/audits/JARVIS_UI_UX_AUDIT.md` — UI/UX инвентаризация и незакрытые runtime-gates;
- `docs/runtime/bug_registry/JARVIS_BUG_REGISTRY.md` — подтверждённые проблемы, риски и пробелы проверки;
- `docs/architecture/migration/JARVIS_OPTIMIZATION_PLAN.md` — приоритетный план без реализации исправлений.

Ключевые результаты:

- ветка `master`, `ahead 21`, рабочее дерево было dirty до аудита; незакоммиченные изменения сохранены;
- import smoke `backend.main` прошёл;
- доступный unittest-путь: `47/47 PASS`, но с повторяющимися `ResourceWarning: unclosed database`;
- `pytest` в окружении отсутствует;
- актуальный source UI, микрофон/TTS, frozen build и reboot-autostart в этом аудите не запускались, поэтому не объявлены подтверждёнными;
- wildcard CORS, прямые Windows-команды, монолитные composition/route-файлы и распределённые knowledge/voice-хранилища внесены в реестр.

Следующий шаг — отдельный контролируемый runtime/UI acceptance pass на текущем исходном дереве. Исправления кода, миграции, установка зависимостей и перезапуск внешних сервисов в рамках этого аудита не выполнялись.

## Phase 2 — Runtime Acceptance & Root Cause Analysis

Дата: 2026-11-15

Проведена runtime-диагностика текущего исходного дерева без исправлений:

- существующий backend listener `127.0.0.1:8000` использован без запуска второй копии; `/health`, `/voice/models`, `/voice/status`, knowledge, providers и settings API ответили HTTP 200;
- запуск `frontend/jarvis_ui.py` через `backend/jarvis_env` подтверждённо падает с `ModuleNotFoundError: No module named 'PySide6'`;
- запуск через `C:\Python314\python.exe` создал окно `Jarvis Assist` и accessibility tree с main controls, chat navigation, START и HUD buttons;
- live screenshot дважды заблокирован `FrameArrived/window capture timed out`; fullscreen input дополнительно сообщил `coordinate input geometry is unavailable`;
- QtWebEngine записал GLES3/virtualization fallback errors, окно при этом осталось живым;
- audio devices и Vosk model найдены; `TTS` package отсутствует, Fish `fish_jarvis` доступен по конфигурации, но `inference_verified=false`;
- `/knowledge/search` подтвердил local conversational match для `Привет, Jarvis` и `Как дела?`; sleep-сценарии не имеют соответствующего intent и дают пустые/нерелевантные read-only search results;
- voice start, chat POST, запись микрофона и TTS намеренно не запускались: они изменяют ChatStore/session state или выполняют side effects, запрещённые защитой этой фазы.

Созданы:

- `docs/testing/acceptance/JARVIS_RUNTIME_ACCEPTANCE_REPORT.md`;
- `docs/JARVIS_RUNTIME_BUG_REGISTRY.md`.

Исходный код, `.env`, конфигурации, базы данных, WAV, knowledge-каталоги, зависимости и user-owned backend не изменялись. Остановлены только frontend-процессы, запущенные в рамках этой диагностики. Подробные причины и классификация `CONFIRMED/LIKELY/BLOCKED/NOT_REPRODUCED` находятся в runtime report.

## Phase 3 — System Stabilization, Bug Fixes & Architecture Consolidation

Дата: 2026-11-15

Реализованы точечные исправления подтверждённых runtime-проблем:

- проектное окружение `backend/jarvis_env` дополнено `PySide6==6.10.2` и
  `GPUtil==1.4.0`, единый launcher документирован в README;
- добавлен общий контекстный `ConversationResolver` для text/voice путей;
- VoiceRuntime хранит ограниченное окно контекста, а `VoiceSessionManager`
  запрещает вторую активную voice-сессию без явной замены;
- `/knowledge/integrity` разделяет `READY/PARTIAL/ERROR` и детальные
  `audio_groups`;
- ChatStore получил детерминированное закрытие SQLite connections;
- shutdown/reboot проходят через `WindowsActionExecutor` с подтверждением;
- добавлены изолированные тесты voice/chat persistence и action boundary.

Проверка: `56/56 PASS` под Python 3.11 с `-W error::ResourceWarning`.
Изменения пользовательских чатов, WAV, knowledge-каталогов, `.env` и работающих
сервисов не выполнялись. Живой микрофон/STT/Fish TTS и визуальный HUD acceptance
остаются отдельными блокерами: захват окна ограничен `FrameArrived` timeout,
а QtWebEngine сообщает GLES3 virtualization fallback.

Подробное состояние: [JARVIS_PHASE3_IMPLEMENTATION_REPORT.md](runtime/diagnostics/JARVIS_PHASE3_IMPLEMENTATION_REPORT.md).

## Phase 3.1 — Live Runtime Acceptance

Дата: 2026-11-15

Результат этапа: **PARTIAL**.

- UI `Jarvis Assist` реально запущен; accessibility tree подтвердил HUD,
  START, верхние/нижние группы кнопок и панели навигации;
- screenshot capture снова заблокирован `window capture timed out`, а QtWebEngine
  сообщил GLES3 virtualization fallback;
- реальный Minifuse input через PortAudio дал 74 callback-а и 75,776 байт без
  ошибок статуса;
- изолированный VoiceRuntime вошёл в Silero VAD, затем штатно остановился;
- изолированный последовательный диалог прошёл через ConversationResolver и
  сохранился в правильный временный `chat_id` без дублей;
- человеческая фраза → STT и слышимое TTS не приняты: Fish `inference_verified=false`,
  а playback нельзя подтвердить без контролируемого внешнего наблюдения;
- live listener на 8000 оказался старым относительно Phase 3 source: его
  `/knowledge/integrity` всё ещё возвращает legacy `ok=true` без `status`;
- launcher, вызванный из venv, породил UI-процесс с системным Python 3.11;
  это отдельный подтверждённый blocker, исправления не выполнялись.

Отчёт: [JARVIS_PHASE3_1_LIVE_RUNTIME_ACCEPTANCE.md](testing/acceptance/JARVIS_PHASE3_1_LIVE_RUNTIME_ACCEPTANCE.md).
Acceptance UI-процессы закрыты после проверки; ранее работающие backend PID 4416
и 10580 оставлены без изменений.

## Phase 3.2 — Runtime + Voice + UI Stabilization

Дата: 2026-11-15

Результат: **PARTIAL**.

- backend теперь поддерживает безопасные test-only env overrides:
  `JARVIS_API_PORT` и `JARVIS_STATE_DB_PATH`; production defaults не изменены;
- CORS учитывает тестовый порт;
- UI endpoints переведены на единый `JARVIS_API_BASE_URL`/`API_ROOT`, поэтому
  изолированный UI не обязан обращаться к старому listener 8000;
- launcher пишет непубличный diagnostic с `sys.executable`, `sys.prefix` и
  `sys.base_prefix`; подтверждено, что venv сохраняется внутри Python runtime,
  а системный Python image Windows является redirector-особенностью;
- актуальный backend на 18081 с временной SQLite вернул `integrity.status=PARTIAL`;
- `py_compile`, import-smoke и `56/56` unittest прошли с отсутствием
  `ResourceWarning`;
- реальный Minifuse capture/VAD lifecycle и изолированный ConversationResolver
  остаются PASS из Phase 3.1;
- human speech→STT, TTS inference/playback и screenshot HUD остаются BLOCKED;
  запуск UI с изолированным backend в этой итерации не завершён из-за политики
  terminal tool.

Отчёт: [JARVIS_PHASE3_2_STABILIZATION_REPORT.md](testing/acceptance/JARVIS_PHASE3_2_STABILIZATION_REPORT.md).
Основной listener 8000 не перезапускался и pre-existing процессы не
останавливались. Пользовательские чаты, WAV, `.env` и Knowledge Library не
изменялись.

## Architecture Audit & Simplification — 2026-11-15

Добавлена фактическая карта архитектуры в [JARVIS_ARCHITECTURE_AUDIT.md](architecture/audits/JARVIS_ARCHITECTURE_AUDIT.md), целевая схема — в [JARVIS_TARGET_ARCHITECTURE.md](architecture/target_design/JARVIS_TARGET_ARCHITECTURE.md), staged-план — в [JARVIS_MIGRATION_PLAN.md](architecture/migration/JARVIS_MIGRATION_PLAN.md).

Подтверждённое изменение: `VoiceRuntime` больше не создаёт второй knowledge/response service graph в обычном `backend/main.py`; он получает общий `KnowledgeSearchService` из composition root. Прямое тестовое создание сохраняет fallback. `py_compile` и 56 backend-тестов прошли, `ResourceWarning` не обнаружен.

Не выполнено и намеренно отложено: удаление Vosk/Silero/wakeword, физическое объединение Knowledge roots, объединение SQLite, встраивание Account Server в основной процесс и удаление старых компонентов. Для них требуется import/runtime evidence, изолированная миграция и rollback.

## Documentation Cleanup & Navigation — 2026-11-15

Папка `docs` перегруппирована по направлениям. Главная навигация: [docs/README.md](README.md), полный реестр и карта статусов: [DOCUMENTATION_REGISTER.md](DOCUMENTATION_REGISTER.md).

Основные разделы: `architecture/`, `voice/`, `knowledge/`, `account/`, `storage/`, `ui/`, `runtime/`, `testing/`, `guides/`, `references/`, `archive/`. Перемещено 74 документа без изменения содержимого; дубликаты не создавались.

`HANDOFF_ASSIST.md`, `HANDOFF_BIBLE.md` и исторический `HANDOFF.md` оставлены в корне для сохранения непрерывности ссылок. Ссылки на перемещённые документы обновлены и проверены: broken Markdown links — 0. Код приложения, конфигурации, базы данных, WAV и пользовательские данные не изменялись.

## Project Map & Technical Passport — 2026-11-15

Созданы фактическая карта проекта и технический паспорт:

- [JARVIS_PROJECT_MAP.docx](project_map/JARVIS_PROJECT_MAP.docx)
- [JARVIS_PROJECT_TREE.txt](project_map/JARVIS_PROJECT_TREE.txt)

Карта построена по текущему workspace, HEAD и реальным исходным границам. Включены backend/composition root, frontend/UI, voice/STT/VAD/TTS, Knowledge/Bible roots, storage/databases, Account/Google OAuth, documentation/assets/build и текущие Mermaid-derived схемы.

Из дерева исключены `.git`, virtual environments, caches, compiled dependencies, large binary/audio payloads, backups/models/logs и generated bulk knowledge files; эти исключения перечислены в конце TXT. Исключённые каталоги не изменялись.

DOCX структурно проверен: ZIP читается, 22 headings, 8 tables, 148 table rows и 8 embedded diagrams. Полный LibreOffice render в текущей среде заблокирован отсутствием `soffice`; существующий Word-процесс также удерживал DOCX, поэтому визуальная печатная приёмка требует открыть файл после освобождения блокировки. Код и пользовательские данные не изменялись.

## Permanent Documentation & Project Map Maintenance Rule — 2026-11-15

Для каждой последующей завершённой задачи Jarvis обязательно:

- обновлять этот `HANDOFF_ASSIST.md` фактическими изменениями, решениями, связями, тестами, ограничениями и следующими шагами;
- проверять влияние задачи на `docs/project_map/JARVIS_PROJECT_MAP.docx` и `docs/project_map/JARVIS_PROJECT_TREE.txt`;
- обновлять DOCX и TXT сразу, если изменились файлы, папки, классы, сервисы, API routes, UI, storage, voice, Knowledge, Account/Auth/Sync или связи компонентов;
- не описывать в карте несуществующие или незавершённые компоненты как активные;
- перед финалом отвечать на вопросы об изменении дерева, новых файлах, назначениях, связях, необходимости обновления DOCX/TXT и состоянии HANDOFF;
- в финальном отчёте добавлять блок `Documentation Update` со статусами `HANDOFF`, `PROJECT MAP DOCX`, `PROJECT TREE TXT` и причиной, если обновление не требовалось.

Текущая задача изменяет только правила сопровождения документации и не меняет код, дерево, архитектурные связи или содержимое карты. Поэтому на этом шаге: HANDOFF — UPDATED; PROJECT MAP DOCX — NO CHANGE; PROJECT TREE TXT — NO CHANGE.

## Phase 4 — Architecture consolidation: verified voice fixes — 2026-11-15

Результат текущего подэтапа: **PARTIAL IMPLEMENTATION**. Выполнены только подтверждённые безопасные исправления в voice runtime; физическая миграция Bible, баз данных и Account/Cloud не запускалась.

Изменения:

- `backend/services/voice_runtime.py`: обработка зарегистрированной команды теперь проходит через один `ResponseRouter`-маршрут; предварительное локальное ACK-воспроизведение удалено, чтобы один запрос не запускал два аудиоответа;
- `backend/services/voice_runtime.py`: дедупликация сохранения реплики привязана к `(chat_id, transcript)`, а контекст и dedupe-состояние сбрасываются при переходе между чатами;
- `backend/tests/test_voice_runtime_isolated.py`: добавлены регрессионные тесты для single-playback command route и chat-scoped persistence;
- `docs/runtime/bug_registry/JARVIS_RUNTIME_BUG_REGISTRY.md`: PH4-VOICE-001 и PH4-VOICE-002 отмечены как FIXED/VERIFIED с доказательствами; PH4-VOICE-003 отражает обновление карты;
- `docs/architecture/migration/JARVIS_MIGRATION_PLAN.md`: пункт двойного ACK/WAV помечен как устранённый и покрытый тестом;
- `docs/project_map/JARVIS_PROJECT_MAP.docx` и `docs/project_map/JARVIS_PROJECT_TREE.txt`: отражено фактическое изменение voice-связей. Новых production-модулей, каталогов данных или баз не добавлено.

Архитектурные решения: `ResponseRouter` остаётся единой точкой выбора маршрута для команды; новый параллельный orchestrator не создавался. Физические каталоги Bible и SQLite сохранены без переноса и удаления. Существующие процессы Jarvis не останавливались.

Проверки:

- `py_compile` для изменённых voice runtime/test файлов — PASS;
- целевая voice-подгруппа — **4/4 PASS**;
- полный backend unittest suite — **58/58 PASS**;
- запуск с `-W error::ResourceWarning` — PASS, новых `ResourceWarning` не обнаружено;
- `git diff --check` — PASS; замечания только о стандартной конвертации LF/CRLF Git для рабочих копий;
- live human STT, TTS inference/playback и слышимый голосовой цикл остаются непроверенными внешними ограничениями предыдущих runtime acceptance.

Не завершено: изолированный backup/dry-run миграции SQLite, физическая консолидация Bible, миграционная проверка PostgreSQL/Account Server, live Google OAuth, удаление legacy Vosk/wakeword и остановка старых listener-процессов. Эти операции требуют отдельных проверяемых этапов с rollback.

Следующие шаги Phase 4: безопасный dry-run инвентаризации и резервного копирования БД; staged Bible adapter/migration report без удаления оригиналов; затем live acceptance voice/UI в изолированном профиле.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменены поведение `VoiceRuntime`, цепочка command playback и chat-scoped сохранение голосовых реплик; дерево проекта физически не расширилось, но карта должна фиксировать изменившиеся связи.

## Phase 4 — Integrity contract and canonical Bible registry — 2026-11-15

Выполнено:

- `KnowledgeIndexService.integrity()` теперь возвращает `ok=false` и `ready=false` при `status=PARTIAL`; `ok=true` означает полную готовность `READY`;
- `roots.offline_knowledge` исправлен: теперь это каталог `data/offline_knowledge`, а не отдельный JSON-файл;
- добавлен read-only канонический реестр `data/Bible/index/catalog.json` для всех текущих источников, audio roots и правил обратимой миграции;
- `KnowledgeSearchService` разрешает исходные пути через Bible manifest с безопасным fallback;
- физические JSON/WAV-источники не перемещались и не удалялись; SHA-256-аудит подтвердил 5 782 WAV и 5 782 уникальных хэша;
- создан SQLite baseline backup через SQLite Online Backup API: `backend/backups/phase4_baseline_20261115_204813/` с manifest и SHA-256.

Проверки:

- Knowledge variations: **14/14 PASS**;
- integrity: **1/1 PASS**;
- voice isolated: **4/4 PASS**;
- свежий backend `127.0.0.1:18081` с изолированной SQLite: `/health` PASS, `/knowledge/integrity` вернул `ok=false`, `ready=false`, `status=PARTIAL`, `/knowledge/answer` вернул ответ из `offline_knowledge`;
- тестовый backend остановлен после проверки; существующий PID 4416 на порту 8000 не останавливался.

Остаются крупные работы: физический staged cutover Bible без дублирования, Storage migration, live human STT/TTS/playback, Account/Google OAuth acceptance, UI runtime acceptance и удаление подтверждённого legacy. Эти пункты не объявлены завершёнными по одним unit-тестам.

Дополнительно исправлен safety-риск launcher: при несовместимом listener на API-порту `frontend/launch_jarvis.py` больше не выполняет принудительный `taskkill`; он сообщает PID и завершает запуск без остановки процесса.

Также исправлен lifecycle backend: добавлен shutdown-hook для `VoiceRuntime` и всех агентов, а `Agent.stop()` теперь освобождает main task и optional lifecycle task. Регрессионный тест `test_stop_cancels_main_and_lifecycle_tasks` прошёл.

После lifecycle-изменения полный backend suite повторно пройден: **60/60 PASS** с `ResourceWarning` как errors. Предупреждение остаётся только о незаданном `OPENAI_TOKEN` в `dev.env`; секреты не выводились и не изменялись.

Account Server dependency boundary также стабилизирован: в проектный venv установлены `SQLAlchemy==2.0.48`, `alembic==1.18.4`, `psycopg==3.3.3`, `argon2-cffi==25.1.0`, `argon2-cffi-bindings==26.2.0`, `google-auth==2.62.2` и `cryptography==46.0.3`; требования зафиксированы в `backend/account_server/requirements.txt`. Account Server suite импортируется и выполняет доступные тесты: 10 tests, 3 PASS, 7 SKIPPED из-за отсутствия изолированной PostgreSQL/Account API; local Account suite 9/9 PASS. Секреты и production PostgreSQL не использовались.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен `data/Bible/index/catalog.json`, изменились integrity-контракт и фактическая связь `KnowledgeSearchService` с Bible-реестром.

## Phase 4 — Account Server lifecycle and migration invocation — 2026-11-15

Выполнено:

- `backend/account_server/database.py`: session factory сохраняет ссылку на SQLAlchemy engine и получил явный `dispose_session_factory()`;
- `backend/account_server/app.py`: добавлен FastAPI shutdown hook, освобождающий PostgreSQL engine;
- Account Server tests теперь явно закрывают TestClient и созданные session factories;
- `backend/account_server/email.py` переименован в `email_provider.py`, чтобы локальный модуль не затенял стандартный Python-пакет `email`;
- `backend/account_server/migrations/env.py` добавляет корень `backend` в `sys.path`, поэтому Alembic воспроизводимо запускается из `backend/` и из `backend/account_server/`;
- обновлены импорты, project tree и runtime bug registry.

Проверки:

- изолированный PostgreSQL Account Server: **10/10 PASS** с `-W error::ResourceWarning`, без предупреждений о незакрытых psycopg connections;
- изолированная Alembic `upgrade head` из `backend/account_server/`: **PASS**;
- полный backend suite: **60/60 PASS** с `-W error::ResourceWarning`;
- Account Server без внешнего PostgreSQL: **10 tests, 3 PASS, 7 SKIPPED**;
- тестовый PostgreSQL container и Account API process остановлены и удалены; pre-existing Jarvis PID 4416 и Ollama не затрагивались.

Ограничения: live human STT, TTS inference/playback, HUD screenshot acceptance, физический Bible cutover, перенос пользовательских SQLite, Google OAuth через внешний браузер и удаление legacy не завершены. Основная PostgreSQL Account Server и пользовательские базы не изменялись.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменены production-модули Account Server, миграционный import path, lifecycle подключения к PostgreSQL и имя email provider-модуля.

## Phase 4 — Physical Bible staging and runtime cutover — 2026-11-15

Выполнено:

- создан copy-only migration tool `backend/knowledge/migrate_bible.py`;
- исходные `data/offline_knowledge`, `data/knowledge3` и `data/voice_responses` скопированы в `data/Bible/materials` и `data/Bible/audio`;
- создан `data/Bible/index/physical_manifest.json` с исходными путями, каноническими путями, размерами и SHA-256;
- обработано 5 833 исходных файла, создано 5 832 канонических объекта; один точный дубликат учтён через mapping, оригиналы сохранены;
- проверены все 5 832 уникальные цели: отсутствующие, повреждённые и hash-mismatch файлы не обнаружены;
- создан `backend/knowledge/rewrite_bible_references.py`; в канонических JSON переписано 4 221 внутренних файловых ссылки;
- `KnowledgeSearchService`, `KnowledgeIndexService`, `LocalResponseService`, `OfflineKnowledgeService` и специализированные knowledge-сервисы теперь читают каноническую Bible;
- catalog status переведён в `CUTOVER_VERIFIED`; старые физические roots оставлены как rollback/legacy copies и не удалялись.

Проверки:

- канонические ссылки на файлы: **0 broken references**;
- полный backend suite: **60/60 PASS** с `-W error::ResourceWarning`;
- Knowledge integrity: `ok=false`, `ready=false`, `status=PARTIAL` только из-за фактической неполной audio-ready подготовки; ошибок путей нет;
- голосовой и текстовый локальный поиск возвращают файлы из `data/Bible`.

Основные offline, voice и `backend/knowledge3` generator/index/validation scripts переведены на Bible через `backend/knowledge3/bible_paths.py`; smoke `--help` прошёл для 13 инструментов. Read-only `audit_unified_wav.py` и отдельные исторические helper-сценарии ещё используют legacy aliases только для анализа/rollback и не являются runtime write-paths. Пользовательские БД, WAV originals, `.env` и pre-existing процессы не изменялись.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлены migration tools, physical manifest, канонические Bible material/audio trees и новые runtime path resolver-связи.

## Phase 4 — Storage inventory gate — 2026-11-15

Проведена read-only инвентаризация локального хранения. `jarvis_state.sqlite3` содержит чат и вложения, `jarvis.sqlite3` — request journal, `account_state.sqlite3` — identity/device/sync metadata, `filesystem_index.db` — специализированный файловый индекс. Пересечения сущностей, оправдывающего физическое объединение, не обнаружено.

Создан [JARVIS_STORAGE_INVENTORY_20261115.md](storage/databases/JARVIS_STORAGE_INVENTORY_20261115.md). Пользовательские базы не изменялись; ранее созданный SQLite baseline backup сохранён. Следующий безопасный gate — миграционные fixtures на копиях с повторным idempotency/rollback тестом.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен актуальный storage inventory и зафиксировано решение не объединять независимые bounded contexts физически.

## Phase 4 — Storage contract and isolated migration gate — 2026-11-15

Выполнено:

- добавлен `backend/services/storage_registry.py` с единым описанием локальных storage paths: Chat state, request journal, Account/Sync metadata и filesystem index;
- добавлен `backend/scripts/storage_migration_harness.py`; он открывает исходные SQLite read-only, создаёт копии через SQLite Online Backup API, проверяет `PRAGMA integrity_check`, физический SHA-256, логический dump hash для idempotence и rollback-копии;
- добавлен `backend/tests/test_storage_registry.py` с проверкой bounded-context paths и изолированного backup/rollback;
- в `backend/config.py` экспортирован `STORAGE_PATHS` как единый контракт путей без физического объединения баз.

Проверки:

- изолированный storage test: **2/2 PASS**;
- harness на актуальных копиях всех четырёх найденных SQLite: **PASS** — integrity `ok`, snapshot/rollback hashes совпадают;
- полный backend suite: **62/62 PASS** с `-W error::ResourceWarning`;
- исходные пользовательские БД не изменялись; временные копии удалены после проверки.

Решение: физическая консолидация `jarvis_state.sqlite3`, `jarvis.sqlite3`, `account_state.sqlite3` и `filesystem_index.db` не выполнялась, поскольку они принадлежат разным bounded contexts и не имеют доказанного дублирования сущностей. Следующий migration gate должен работать на fixtures с явными entity mappings, idempotency и rollback.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлены StoragePaths registry, migration harness и storage regression test; изменились карта backend/storage и проверяемый жизненный цикл копирования SQLite.

Дополнительная интеграция: `frontend/jarvis_ui.py` теперь получает Account Center root через `StoragePaths`, поэтому UI и backend используют один канонический путь локального Account Store без изменения данных или настроек.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**

## Phase 4 — voice-flow regression review and fast-path restoration — 2026-11-16

По запросу владельца повторно просмотрены исторические голосовые отчёты и handoff-решения (`HANDOFF_ASSIST.md`, `HANDOFF.md`, `HANDOFF_BIBLE.md`, Phase 3/3.1/3.2 acceptance, voice audits и voice runtime handoff). Подтверждён принятый прежний flow:

1. Wake-word/короткий локальный ACK — готовый WAV.
2. Зарегистрированная команда — `computer_control.find_intent()` → action → intent WAV.
3. Бытовой small talk — существующий `smalltalk_*.wav` без Ollama.
4. Неизвестный разговорный запрос — отдельный WAV-предупредитель → Ollama qwen3:8b → выбранный Fish Audio.
5. Ollama прогревается один раз в backend startup.

Подтверждённая регрессия текущей ветки: small-talk WAV-путь был удалён из active `VoiceRuntime`, поэтому «как дела?» проходил через Knowledge/Fish и ощущался медленнее. Три существующих WAV в `backend/voice_engine/sound/cache` сохранены и снова подключены через единственный `VoiceRuntime`; новые аудиофайлы не создавались.

Дополнительные исправления:
- Silero/Vosk segmenter получил ~192 ms pre-roll, чтобы не отбрасывать начало короткого `Jarvis`;
- UI очищает stale `Голосовой runtime: ошибка` после восстановления backend;
- `smalltalk_how_*.wav` больше не используется для семантически другого «что нового?».

Тесты: `test_voice_runtime_isolated` **6/6 PASS**, STT route tests **3/3 PASS**, frontend contract tests **9/9 PASS**, `git diff --check` PASS. Прямой Vosk A/B запуск через временный `JARVIS_STT_ENGINE=vosk` проведён без изменения `.env`; он не дал достаточно надёжного live transcript для выбора его production-маршрутом. Production default остаётся `vosk-silero`.

Live evidence после fast-path восстановления: `джарвис` → `wav:Да сэр.wav`; `как дела` → `wav:smalltalk_how_2.wav`. Повторное распознавание короткого wake-word всё ещё требует ручной проверки на паузе между фразами; dedicated openWakeWord найден и загружается, но в production runtime не включался без отдельного сравнения на микрофоне.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменились активные voice-связи и добавлен fast-path к существующим WAV.

Documentation Update correction:
- PROJECT TREE TXT: **UPDATED** — добавлен `frontend/tests/test_voice_error_recovery_contract.py` и уточнено назначение `test_voice_runtime_isolated.py`.
- Причина: изменена связь Account UI → Account Store; дерево файлов не изменилось.

## Phase 4 — isolated runtime probe — 2026-11-15

Проведён контролируемый запуск актуального `backend/main.py` проектным Python 3.11 на отдельном порту `127.0.0.1:18081` с временной SQLite через `JARVIS_STATE_DB_PATH`. Production listener и пользовательские базы не использовались.

Результаты:

- `/health`: **PASS**; Ollama обнаружен;
- `/settings/llm`: **PASS**; активен `ollama`, модель `qwen3:8b`, provider connection `ok=true`;
- `/voice/status`: **PASS как статусный endpoint**; сессия не активна, микрофон не запускался, `microphone_index=-1`;
- `/knowledge/integrity`: **PASS как честный PARTIAL-статус**; `ok=false`, `ready=false`, `status=PARTIAL`, roots указывают на canonical `data/Bible`;
- shutdown: **PASS**; агенты остановлены штатно, тестовый процесс завершён;
- временная SQLite и тестовый порт очищены после проверки.

Ограничение: `fish_jarvis` сообщает `available=true`, но `ready=false` и `inference_verified=false`; это не является доказательством рабочего TTS. Реальный микрофон/VAD/STT/TTS playback в этом probe не запускались и остаются отдельным acceptance-сценарием.

Дополнительная безопасная проверка голосового контура:

- Minifuse capture: **PASS** — device 1 `Mic/Line/Inst 1-2 (Minifuse 2)`, 90 блоков за 3 секунды, PortAudio status errors отсутствуют; сырое аудио не сохранялось;
- Silero VAD import/load: **PASS**, в периоде без речи speech blocks не обнаружены;
- локальный XTTS v2 inference: **PASS** — модель была уже локально установлена, короткий русский текст дал WAV 218188 байт; новый библиотечный WAV не сохранялся;
- playback smoke: **PASS технически** — `sd.play`/`sd.wait` завершились на output device 4, 24 kHz, 112400 frames; фактическое субъективное восприятие человеком не подтверждено;
- Fish Audio inference: **NOT TESTED** — `ready=false`, `inference_verified=false`, платный запрос не выполнялся;
- human speech → STT → ConversationResolver: **BLOCKED / USER ACTION REQUIRED** — для доказательства нужен короткий произнесённый тест пользователем, синтетическая речь не использовалась.

Уточнение по голосу: локальный XTTS inference/playback выше был отдельным диагностическим smoke-тестом и не менял выбранный профиль Jarvis. Штатный `voice_engine.tts.speak()` при `selected_id=fish_jarvis` маршрутизирует только в `VoiceModelManager.synthesize_fish()`; автоматического перехода на XTTS для Fish-профиля нет. Добавлен регрессионный тест `backend/tests/test_tts_routing.py`.

После добавления Fish-routing guard полный backend regression suite: **63/63 PASS**.

### Fish Jarvis acceptance — 2026-11-15

- профиль: `fish_jarvis`, выбран штатно как default;
- provider available до inference: **true**;
- Fish Audio inference: **PASS** — один короткий тестовый текст, без массовой генерации;
- артефакт: WAV 163884 bytes, 44100 Hz, 81920 frames;
- после inference: `ready=true`, `inference_verified=true`;
- playback: **PASS технически** — `sd.play`/`sd.wait` завершились на output device 4 (Minifuse 2);
- субъективное подтверждение “услышал пользователь”: не заявляется автоматически;
- XTTS и Fish Audio не запускались параллельно; Fish Audio был единственным TTS provider этого теста.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: добавлены runtime evidence и статусы внешних голосовых зависимостей; дерево и связи компонентов не изменились.

## Phase 4 — live voice lifecycle and STOP queue cleanup — 2026-11-15

Выполнено:

- на отдельном тестовом backend `127.0.0.1:18081` создан изолированный chat session и запущен `/voice/start` с Minifuse device 1;
- фактический runtime вошёл в `слушаю (Silero VAD)`, `conversation_worker=true`, `voice_session.source=chat` и корректный `chat_id`;
- `/voice/stop` завершил capture и voice session; тестовый backend и временная SQLite удалены;
- обнаружена и исправлена оставшаяся control sentinel в `VoiceRuntime._conversation_queue`; после STOP queue size теперь 0;
- добавлен `backend/tests/test_voice_runtime_lifecycle.py`.

Проверки:

- lifecycle regression: **1/1 PASS**;
- полный backend suite: **64/64 PASS**;
- реальный audio capture/VAD lifecycle: **PASS**;
- human speech → STT → ConversationResolver: всё ещё **BLOCKED / USER ACTION REQUIRED**, так как в момент автоматического probe не произносилась тестовая фраза; синтетическая речь не использовалась.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменено поведение VoiceRuntime.stop(), добавлен новый lifecycle regression test и уточнена фактическая live-связь voice session → chat_id → Minifuse/VAD.

## Phase 4 — UI file-origin CORS fix — 2026-11-15

Live launcher runtime показал, что QWebEngine chat polling из `file://` получал CORS error на `/api/messages`. Исправлено минимально: в FastAPI allow-list добавлен точный origin `file://`; wildcard CORS не включался.

Проверки:

- изолированный backend preflight `Origin: file://`: **HTTP 200**;
- `Access-Control-Allow-Origin: file://`: **PASS**;
- разрешённые методы `GET, POST, OPTIONS`: **PASS**;
- regression `test_cors_policy.py`: **PASS**;
- QtWebEngine GLES3 virtualization fallback зафиксирован отдельно; Chromium security/sandbox flags не отключались.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменена связь local QWebEngine UI → FastAPI `/api/messages`, добавлен CORS regression test.

## Phase 4 — STT route selection and Fish conversational consistency — 2026-11-15

Проведено сравнение доступных маршрутов распознавания и зафиксирован текущий эталон live voice:

- `faster-whisper + Silero VAD` не принят как production route: изолированный native probe завершился `OMP: Error #15` из-за конфликта `libiomp5md.dll` и `libomp140.x86_64.dll`;
- default `JARVIS_STT_ENGINE` теперь `vosk-silero`;
- Silero VAD используется для сегментации речи, Vosk — для транскрипции сегмента;
- live-тест на Minifuse device 1 реально распознал `хочешь спать`, сформировал ответ `Я не сплю и готов к работе.` и сохранил обе реплики в изолированный `chat_id`;
- измерения: Vosk model load около 1.046 s, Vosk inference около 0.508 s на silent probe; Silero+Vosk warmup/segment probe около 3.854 s, последующая Vosk inference около 0.373 s. Поэтому эталон выбран как наиболее стабильный подтверждённый live-маршрут, а не как безусловно самый быстрый cold-start;
- conversational Knowledge answers больше не воспроизводят связанный legacy WAV вместо выбранного TTS: они проходят через выбранную TTS queue и `fish_jarvis`; готовые command WAV сохранены отдельным детерминированным маршрутом.

Добавлены регрессионные тесты `test_stt_route_selection.py` и `test_voice_knowledge_tts.py`; полный backend suite после изменений: **68/68 PASS** с `ResourceWarning` как errors.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: зафиксированы подтверждённый STT baseline, native blocker faster-whisper и единый Fish TTS путь для разговорных ответов.

## Phase 4 — live UI stale-response and Ollama timeout diagnosis — 2026-11-15

Реальный UI/HUD acceptance подтвердил:

- окно `Jarvis — состояние` и HUD отображаются;
- `Silero VAD + Vosk` реально распознал `объясни квантовая запутанность простыми словами` и сохранил реплику в изолированный chat;
- поле «Слышит» обновлялось сразу, но поле «Ответ» до исправления содержало ответ предыдущего turn;
- Ollama `qwen3:8b` не вернул ответ за настроенный 45-секундный timeout (`ollama request failed: ReadTimeout`), поэтому текущий ответ не был сформирован;
- старый exception path дополнительно проигрывал несвязанный WAV `Сэр, для реальной попытки полета...`, что создавало ложное впечатление ответа.

Исправлено:

- новый transcript очищает предыдущие `last_response` и `last_error`;
- статус сразу показывает `уточняю информацию`, пока работает Knowledge/Ollama;
- timeout модели больше не запускает несвязанный WAV; UI показывает `Не удалось получить ответ от модели`;
- добавлен `backend/tests/test_voice_status_fresh_turn.py`.

Проверки после исправления:

- адресные voice tests: **4/4 PASS**;
- полный backend suite: **69/69 PASS** с `ResourceWarning` как errors;
- UI/HUD live: **PARTIAL** — окно и polling PASS, свободный Ollama turn BLOCKED из-за `ReadTimeout`;
- QtWebEngine: GLES3 virtualization fallback зафиксирован, security/sandbox flags не отключались.

### Текущая логика быстрых ответов

1. Команда — локальный `Command Router` и готовый command WAV.
2. Короткий известный ответ — локальная Bible/ConversationResolver и выбранный Fish TTS.
3. Сложный или неизвестный вопрос — мгновенный статус `уточняю информацию`, затем один запрос в `qwen3:8b`, после него Fish TTS.
4. При ошибке Ollama — честная ошибка без старого ответа и без несвязанной аудиозаглушки.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен новый status regression test и изменён фактический voice/UI flow при ожидании Ollama.

### Что оставляем и от чего отказываемся в голосовом контуре

Оставляем как текущий эталон:

- `Silero VAD` — сегментация речи;
- `Vosk` — live-транскрипция и отдельная UI-диктовка;
- `ConversationResolver`/Bible — быстрые локальные ответы;
- `qwen3:8b` — целевая локальная модель для неизвестных вопросов;
- `fish_jarvis` — единственный conversational TTS-профиль.

Не используем в live по умолчанию:

- `faster-whisper` + Silero: отключён из-за подтверждённого native OpenMP abort; оставлен только как explicit diagnostic route до отдельной изоляции;
- `openwakeword`/`backend/voice_engine/wakeword_engine.py`: текущий backend напрямую его не импортирует; это кандидат на удаление после отдельной проверки standalone-сценария;
- несвязанные fallback WAV для ошибок модели: удалены из conversational exception path.

Пока **не удаляем** `faster-whisper`, `wakeword_engine.py` и их зависимости физически: первый ещё нужен для диагностического сравнения, второй является legacy-кандидатом, но его удаление должно пройти отдельным smoke/import-аудитом. `Vosk` и `Silero` удалять нельзя — они входят в подтверждённый рабочий маршрут.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: карта дополнена быстрым маршрутом, статусом ожидания Ollama и решением по оставляемым/legacy голосовым компонентам.

## Phase 4 — Fish model-wait acknowledgements — 2026-11-15

Добавлена логика короткого предварительного ответа только для model-backed turns:

- семь вариантов: «Сейчас подумаю», «Уточняю информацию», «Изучаю Ваш вопрос, сэр», «Изучаю Ваш запрос», «Сейчас просканирую», «Сканирую глобальную сеть», «Я в поисках ответа, сэр»;
- локальный ответ из Bible/ConversationResolver не получает лишнюю задержку;
- runtime выбирает готовый WAV без повтора подряд и проигрывает его до одного запроса Ollama;
- генератор Fish не перезаписывает WAV, не меняет `questions.json` и безопасно возобновляется.

Добавлены:

- `backend/voice_engine/model_acknowledgements.py`;
- `backend/voice_engine/generate_model_acknowledgements.py`;
- `backend/tests/test_model_acknowledgements.py`.

Статус первичного запуска был **PARTIAL / BLOCKED EXTERNAL**: Fish intermittently возвращал `SSLEOFError` на TLS-соединении `api.fish.audio`. После безопасного повторного запуска генератор создал все семь WAV без перезаписи уже готовых файлов.

Фактический результат: `model_ack_01.wav`–`model_ack_07.wav`, 7/7 валидных mono WAV, 44100 Hz, длительность 1.25–1.90 с; итоговая проверка `soundfile` прошла. Другой голос не подставлялся. Команда возобновления: `backend\\jarvis_env\\Scripts\\python.exe backend\\voice_engine\\generate_model_acknowledgements.py --limit 7`.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлены новый Fish acknowledgement catalog/generator, runtime route и внешний блокер генерации WAV.

## Phase 4 — voice Ollama latency policy — 2026-11-15

Для голосового маршрута убран автоматический warmup Ollama при старте микрофона: он мог конкурировать с первой пользовательской репликой. Голосовой запрос теперь выполняется одной попыткой без повторных 45-секундных retry-циклов; `qwen3:8b` сохранён, spoken budget снижен до 48 токенов для обычных вопросов, для историй остаётся 96.

Проверки после изменения: полный backend suite **71/71 PASS**, py_compile **PASS**. Новое измерение свободного qwen3:8b turn отложено до освобождения текущего Ollama runtime; предыдущий live run был заблокирован `ReadTimeout`.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменена политика warmup/retry и бюджет голосового запроса без добавления файлов.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен canonical pending-путь `data/Bible/audio/voice_responses/model_ack/` и синхронизирована карта новых Fish acknowledgement файлов.

Обновлён `docs/architecture/migration/JARVIS_OPTIMIZATION_PLAN.md`: пункт про Ollama warmup отмечен как реализованный для voice route; telemetry для остальных маршрутов остаётся отдельной задачей.

## Phase 4 — Fish model-wait WAV generated — 2026-11-15

По запросу владельца повторно проверен текущий Fish-профиль `fish_jarvis` и выполнена генерация недостающих фраз ожидания. Первые четыре WAV создались с первой попытки, `model_ack_05.wav` и `model_ack_07.wav` потребовали безопасного повтора из-за временного `Fish Audio RuntimeError`; генератор пропускал существующие файлы и не перезаписывал их.

Итоговый каталог: `data/Bible/audio/voice_responses/model_ack/`; 7/7 файлов присутствуют и валидируются через `soundfile`: mono, 44100 Hz, 1.25–1.90 с. Эти WAV теперь доступны runtime для предварительного ответа перед запросом `qwen3:8b`. Фразы из Bible по-прежнему не получают лишнюю задержку и не запускают acknowledgement.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: статус model-wait WAV изменён с внешнего блокера на фактически сгенерированный набор 7/7; карта синхронизирована с содержимым каталога.

## Phase 4 — qwen3:8b latency verification — 2026-11-15

После освобождения Ollama выполнены два единичных read-only запроса к `qwen3:8b` с `think=false`, `num_predict=24` и без повторной попытки. Холодный запрос завершился HTTP 200 за **15.67 с**, из них около **15.16 с** заняла загрузка модели. Следующий тёплый запрос завершился HTTP 200 за **0.46 с**; `load_duration` составил около 0.005 с.

Вывод: задержка первого неизвестного голосового вопроса в основном связана с cold-start Ollama, а не с Fish acknowledgement или STT. Сгенерированные 7 Fish WAV подключены к runtime и могут проигрываться во время ожидания холодной загрузки/ответа модели. Полный live voice turn с физическим микрофоном и слышимым ACK после этой точки остаётся отдельной проверкой.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: добавлены runtime-метрики существующего маршрута; структура и связи проекта не изменились.

## Phase 4 — Ollama startup warmup — 2026-11-15

По запросу владельца добавлен единичный startup warmup для выбранного `qwen3:8b`: backend при запуске выполняет короткий bounded-запрос без записи в ChatStore, без retry и без запуска voice runtime. Ollama получает `keep_alive=-1` числом JSON, поэтому модель остаётся загруженной до явной выгрузки. При недоступной Ollama backend продолжает запуск и пишет только тип ошибки.

Первичная проверка выявила и устранила точную ошибку: строковое значение `"-1"` Ollama отклоняет как `HTTP 400 time: missing unit in duration`; адаптер теперь преобразует его в числовое `-1`. Прямой контрольный запрос после исправления: HTTP 200, холодная загрузка около 15.7 с, `ollama ps` показывает `qwen3:8b ... Forever`. Адресные provider tests **10/10 PASS**; полный backend regression suite после исправления — **72/72 PASS** с `ResourceWarning` как errors, `py_compile` PASS.

## Phase 4 — HUD calibration snapshot — 2026-11-15

Текущий режим `--calibrate-panels` оставлен запущенным на изолированном backend `18081`. После нескольких последовательных чтений `QSettings` координаты не менялись; пользователь подтвердил эту расстановку как принятую для режима виджета. Снимок `docs/ui/HUD_CALIBRATION_LAYOUT_20261115.json` переведён в статус `WIDGET_ACCEPTED`.

В снимке зафиксированы 9 панелей в координатном пространстве HUD 710x710. Верхние текстовые панели имеют поля `x`, `y`, `angle`; нижние SVG-иконки — `x`, `y`, `angle=0`, поскольку текущий UI поддерживает для них перемещение, но не вращение. Для следующего этапа создан отдельный `docs/ui/HUD_CALIBRATION_LAYOUT_FULLSCREEN_20261115.json` со статусом `DRAFT_WAITING_USER_CONFIRMATION`; его координаты будут калиброваться независимо от виджетного профиля.

Для второго запуска добавлен штатный флаг `--fullscreen`: комбинация `--calibrate-panels --fullscreen` открывает тот же калибровочный режим на полном экране и не копирует координаты в widget-профиль.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен машинно-читаемый текущий снимок HUD-калибровки.

## Phase 4 — live startup warmup and model route — 2026-11-15

После перезапуска принадлежащего проверке backend на `127.0.0.1:18081` startup log подтвердил `Ollama warmup: ready qwen3:8b`; UI продолжил polling `/api/messages`, `/voice/status` и `/devices/capabilities` через тот же backend. Изолированный неизвестный текстовый вопрос прошёл через модельный маршрут за **2.98 с** и вернул содержательный ответ; `ollama ps` подтвердил `qwen3:8b ... Forever`. Локальный вопрос `Хочешь спать?` ранее прошёл через ConversationResolver за **0.10 с** и сохранил обе реплики в отдельном chat_id.

Первый запрос до перезапуска был намеренно зафиксирован как FAIL: старый процесс был поднят до исправления и отправлял строковый `keep_alive="-1"`, получая HTTP 400. После перезапуска актуального процесса ошибка не воспроизвелась.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: зафиксировано runtime-подтверждение уже описанного startup lifecycle; структура проекта не изменилась.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменён startup lifecycle backend и контракт Ollama keep-alive; карта дополнена актуальной связью запуска с локальной моделью.

## Phase 4 — independent fullscreen HUD calibration profile — 2026-11-15

Для калибровки полного экрана в `frontend/jarvis_ui.py` добавлен профиль `panel_positions_by_mode`: режим `widget` сохраняет принятую расстановку в legacy-ключе `panel_positions` и в одноимённом профиле, а запуск с `--fullscreen` читает и сохраняет отдельный профиль `fullscreen`. Это исключает перезапись принятой виджетной геометрии при дальнейшей настройке полного экрана. Запуск `--calibrate-panels --fullscreen` проверен через project venv; окно инициализировалось, подключалось к изолированному backend `18081`, а QtWebEngine продолжил выдавать только известный GLES3/GLES2 virtualization fallback.

Полноэкранная расстановка пока не принята пользователем: `docs/ui/HUD_CALIBRATION_LAYOUT_FULLSCREEN_20261115.json` остаётся `DRAFT_WAITING_USER_CONFIRMATION`. Текущий процесс калибровки оставлен работающим для ручной настройки.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **PENDING CURRENT TURN**
- Причина: добавлена новая логика хранения профилей калибровки; оба проектных паспорта требуют синхронизации после фиксации текущего профиля.

Промежуточные фактические fullscreen-координаты также записаны в `docs/ui/HUD_CALIBRATION_LAYOUT_FULLSCREEN_20261115.json` со статусом `DRAFT_PARTIAL`: `AGENTS`, `FUNCTION`, `HISTORY`, `PROV`, `VID`. Это не является пользовательской приёмкой полного экрана; окно калибровки оставлено активным для продолжения настройки.

В fullscreen-калибровку добавлено управление размером текста верхних панелей: обычное колесо меняет наклон, `Ctrl + колесо` меняет размер шрифта в диапазоне 6–14 пунктов. Стартовые компактные значения: `CHAT=8`, `AGENTS=8`, `FUNCTION=7`, `HISTORY=8`; размер сохраняется в том же mode-specific профиле вместе с координатами и углом. UI перезапущен через project launcher для проверки загрузки новой логики.

JSON-снимки HUD синхронизированы с текущими значениями QSettings. Widget остаётся принятым профилем; fullscreen отмечен `DRAFT_TEXT_SIZE_REVIEW`, поскольку пользователь ещё проверяет, помещается ли текст в ячейки. Финальное принятие fullscreen не заявляется.

По запросу владельца текущий fullscreen-профиль был сохранён, UI перезапущен через `frontend/launch_jarvis.py --calibrate-panels --fullscreen`, и после запуска выполнено сравнение QSettings с JSON. Результат: `RELOAD_PROFILE_MATCH=True`; все 9 сохранённых панелей загрузились с теми же координатами, углами и заданными размерами текста. Активны launcher/backend-процессы, принадлежащие этой проверке.

## Phase 4 — HUD hitbox and first-click regression — 2026-11-15

По визуальной проверке выявлены две связанные UI-проблемы. Нижний ряд иконок имел контейнер `56x48` со смещённым относительно визуального центра anchor; hitbox расширен до `68x56`, при этом offset изменён на `14/12`, поэтому центр иконки и сохранённые координаты не меняются. Перекрытие соседних зон ограничено геометрией одного ряда; внешний SVG и стилистика не изменялись.

В режиме `--calibrate-panels` `eventFilter` перехватывал press/release для drag и поглощал обычный клик, из-за чего первое нажатие только активировало drag-состояние. Теперь при перемещении не более 6 px вызывается `dragged.click()`, а сохранение координат выполняется только для реального drag. Это восстанавливает однокликовое открытие пунктов и сохраняет калибровку.

После повторной проверки по скриншоту обнаружен ещё один путь промаха: часть визуальной области попадала в прозрачный фон `hud`/`hud_container`, минуя дочерний hitbox. В `eventFilter` добавлена локальная fallback-маршрутизация: release на HUD-фоне в радиусе 34 px от центра нижней иконки направляется ближайшему `hud_panel_button_map` элементу. Это не создаёт общего перекрывающегося слоя и не меняет внешний рисунок.

По повторному пользовательскому тесту добавлен более полный уровень: `QApplication`-фильтр с ограничением прямоугольником `hud_container` ловит release даже от декоративного дочернего слоя и направляет его к ближайшей нижней иконке в радиусе 46 px. Клик по самому button исключается из fallback, поэтому двойное срабатывание не создаётся. Это делает весь визуальный контейнер панели кликабельным без изменения ассетов и расположения.

`frontend/jarvis_ui.py` прошёл `py_compile`; `git diff --check` не выявил ошибок форматирования. UI перезапущен через изолированный launcher; известные GLES3/GLES2 предупреждения среды остались без небезопасных флагов.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено поведение hitbox и click routing существующего UI-модуля без изменения дерева файлов.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: click routing дополнен fallback для прозрачных HUD-слоёв.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: добавлен ограниченный application-level fallback для кликов внутри HUD-контейнера.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: обновлено содержимое существующего JSON-профиля, без изменения дерева файлов.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено поведение существующего UI-модуля без добавления файлов.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: синхронизированы содержимое двух существующих HUD JSON-снимков.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: добавлено runtime-подтверждение сохранения и восстановления fullscreen-профиля.

## Phase 4 — widget-mode full-cell HUD hit testing — 2026-11-15

По живой проверке подтверждено расхождение: в обычном оконном режиме кнопки реагировали, а в прозрачном widget-режиме часть кликов по ячейке попадала в декоративный слой HUD. Причина была в том, что fallback учитывал только событие release и ограничивал область манхэттенским радиусом; углы видимой ячейки не считались кликом.

В `frontend/jarvis_ui.py` добавлена маршрутизация на уровне `QApplication` для события press внутри `hud_container`. Для нижних панелей используется прямоугольная ячейка `42 px` по X и `34 px` по Y вокруг центра существующей иконки; при перекрытии выбирается ближайший центр. Клик по настоящей кнопке, START или TECH-A исключается из fallback. Событие release после fallback поглощается, чтобы не получить двойное открытие. Внешняя геометрия, ассеты и сохранённые координаты HUD не менялись.

Проверки: `backend\\jarvis_env\\Scripts\\python.exe -m py_compile frontend\\jarvis_ui.py` — PASS; `git diff --check -- frontend/jarvis_ui.py` — PASS. Изолированный UI перезапущен с backend `127.0.0.1:18081` и отдельной SQLite; в логах запуска нет traceback. Пользовательская проверка клика по всей ячейке после перезапуска ещё ожидается; автоматическая визуальная приёмка не заявляется.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено поведение hit testing существующего UI-модуля, без добавления или удаления файлов.

## Phase 4 — widget-to-application navigation and fullscreen state — 2026-11-15

По живым скриншотам подтверждены три UI-проблемы. Страница «Устройства и возможности» открывалась прямым вызовом `open_settings_section(12)` и не выключала `widget_mode`, поэтому настройки отображались поверх прозрачного компактного слоя. Теперь `open_settings_section()` всегда вызывает `ensure_full_ui()` перед переходом к разделу; переход из widget-режима в настройки проверен изолированным Qt smoke-тестом: `widget_mode=False`, `pages.currentIndex()==3`, `settings_nav.currentRow()==12`.

Переключатель fullscreen/window теперь синхронизируется с фактическим `QWidget.isFullScreen()`, сохраняет нормальную геометрию только для оконного состояния, перед входом выводит приложение из widget-режима и обновляет tooltip после `WindowStateChange`. Изолированный smoke-тест подтвердил переход `widget → fullscreen` и возврат в window без сохранения компактного режима.

Для нижних HUD-панелей сохранена маршрутизация по полной прямоугольной ячейке; отдельный Qt smoke-тест кликнул по краю ячейки вне исходного `QToolButton` и получил действие `OUT` (`WIDGET_EDGE_CELL_CLICK=PASS`). Это подтверждает event path, но не заменяет ручную проверку мышью на реальном экране.

Проверки текущего изменения: `py_compile` — PASS; `git diff --check` — PASS; полный backend-набор с `-W error::ResourceWarning` — **72/72 PASS**; UI перезапущен на изолированном backend `127.0.0.1:18081`, основной пользовательский backend и данные не затрагивались.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено поведение существующего UI и переходов режимов; дерево файлов не менялось.

Реестр `docs/runtime/bug_registry/JARVIS_RUNTIME_BUG_REGISTRY.md` дополнен записями `PH4-UI-003` (переход устройств из widget), `PH4-UI-004` (fullscreen/window state) и `PH4-UI-005` (полная ячейка HUD). Первые две подтверждены Qt smoke-тестами; для `PH4-UI-005` физическая ручная проверка мышью остаётся открытой.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: обновлён существующий bug registry и зафиксирован его статус; структура компонентов и файлов не менялась.

## Phase 4 — expanded widget HUD cells — 2026-11-15

Владелец вручную подтвердил приёмку двух исправлений: переход «Устройства и возможности» из widget-режима и fullscreen/window. Для третьей проблемы подтверждено улучшение, но требуется ещё меньше точности при наведении на нижние иконки.

Нижние HUD-кнопки расширены с `68x56` до `84x68`; anchor offsets изменены с `14/12` на `22/18`, поэтому визуальный центр, сохранённые координаты и внешний рисунок не меняются. В обычном widget-режиме application-level press routing теперь выбирает ближайшую нижнюю ячейку до Qt child hit-test; это предотвращает выбор соседней кнопки только из-за z-order перекрывающихся контейнеров. TECH-A и START защищены от перехвата. Режим `--calibrate-panels` сохраняет drag-поведение.

Изолированный Qt smoke-тест кликнул по точке `45x35` от центра, находящейся вне старого `68x56` контейнера, и получил `OUT`; фактический размер проверен как `84x68`. Физическая ручная проверка новой версии после перезапуска UI ещё ожидается.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено поведение и размер невидимых UI-hitbox существующих HUD-компонентов; структура файлов не менялась.

## Phase 4 — isolated warm Ollama text acceptance — 2026-11-15

На изолированном backend `127.0.0.1:18081` выполнен один неизвестный текстовый вопрос с тестовым `chat_id=phase4_text_acceptance_20261115`. Ответ получен за `2.936 s`; в изолированной истории после запроса ровно одна новая пара `user,assistant`, без дублирования. Runtime-события подтверждают последовательность `planner → executor → critic → turn.completed`, а `ollama ps` показывает `qwen3:8b`, загруженную с `Forever`.

Это закрывает текущую проверку тёплого текстового пути и не доказывает голосовой human speech → STT → Ollama → Fish playback; голосовой end-to-end остаётся отдельным acceptance-критерием.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: зафиксирован runtime-результат существующего маршрута без изменения структуры или назначения компонентов.

После расширения HUD-hitbox повторно выполнен полный backend-набор: **72/72 PASS** с `-W error::ResourceWarning`. Изолированный backend `/health` отвечает и сообщает `ollama=true`; UI-процесс `Jarvis — состояние` остаётся отвечающим. `git diff --check` не выявил ошибок (только стандартное предупреждение Git о нормализации CRLF для HANDOFF).

## Phase 4 — voice route timing diagnostics — 2026-11-15

Проверен фактический маршрут последней живой фразы `что нового`: она распознана через `vosk-silero`, получила локальный ответ из Knowledge/локального response layer и не обращалась к `qwen3:8b`. В тестовой изолированной истории между пользовательской и ответной записью было около 3 секунд. Это не является задержкой Ollama; интервал включает завершение речевого сегмента Silero VAD, передачу аудио в Vosk и обработку ответа. Последующее озвучивание выполняется очередью выбранного Fish Audio профиля.

В `backend/services/voice_runtime.py` добавлена безопасная диагностическая метрика `last_turn_metrics`: источник маршрута (`knowledge`/`ollama`), время локального поиска, время ACK, время модели и момент постановки текста в TTS-очередь. Содержимое речи и сырое аудио в метрики не записываются. Это позволяет на следующем живом прогоне отдельно измерить VAD/STT, Knowledge/Ollama и Fish, не меняя маршрут ответа.

Для штатного production-пути `vosk-silero` сокращён порог завершения короткой реплики с 24 до 16 блоков тишины (примерно с 768 до 512 мс). Порог изменён только для выбранного стабильного маршрута; faster-whisper остаётся консервативным диагностическим вариантом. Это изменение требует повторной живой проверки короткой и длинной фразы на Minifuse.

Последний цикл завершился корректно: `enabled=false`, `listening=false`, `conversation_queue_size=0`, активная voice session отсутствует. Одновременно зафиксирован внешний сбой последнего Fish inference (`SSLEOFError`); профиль `fish_jarvis` остаётся выбранным и fallback на другой голос не включался.

Дополнительно исправлена честность статуса Fish: после текущего неудачного inference предыдущий `inference_verified=true` больше не сохраняется. Профиль остаётся выбранным `fish_jarvis`, но `ready/inference_verified` сбрасываются до следующего успешного запроса; автоматического перехода на XTTS нет.

Проверка внешнего endpoint показала: DNS/TCP `api.fish.audio:443` доступны, обычный HTTPS GET отвечает Cloudflare `404`, но POST `/v1/tts` из текущей Windows-среды завершается `SSLEOFError`. Для защиты latency timeout Fish ограничен отдельным `JARVIS_FISH_TTS_TIMEOUT` (по умолчанию 20 секунд, допустимо 5–90); другой голос не включается.

После изменения поднят новый изолированный backend на `127.0.0.1:18082` с отдельной SQLite `backend/backups/phase4_metrics_20261115/isolated_state.sqlite3`; старый listener `18081` и UI не перезапускались. `/health` сообщает `ollama=true`, `ollama ps` показывает `qwen3:8b` с `Forever`. Контрольный неизвестный текстовый запрос завершился за 2683 мс и вернул один ответ; это подтверждает тёплый текстовый Ollama-маршрут на новой версии исходников, но не заменяет живой микрофонный прогон.

## Phase 4 — fullscreen sidebar usability — 2026-11-15

Исправлены три небольших дефекта полноэкранного режима. Переключатель больше не вызывает Qt `showFullScreen()`: используется максимизация обычного окна, поэтому Windows Start menu/taskbar не блокируются полноэкранной поверхностью Jarvis. Состояние `_fullscreen_mode` и tooltip синхронизируются также для максимизированного окна.

В максимизированном режиме sidebar расширяет список недавних чатов до 320 px и загружает до 8 неприкреплённых сессий; в обычном режиме сохраняется лимит 3 и прежняя высота. Подпись `© Разработано Tandem Marketing` получила перенос строк, отдельную высоту и ширину 280 px в максимизированном режиме, чтобы текст не обрезался.

Проверка кода и живой UI после перезапуска ещё не выполнены; существующий UI на `18081` намеренно не перезапускался, чтобы не прерывать ручную сессию.

Точечная Qt-проверка новой разметки прошла: `SIDEBAR_FULLSCREEN_LAYOUT=PASS` — максимизированный sidebar получает высоту recent-list `320` и footer width `280`, возврат в обычный режим возвращает `120/240`. `py_compile` для UI и затронутых voice-модулей прошёл, `git diff --check` прошёл с обычными предупреждениями Git о CRLF.

Финальные тесты итерации: целевой `test_tts_routing.py` — 2/2 PASS; STT status и Knowledge TTS regression — 3/3 PASS; полный backend suite из `backend` с `-W error::ResourceWarning` — **73/73 PASS**. Живая проверка нового fullscreen UI, Start menu/taskbar и восьми recent chats остаётся отдельным ручным acceptance.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменены существующие UI/VoiceRuntime-поведения, дерево файлов не менялось; карта DOCX дополнена описанием новых связей и состояний.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено поведение существующего окна и layout sidebar без изменения дерева файлов.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: добавлена диагностическая телеметрия существующего VoiceRuntime без изменения дерева файлов; карту DOCX нужно синхронизировать после проверки структуры документа.

## Phase 4 — top HUD label overlap routing — 2026-11-15

После ручной подстройки подписей выполнена проверка текущих координат widget-профиля. Обнаружен потенциальный конфликт hitbox: `CHAT/AGENTS` и соседние верхние панели частично перекрываются в координатном пространстве 710×710, поэтому обычный Qt z-order мог открыть соседнее действие.

В `frontend/jarvis_ui.py` nearest-center routing распространён на верхние текстовые панели. В обычном widget-режиме клик в перекрывающейся области выбирает ближайший центр, а не последнюю созданную кнопку; калибровочный режим drag не изменён. Текущие координаты, углы и размеры текста пользователя сохранены без изменений.

Qt smoke-тест кликнул в зоне перекрытия `CHAT/AGENTS` и получил действие `CHAT` (`TOP_OVERLAP_ROUTE=PASS`). `py_compile` прошёл. Ручная визуальная проверка после следующего перезапуска UI остаётся желательной для подтверждения фактических границ на экране.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменён routing событий существующих HUD-компонентов без изменения дерева проекта.

## Phase 4 — current state snapshot — 2026-11-15

Последний актуальный статус после UI-правок и полного прогона: fullscreen/sidebar изменения находятся в исходниках; Qt layout smoke и `py_compile` прошли; полный backend suite — **73/73 PASS** с `-W error::ResourceWarning`; целевой Fish status regression — **2/2 PASS**. Новый изолированный backend `18082` подтверждает `/health` и тёплый `qwen3:8b` текстовый маршрут, но старый UI на `18081` не перезапускался.

Открытые acceptance-пункты: ручная проверка Start menu/taskbar в новом maximized режиме, визуальная проверка 8 recent chats и полного footer, живой голосовой unknown-question через Ollama с `last_turn_metrics`, стабильный Fish inference и подтверждение слышимого playback. Эти пункты не объявлены PASS.

Владелец разрешил не выполнять ручные проверки UI и субъективное подтверждение слышимого звука в текущем проходе. Поэтому они остаются `SKIPPED/NOT TESTED`, а не `PASS`. Независимые технические ограничения также остаются открытыми: последний live Fish inference завершился сетевым `SSLEOFError`; реальный voice → Ollama → Fish цикл после новых метрик не повторён; Google OAuth и физический production data cutover не заявляются завершёнными.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: это актуальный консолидированный снимок после изменений; дерево файлов не менялось, карта DOCX синхронизирована.

### Phase 4 final technical pass — Fish transport bound — 2026-11-15

Fish transport diagnostics: `api.fish.audio:443` reachable, HTTPS GET succeeds with Cloudflare `404`, but POST `/v1/tts` fails during TLS handshake with `SSLEOFError` in the current Windows environment. `VoiceModelManager` now bounds Fish request timeout through `JARVIS_FISH_TTS_TIMEOUT` (default 20 seconds, clamped 5–90), clears stale readiness after a failed inference, and never switches from selected `fish_jarvis` to XTTS.

Post-change verification: `py_compile` PASS; `git diff --check` PASS; full backend suite **73/73 PASS** with `-W error::ResourceWarning`; DOCX ZIP integrity PASS. Manual UI and audible playback checks remain intentionally `SKIPPED/NOT TESTED` by owner. The goal therefore remains technically partial rather than falsely complete.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: обновлена логика Fish transport/status и зафиксирована внешняя TLS-зависимость; структура проекта не менялась.

## Phase 4 — current Bible migration clarification — 2026-11-15

Актуальное состояние Knowledge Library уточнено по `data/Bible/index/physical_manifest.json` и исходникам мигратора. Выполнена физическая **copy-only staging и runtime cutover**: 5833 исходных файлов обработаны, 5832 уникальных канонических файла находятся в `data/Bible`, один точный SHA-256-дубликат объединён ссылкой canonical path. `originals_preserved=true`; исходные `data/offline_knowledge`, `data/knowledge3` и `data/voice_responses` не удалены.

Все основные runtime search/index/path adapters используют `data/Bible`, а старые roots остаются read-only/legacy/rollback-источниками для аудита и отката. Поэтому формулировка «полностью мигрирована» корректна только для активного runtime cutover; финальное физическое удаление или архивирование старых roots не выполнено и не заявляется завершённым.

Полный backend regression после последнего изменения: **74/74 PASS**, включая новый Fish timeout regression.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: уточнён фактический статус Knowledge/Bible migration и синхронизирована карта проекта.

## Phase 4 — Bible runtime state cutover — 2026-11-15

Аудит после физического copy-only staging выявил остаточные активные записи в legacy-каталоги. Исправлено: `LocalResponseService.selection_state`, `KnowledgeSearchService.variant_selection_state`, `VoiceProductionService.sessions`, `ProgrammingMentorService.progress` и `DawControlService` snapshots теперь принадлежат `data/Bible/index/runtime`. При отсутствии канонического state-файла старый legacy-файл читается только как fallback; новые записи в legacy roots не выполняются. Исходные state-файлы не удалялись.

Добавлен `backend/tests/test_bible_runtime_paths.py`; targeted test PASS. Полный набор после этой правки ещё должен быть повторён.

Полный набор после правки выполнен: **75/75 PASS** с `-W error::ResourceWarning`; `py_compile` и `git diff --check` — PASS. Это подтверждает, что новые Bible-owned runtime state paths не ломают существующие сервисы.

### Documentation Update

- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменены фактические storage/runtime-связи Knowledge/Bible без добавления нового runtime-компонента.
## Phase 4 — Bible human-facing catalog and physical-state clarification — 2026-11-15

Проверка по запросу владельца подтвердила: прежняя миграция была `copy-only`. Поэтому три исходных корня (`data/offline_knowledge`, `data/knowledge3`, `data/voice_responses`) и зеркальные source-папки внутри `data/Bible/materials` и `data/Bible/audio` всё ещё существуют. Это сохранение для rollback, а не доказательство полностью приведённой в порядок физической библиотеки.

Добавлен фактический единый каталог `data/Bible/index/library_catalog.json` и тематические представления `data/Bible/knowledge/*`. Индекс построен из канонических Bible-копий и содержит 727 записей: Computer/CPU и IT, Audio, Music, Science, History, Practical, Stories, Responses, Programming, Psychology и Literature. Добавлен генератор `backend/knowledge/build_bible_catalog.py`; он не удаляет и не перезаписывает исходные материалы и сохраняет `source_of_truth` в одном каталоге.

Проверки: генератор выполнен; JSON-каталог валиден; созданные доменные views присутствуют. Полное физическое архивирование source-зеркал пока не заявляется завершённым: перед ним требуется отдельная проверка всех активных генераторов, ссылок на WAV и runtime path resolver, затем обратимое перемещение в архив с контрольной сверкой SHA-256.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлены генератор единого Bible-каталога, `library_catalog.json`, `domain_map.json` и тематические каталоги `data/Bible/knowledge/*`.
## Phase 4 — Bible domain catalog and consolidation gate — 2026-11-15

По запросу владельца подтверждена причина старых папок: предыдущая стадия была copy-only. Создан единый человеческий каталог `data/Bible/index/library_catalog.json` с 727 фактическими записями и тематическими views `data/Bible/knowledge/*`: Computer, Audio, Music, Science, History, Practical, Stories, Responses, Programming, Psychology и Literature. Добавлен `data/Bible/README.md` с правилами единой точки входа.

Подготовлен обратимый мигратор `backend/knowledge/apply_bible_physical_consolidation.py`. Его проверка SHA-256 по 5 833 каноническим файлам прошла; план содержит 9 перемещений: три legacy source roots в `data/archive` и шесть зеркал Bible в `Bible/sources`/`Bible/audio/library`/`Bible/audio/responses`. Мигратор не удаляет данные, пишет журнал перемещений и обновляет physical manifest/catalog после применения.

Физическое применение намеренно не выполнено в этом окне: сейчас работают ранее запущенные backend `18081` и UI `--calibrate-panels --fullscreen`; их остановка запрещена. Поэтому текущий статус — `READY_TO_APPLY`, а не `PHYSICALLY_CONSOLIDATED`. После штатного закрытия этих экземпляров мигратор нужно запускать сначала без `--apply`, затем с `--apply`, после чего перезапустить актуальный backend и выполнить runtime/integrity smoke.

Проверки: `test_bible_physical_consolidation.py` — 1/1 PASS; полный backend suite до добавления этого gate — 75/75 PASS с `-W error::ResourceWarning`; JSON catalog и DOCX ZIP — PASS.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлены единый каталог Bible, README, migration gate, тест и новые активные связи между источниками и доменными views.
## Phase 4 — Bible consolidation gate regression update — 2026-11-15

После добавления переходного resolver для `materials` → `sources` адресные Bible-тесты прошли 2/2, полный backend regression suite прошёл **76/76 PASS** с `-W error::ResourceWarning`. `git diff --check` не выявил ошибок форматирования.

Физическое применение мигратора всё ещё не выполнялось, потому что в системе остаются ранее запущенные `uvicorn` на `18081` и UI `--calibrate-panels --fullscreen`; они не были остановлены. Это единственный текущий операционный gate для удаления видимых source-зеркал. Все данные остаются сохранены, а операция обратима через журнал `physical_consolidation.json` после запуска.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: обновлены тестовая доказательная база и статус физической консолидации.
## Phase 4 — Bible migration gate path rewrite hardening — 2026-11-15

Усилен `backend/knowledge/apply_bible_physical_consolidation.py`: при применении он теперь переписывает пути не только в `physical_manifest.json` и source JSON, но и в едином `data/Bible/index/library_catalog.json`. Это закрывает риск устаревших ссылок в пользовательской навигации после перемещения. `py_compile` и dry-run SHA-256 проверки прошли; план по-прежнему 9 обратимых перемещений, физическое применение ожидает закрытия активного backend `18081`.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**

## Phase 4 — Bible maintenance freeze by owner — 2026-11-16

По прямому указанию владельца дальнейшие изменения `data/Bible`, архивов исходных материалов, индексов, каталогов, генераторов, миграций и связанных Knowledge-путей приостановлены. Библиотека наполняется и упорядочивается владельцем вручную. До отдельного возобновления этой работы Codex не изменяет Bible/Knowledge и не удаляет старые источники.

Независимые задачи Jarvis можно продолжать только в областях, не затрагивающих библиотеку: UI, runtime, voice, launcher, backend-контракты, storage harness и документация состояния.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: зафиксировано ограничение работ; дерево и архитектура не изменялись.

## Phase 4 — восстановление контекста голосового диалога по chat_id — 2026-11-16

Исправлена подтверждённая проблема, из-за которой голосовые уточняющие вопросы могли выполняться без предыдущих реплик после перезапуска/смены voice-сессии. Причина была в том, что `VoiceRuntime` держал историю только в памяти и при новом `chat_id` очищал её без загрузки сообщений выбранного чата.

Теперь `VoiceRuntime` при старте и переключении voice-сессии загружает последние сообщения из общего `ChatStore`, ограничивает их безопасным окном и не переносит историю между чатами. Prompt Ollama дополнен явным требованием сохранять тему при уточняющих вопросах. Bible и её ручное содержимое не изменялись.

Проверки: новые изолированные сценарии восстановления и отсутствия утечки контекста; `test_voice_runtime_isolated` — **10/10 PASS**. Полный backend suite и живой разговор после правки требуют следующего запуска; UI пока закрыт по просьбе владельца.

Изменены:
- `backend/services/voice_runtime.py`
- `backend/tests/test_voice_runtime_isolated.py`
- `docs/runtime/bug_registry/JARVIS_RUNTIME_BUG_REGISTRY.md`
- `docs/project_map/JARVIS_PROJECT_TREE.txt`
- `docs/project_map/JARVIS_PROJECT_MAP.docx`
- `docs/HANDOFF_ASSIST.md`

Архитектурная связь: voice context теперь следует за `VoiceSessionManager.active.chat_id` и читает историю через `ChatStore`; новый backend или второй storage не добавлялись. Следующий шаг — поднять task-owned backend/UI после завершения исправлений и провести ручной диалог из двух-трёх связанных реплик.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка; визуальный render требует отсутствующий `soffice.exe`)
- PROJECT TREE TXT: **UPDATED**
- Причина: изменились фактическая связь VoiceRuntime → VoiceSessionManager → ChatStore и поведение контекстного prompt.

## Phase 4 — акцентное выделение активного чата — 2026-11-16

По запросу владельца UI теперь явно выделяет чат, соответствующий `current_chat_id`: карточка получает акцентный фон и рамку, цвет и жирность названия. Состояние синхронизируется для закреплённого и недавнего списков при загрузке, выборе чата, открытии истории и создании нового черновика. Сохранение сообщений и API не менялись.

Проверено: frontend contract suite — **10/10 PASS**; `py_compile frontend/jarvis_ui.py` — PASS. Живой визуальный retest будет выполнен после запуска UI вместе с backend.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка; визуальный render требует отсутствующий `soffice.exe`)
- PROJECT TREE TXT: **UPDATED**
- Причина: изменилось фактическое поведение UI-карточек и связь `current_chat_id` → визуальное состояние списка.

## Phase 4 — непрозрачное подтверждение удаления чата — 2026-11-16

Исправлен визуальный баг подтверждения удаления чата. Причина была в `WA_TranslucentBackground=True` у frameless `QDialog`: фон основного окна и список чатов просвечивали через модальное окно. Диалог теперь принудительно непрозрачный (`#12151c`) с явной заливкой и границей; API и логика удаления не изменялись.

Проверено: frontend contract suite — **11/11 PASS**; `py_compile frontend/jarvis_ui.py` — PASS. Визуальная проверка после перезапуска UI ещё ожидает ручного открытия меню удаления.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка; визуальный render требует отсутствующий `soffice.exe`)
- PROJECT TREE TXT: **UPDATED**
- Причина: изменилось фактическое визуальное поведение UI-модального окна.

## Phase 4 — устранение блокирующего перебора камер при старте UI — 2026-11-16

Устранён лишний тяжёлый шаг запуска: `frontend/jarvis_ui.py` больше не открывает синхронно шесть DirectShow-индексов при построении страницы настроек. Это вызывало задержку появления HUD и повторяющиеся ошибки OpenCV на недоступных устройствах. Теперь сохраняемый индекс камеры отображается сразу, а реальная проверка выполняется только по запросу через capability/snapshot путь.

Проверено: frontend suite — **12/12 PASS**; `py_compile frontend/jarvis_ui.py` — PASS. Live-перезапуск с замером времени старта ещё требуется.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка; визуальный render требует отсутствующий `soffice.exe`)
- PROJECT TREE TXT: **UPDATED**
- Причина: изменился критический путь запуска UI и фактическая связь настроек камеры с runtime-проверкой устройств.

## Phase 4 — контекстное уточнение о сне — 2026-11-16

Исправлен воспроизведённый сценарий: после «Ты хочешь спать?» вопрос «Почему ты не спишь?» больше не отправляется в Ollama и не получает шаблонный ответ. `ConversationResolver` теперь возвращает короткое тематическое объяснение с `context_used=true`.

Проверено: `test_conversation_resolver` — **6/6 PASS**; `py_compile` — PASS. Живой повтор через микрофон после перезапуска UI ещё требуется.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка; визуальный render требует отсутствующий `soffice.exe`)
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**
- Причина: изменился активный маршрут ConversationResolver, без добавления файлов или папок.

## Phase 4 — общий якорь темы для модельных follow-up — 2026-11-16

Модельный маршрут теперь глобально получает последнюю тему выбранного чата и ограниченную историю, поэтому уточняющие реплики по любым темам продолжают текущий разговор. В prompt добавлено правило: если контекста недостаточно для надёжного ответа, Jarvis должен задать один короткий естественный уточняющий вопрос по теме, а не гадать и не переключаться на общий шаблон. Это относится к любым темам, не только к диалогу о сне.

Тесты: `test_voice_knowledge_tts` **2/2 PASS**, полный backend suite **94/94 PASS** с `-W error::ResourceWarning`, frontend suite **12/12 PASS**, `git diff --check` PASS. Живой многошаговый голосовой тест после перезапуска требует ручных реплик пользователя.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменилось поведение модельного prompt и контекстная связь, но дерево файлов не изменилось.

## Git checkpoint — 2026-11-16

По запросу владельца текущее состояние исходников, тестов и документации сохранено локальным коммитом `27df757` (`chore: checkpoint Jarvis Phase 4 stabilization`). Push не выполнялся. В коммит вошли 259 файлов; `data/Bible` и `data/archive` намеренно не включались из-за ручного freeze библиотеки и большого объёма пользовательских данных. Эти каталоги сохранены локально без удаления или перезаписи.

Уточнён общий механизм контекста, а не только сценарий сна. Перед модельным ответом `VoiceRuntime` теперь передаёт последние bounded-реплики и явно выделяет последнюю пользовательскую тему. Prompt требует сначала связать текущий вопрос с предыдущей репликой и продолжать её, если это уточнение. Это применяется к любым темам; локальные быстрые правила остаются оптимизацией для коротких известных сценариев.

Проверено: `test_voice_knowledge_tts` — **2/2 PASS**; `py_compile` — PASS. Полный backend suite и живой multi-turn voice retest после перезапуска ещё требуются.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка; визуальный render требует отсутствующий `soffice.exe`)
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**
- Причина: изменился общий маршрут VoiceRuntime → Ollama prompt, без изменения дерева файлов.

## Phase 4 — текущая фиксация голосовых исправлений — 2026-11-16

Закрыты подтверждённые программные причины текущих жалоб: для `что нового` подключены десять Fish WAV `news_01.wav`–`news_10.wav`; короткие `wake-word + greeting` варианты возвращают `Да сэр.wav`; вопрос `ты хороший` обслуживается локальным `ConversationResolver`; голосовая команда погоды использует OpenWeather и настроенный город вместо открытия Yandex. Bible и пользовательские базы не изменялись.

Тесты: полный backend suite **89/89 PASS**, включая voice runtime **8/8**, ConversationResolver **5/5**, weather route **2/2** и knowledge semantics **15/15**. Live STT accuracy, одиночный wake-word без повторов и слышимое подтверждение новых маршрутов требуют следующего физического запуска после перезапуска приложения; они не объявлены PASS.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка PASS; визуальный render BLOCKED: отсутствует `soffice.exe`)
- PROJECT TREE TXT: **UPDATED**
- Bug Registry: **UPDATED** (`PH4-VOICE-015`–`018`)
- Bible/Knowledge source: **NO CHANGE** по действующему freeze владельца.

## Phase 4 — исправление семантики голоса и голосовой погоды — 2026-11-16

Зафиксированы и исправлены три независимых маршрута. Для `что нового` сохранены десять новых Fish WAV в `backend/voice_engine/sound/cache`, а ошибочная карточка `mood_010` не используется без изменения Bible. Для коротких вариантов `джарвис привет` active voice session теперь всегда выбирает существующий `Да сэр.wav`, а содержательная реплика сохраняет bypass wake-word и идёт в единый resolver. Для `ты хороший` добавлено локальное правило `ConversationResolver`, чтобы не получать нерелевантный ответ Ollama.

Голосовая команда погоды больше не открывает Yandex: `computer_control.open_weather()` получает `WEATHER_CITY` и `OPENWEATHER_API_KEY` из существующей конфигурации и запрашивает OpenWeather. Реальный read-only API smoke вернул HTTP 200 для настроенного города; секреты не выводились. Live точность STT и слышимое подтверждение этих новых маршрутов остаются отдельными ручными gates.

Проверки: `test_voice_runtime_isolated` **8/8 PASS**, `test_conversation_resolver` **5/5 PASS**, `test_weather_command` **2/2 PASS**, `test_knowledge_variations` **15/15 PASS**, полный backend suite **89/89 PASS**, `py_compile` и `git diff --check` — PASS. `JARVIS_RUNTIME_BUG_REGISTRY.md` дополнен `PH4-VOICE-016`–`018`.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка PASS; визуальный render BLOCKED отсутствием LibreOffice)
- PROJECT TREE TXT: **UPDATED**
- Bug Registry: **UPDATED** (`PH4-VOICE-016`–`018`)
- Bible/Knowledge source: **NO CHANGE** по действующему freeze владельца.

## Phase 4 — отдельные ответы на «что нового» — 2026-11-16

Подтверждена причина неправильного ответа: в вручную редактируемой карточке `mood_010` для вопроса «что нового» лежали готовые фразы от «как дела», поэтому Jarvis мог сказать «У меня всё в порядке». Bible не изменялась. В `KnowledgeSearchService` добавлен точный semantic guard для формулировок о новом, а в `VoiceRuntime` подключён отдельный быстрый Fish Audio маршрут с десятью вариантами: `news_01.wav`–`news_10.wav` в `backend/voice_engine/sound/cache`. Эти варианты не вызывают Ollama и выбираются только для точных news-запросов.

Генератор `backend/voice_engine/generate_news_wavs.py` создал **10/10** WAV через профиль `fish_jarvis`; существующие файлы не перезаписывались. Регрессии: `test_voice_runtime_isolated` **8/8 PASS**, `test_knowledge_variations` **15/15 PASS**. `git diff --check` — PASS. Render Project Map через bundled DOCX renderer не выполнен: в окружении отсутствует `soffice.exe`; структурное открытие DOCX — PASS.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED** (структурная проверка PASS; визуальный render BLOCKED отсутствием LibreOffice)
- PROJECT TREE TXT: **UPDATED**
- Bug Registry: **UPDATED** (`PH4-VOICE-015`)
- Bible/Knowledge source: **NO CHANGE** по действующему freeze владельца.

## Phase 4 — live voice wake-word gate correction — 2026-11-16

Во время физической проверки UI/голоса на Minifuse активная voice-сессия виджета несколько раз получила от Vosk transcript `обвес` вместо произнесённого `Jarvis`; из-за точного wake-word gate `_extract_command()` отбрасывал transcript до `ResponseRouter`, поэтому командная логика не запускалась. При этом live `/voice/status` подтвердил `vosk-silero`, активную сессию и выбранный `fish_jarvis` (`ready=true`, `inference_verified=true`).

Исправлено только поведение уже явно запущенной сессии: для `source in {"chat", "widget"}` transcript передаётся дальше без требования повторного wake-word. Пассивный wake-word маршрут сохранён. Это устраняет потерю команды после нажатия START и не добавляет конкурирующий STT.

Проверки:
- адресный `backend.tests.test_voice_runtime_isolated` — **5/5 PASS**;
- реальный перезапуск штатным launcher — окно `Jarvis Assist` найдено, UI показывает `JARVIS слушает...`, кнопка `STOP`;
- live после перезапуска: `last_transcript="джарвис"`, WAV-ответ `Рад вас слышать. Jarvis готов заняться делом.`, `route=knowledge`, `tts_queued_ms=214.4`;
- полный одновременный тест команды `Jarvis, открой браузер` ещё ожидает произнесения пользователем.

Ограничение: внешний screenshot capture для окна снова завершился `window capture timed out`; accessibility-состояние окна получено успешно. При остановке task-owned экземпляра Qt вывел серию `QPainter` предупреждений, поэтому graceful shutdown и повторный визуальный acceptance требуют отдельного наблюдения.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменился активный voice-flow и добавлен regression test.

## Phase 4 — live voice command acceptance and ACK regression correction — 2026-11-16

Первый вариант active-session bypass действительно убирал потерю команд, но ошибочно передавал одиночное распознанное `джарвис` в Knowledge вместо мгновенного `Да сэр.wav`. Это вызвало замеченное владельцем замедление и регрессию стабильного ACK.

Исправление: `_extract_command()` теперь возвращает пустую команду для одиночного wake-word даже внутри `chat/widget`-сессии; `_handle_transcript()` сохраняет прежний быстрый путь `_say_wav("Да сэр.wav")`. Для содержательной фразы активной сессии bypass повторного wake-word сохраняется.

Живой acceptance после перезапуска штатным launcher:
- `Jarvis, открой Яндекс Музыку` → `command`, готовый WAV `Мы подключены и готовы.wav`;
- `Jarvis, ты хочешь спать?` → `knowledge`, «Я не сплю и готов к работе.»;
- `Почему ты такой долгий?` → `knowledge`;
- `Тупой` → `ollama`, `model_ms=1701.6`, ответ «Извините, я не понял. Могу ли я чем-нибудь помочь?»;
- live `/voice/status`: `fish_jarvis`, `ready=true`, `inference_verified=true`, `last_error=""`, voice session active.

Адресный тест после исправления — **5/5 PASS**; `git diff --check` — PASS. Текущий процесс Jarvis оставлен работающим для продолжения ручных тестов.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**
- Причина: исправлен runtime-flow без изменения дерева файлов.

## Phase 4 — Fish Audio transient outage and recovery — 2026-11-16

Свежая live-фраза `подскажи погоду` была распознана и обработана через Ollama (`model_ms=1630.5`), но текущий Fish-запрос получил `SSLEOFError` от `api.fish.audio`; runtime честно показал `ошибка озвучки`, сбросил `ready=false/inference_verified=false` и не включил XTTS.

Однократный прямой повтор через текущий Python 3.11 venv и тот же выбранный профиль `fish_jarvis` успешно выполнил inference: реальный WAV **159788 байт**, время **1994.2 ms**. Секреты и `.env` не изменялись. Это подтверждает временный сетевой сбой провайдера, а не неверный профиль или потерю Fish-маршрута.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: зафиксирован фактический runtime-результат Fish provider и восстановление inference.

## Phase 4 — live Fish recovery confirmed in running Jarvis — 2026-11-16

Следующий живой цикл после временного Fish TLS-сбоя: transcript `папик подключён к тебе` распознан, маршрут `ollama`, ответ получен за `model_ms=1568.4` и `response_ready_ms=1581.3`, `last_error` пустой. В том же работающем backend `/voice/status` теперь показывает `fish_jarvis`, `ready=true`, `inference_verified=true`, `actual_engine=fish_audio_s2_1_pro_free`; voice session остаётся активной.

Это подтверждает восстановление provider в runtime. Факт слышимости именно этого последнего ответа отдельно не заявляется без словесного подтверждения владельца.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **NO CHANGE**

## Phase 4 — Bible и архив оставлены без изменений — 2026-11-16

Владелец подтвердил, что текущая структура `data/Bible` и `data/archive` остаётся как есть. Перемещение, переименование, объединение и очистка папок отложены до отдельного будущего этапа, который владелец выполнит вручную. Codex не выполняет операции с этими каталогами и не считает их текущим блокером для независимых runtime/UI/voice задач.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: зафиксировано решение владельца; структура не изменялась.

## Phase 4 — независимый regression-набор без Knowledge — 2026-11-16

После корректного запуска с `PYTHONPATH=backend` выполнен независимый набор backend/voice/storage/account/launcher и frontend voice-input без Knowledge-тестов: **46/46 PASS** за 1.338 секунды. Проверены Account foundation/persistence, action safety, agent lifecycle, ConversationResolver, CORS, launcher contract, model acknowledgements, provider adapters, storage harness, STT route, Fish TTS routing, VoiceRuntime isolation/lifecycle и свежесть voice status.

Первая попытка запуска из корня без `PYTHONPATH=backend` дала только ошибки импорта тестовых пакетов; исходники не изменялись. Повторный запуск из корректного окружения прошёл полностью. Bible/Knowledge не импортировались и не изменялись.

Рабочая команда запуска этого независимого набора добавлена в `docs/runtime/README.md`, чтобы исключить ложные ImportError при последующих проверках.

При уточнении границы обнаружено, что `test_model_acknowledgements.py` читает WAV из `data/Bible`; он исключён из документированной команды. Строгий Bible-free набор повторно прошёл **44/44 PASS** за 1.250 секунды.

Контроль после прогона: `git diff --check` не выявил ошибок (только стандартные предупреждения о преобразовании LF/CRLF), Python/backend-процессов после тестов не осталось, пользовательские SQLite/DB/WAV в изменениях не появились. Работает только ранее существующий процесс Ollama PID 64536.

Дополнительный smoke-check: `py_compile` успешно проверил 17 актуальных Python-файлов backend/frontend вне `backend/knowledge*` и `data/Bible`. YAML-конфигурация `backend/voice_engine/commands.yaml` намеренно не включалась в Python-компиляцию.

## Phase 4 — sidebar assistant toggle подключён к voice runtime — 2026-11-16

Исправлен подтверждённый UI-дефект: переключатель «Ассистент» в `frontend/jarvis_ui.py` больше не является визуальной заглушкой. Его включение и выключение используют общий START/STOP-контур voice runtime, а `_set_assistant_ui()` синхронизирует положение переключателя с фактическим состоянием runtime вместо безусловного `ON`.

Добавлен `frontend/tests/test_assistant_toggle_contract.py`. Адресная проверка frontend: **7/7 PASS**, включая поведенческую проверку dispatch при смене состояния; `py_compile` UI и теста: **PASS**. При запуске с `-W error::ResourceWarning` тесты также завершились успешно, хотя Qt напечатал завершающее сообщение о 1 uncollectable object без падения теста. Project Map DOCX и TXT обновлены; структурная проверка DOCX: **PASS**. Визуальный DOCX-рендер не выполнен, потому что bundled `soffice.exe` отсутствует в текущем runtime.

Новый пункт `PH4-UI-011` добавлен в `docs/runtime/bug_registry/JARVIS_RUNTIME_BUG_REGISTRY.md` со статусом `FIXED / REGRESSION VERIFIED`; ручная проверка кликом в живом окне остаётся отдельным незакрытым gate.

После расширения поведенческого теста Project Map DOCX дополнен уточнением о результате **7/7 PASS**; структурная проверка DOCX прошла (`300` абзацев). Визуальный рендер по-прежнему недоступен из-за отсутствия bundled `soffice.exe`.

Финальный независимый regression-прогон после UI-изменения: **52/52 PASS** за 1.343 секунды (`44` backend + `8` frontend, `-W error::ResourceWarning`, без Knowledge/Bible). После удаления лишнего импорта PySide6 из AST-контрактного теста весь набор завершается без Qt teardown-сообщения; отдельный прямой импорт UI всё ещё классифицируется как внешний Qt teardown-риск.

В UI добавлена проверка единого настраиваемого `API_ROOT`: в `frontend/jarvis_ui.py` не осталось endpoint-литералов `127.0.0.1:8000/...` вне определения значения по умолчанию. Адресная frontend-проверка после этого расширения: **8/8 PASS**.

Account/OAuth read-only smoke: `backend.account_server.tests.test_google_oauth` — **1 PASS, 3 SKIPPED**. Тесты, требующие PostgreSQL, не запускались без отдельной `ACCOUNT_TEST_DATABASE_URL`; существующий listener не подключался. Google validator подтвердил отклонение неверного issuer и неподтверждённого email.

После smoke-проверки процессов остался только ранее существующий Ollama PID 64536; Python/backend/Account Server процессов, запущенных тестом, нет. `git diff --check` без ошибок; `data/Bible` и `data/archive` не изменялись.

Read-only проверка относительных ссылок в обновлённых runtime-документах: **6/6 путей существуют** (`DOC_LINK_CHECK=PASS`).

Диагностическая проверка обычным `gc.collect()` после импорта `frontend.jarvis_ui` дала `GARBAGE=0`. Большое число объектов появляется только при искусственном `gc.DEBUG_SAVEALL`, поэтому подтверждения утечки Jarvis не получено; сообщение возникает на teardown PySide6/Qt. Chromium/Qt security-флаги и исходники ради его подавления не менялись.

Дополнительный импорт-смоук обновлённого `frontend.jarvis_ui` через проектный Python 3.11: **PASS**. UI-модуль загрузился без ImportError; Bible и `data/archive` не читались и не изменялись.

Bible и `data/archive` в этой работе не изменялись.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменился UI-контракт и добавлен новый frontend-тест.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнена проверка без изменений файловой структуры и архитектуры.

## Phase 4 — контрольный Ollama smoke для быстрого маршрута — 2026-11-16

Read-only проверка локального Ollama выполнена без запуска или остановки процессов: listener `127.0.0.1:11434` принадлежит `ollama.exe`, модель `qwen3:8b` доступна. Контрольный запрос с `think=false`, `keep_alive=10m` и ограничением `num_predict=32` завершился успешно за **571 ms**, вернул осмысленный русский ответ и `done=true`. Это подтверждает готовность модели для быстрого локального fallback; отдельный полный сценарий `ConversationResolver → Ollama → Fish` через тестовый backend ещё требует изолированной интеграционной проверки.

Обычный Fish Audio playback ранее подтверждён отдельным стандартным маршрутом, пользователь подтвердил, что услышал результат.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнена read-only runtime-проверка существующих процессов и маршрута; структура проекта и связи компонентов не изменялись.

## Phase 4 — изолированный Ollama → Fish integration smoke — 2026-11-16

На свободном `127.0.0.1:18083` временно поднят task-owned backend проектным Python 3.11 с отдельной SQLite в `%TEMP%` и без warmup, затем штатно остановлен. Основной порт и пользовательская БД не использовались. Неизвестный вопрос прошёл через backend и сохранил в изолированный `chat_id=phase4-ollama-test` ровно две записи: user + assistant. Ответ занял **2491 ms**. Runtime events подтвердили последовательность `planner → executor → critic → chat`; `/runtime/providers` подтвердил выбранного `ollama` и модель `qwen3:8b`. `ollama ps` показал загруженную `qwen3:8b` с `Forever` keep-alive.

Для текста полученного ответа выполнен реальный Fish Audio inference профиля `fish_jarvis`: **PASS**, 598060 байт, RIFF/WAV. Воспроизведение этого конкретного нового ответа не запускалось, чтобы не создавать неожиданный звук; отдельный стандартный Fish playback ранее был воспроизведён и подтверждён пользователем на слух.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: проверены существующие связи без изменения файловой структуры или архитектуры.

## Phase 4 — полный backend regression suite после runtime smoke — 2026-11-16

Запущен проектный Python 3.11: `python -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' -v`. Результат: **78/78 PASS за 38.286 с**. Проверены в том числе единый каталог Bible, физическая консолидация, ChatStore, ConversationResolver, Ollama adapters/warmup, Fish routing и ошибки статуса, Vosk/Silero route selection, voice lifecycle/ownership, Account foundation, Storage registry, CORS и runtime events. `ResourceWarning` не возник.

После тестов активных task-owned backend-процессов и listener на `18083` не осталось. Пользовательские данные и production-конфигурация не изменялись.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнена регрессионная проверка без изменения кода, структуры или связей.

## Phase 4 — синхронизация RT-009 с фактическим isolated chat acceptance — 2026-11-16

В актуальной верхней таблице `docs/runtime/bug_registry/JARVIS_RUNTIME_BUG_REGISTRY.md` RT-009 переведён из устаревшего `NOT_REPRODUCED` в `PASS / ISOLATED`: POST `/chat` реально выполнен на task-owned `18083` с временной SQLite, `qwen3:8b` и отдельным `chat_id`; сохранены ровно user + assistant. Это не закрывает отдельную проверку живого voice-to-Ollama цикла и не меняет статус UI/GLES-сценариев.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: исправлена только актуальность runtime-реестра; структура и связи проекта не менялись.

## Phase 4 — обновление исторических LLM/voice acceptance формулировок — 2026-11-16

В runtime bug registry синхронизированы детали `PH4-LLM-003` и `PH4-VOICE-009`: указаны актуальные `18083`, 2.491 с для изолированного chat smoke, 571 мс для прямого warm adapter probe и подтверждённый `Forever` keep-alive. Отдельно сохранено ограничение: это не является доказательством полного live microphone → STT → Ollama → Fish цикла; стандартный Fish playback уже подтверждён владельцем на слух.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: скорректированы только фактические статусы и доказательства в runtime registry.

## Phase 4 — изолированный VoiceRuntime → Ollama → Fish inference — 2026-11-16

Временный изолированный harness с `ChatStore` и `VoiceSessionManager` прогнал неизвестный голосовой запрос как synthetic transcript через фактический `VoiceRuntime._respond_conversationally()`. ACK playback был подавлен только в harness, чтобы не создавать неожиданный звук. Маршрут зафиксирован как `ollama`; запрос сохранил ровно `user + assistant` в одном тестовом `chat_id`; `qwen3:8b` сформировала ответ; затем выполнен реальный Fish Audio inference профиля `fish_jarvis` для этого ответа — корректный RIFF, 466988 байт. Метрики: Knowledge 407.7 мс, модель 1768.7 мс, ответ готов за 1782.5 мс; ошибок нет.

Это закрывает техническую связность `VoiceRuntime → Ollama → ChatStore → Fish inference`, но не заменяет реальную речь с микрофона и подтверждение слышимости именно этого нового ответа.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнен изолированный runtime-тест без изменения структуры, данных или production-кода.

## Phase 4 — frontend smoke и UI import/compile check — 2026-11-16

Проверены проектным Python 3.11 модули `frontend/launch_jarvis.py`, `frontend/jarvis_ui.py`, `frontend/chat_composer.py` и `frontend/account_ui.py`: `py_compile` — PASS. Тесты `frontend/tests/test_voice_input.py` запущены напрямую (каталог не является importable package для `unittest discover`, так как в нём нет `__init__.py`): **4/4 PASS** с `-W error::ResourceWarning`. Это подтверждает импорт/компиляцию и контракт voice-input, но не заменяет ручную проверку живого HUD, кликов, Start menu и визуального захвата.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнена проверка без изменения файлов, дерева или связей.

## Phase 4 — попытка безопасной live UI acceptance — 2026-11-16

Проверен список окон Windows: окна Jarvis в текущей пользовательской сессии не обнаружено. Компьютерный инструмент не смог запустить `.py`-launcher как установленное приложение без executable identifier, поэтому живое окно не запускалось через UI-автоматизацию, чужие процессы не останавливались, а визуальный PASS для HUD/fullscreen/widget не заявляется. Статическая проверка launcher/UI и Qt smoke остаются положительными; ручная/live визуальная проверка продолжает числиться `PENDING`.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнена только безопасная read-only проверка окон; структура проекта не менялась.

## Phase 4 — исправлена discoverability frontend-тестов — 2026-11-16

Добавлен `frontend/tests/__init__.py`, после чего штатный `unittest discover` для frontend проходит: **4/4 PASS**. Обновлён `docs/project_map/JARVIS_PROJECT_TREE.txt` и добавлен короткий раздел в `docs/project_map/JARVIS_PROJECT_MAP.docx`; ZIP-структура DOCX проверена. Runtime-код и пользовательские данные не изменялись.

Текущая ориентировочная оценка Phase 4 по проверяемым критериям: **около 78%**. Основные незакрытые блоки: live UI/HUD acceptance, полный реальный microphone → STT → Ollama → Fish playback для неизвестного вопроса, реальный Google OAuth и производственная миграция Storage без пользовательского окна/rollback-приёмки.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен новый файл тестовой инфраструктуры и обновлена карта проекта.

## User direction — Bible work paused — 2026-11-16

Пользователь сообщил, что вручную формирует библиотеку. Все дальнейшие операции с `data/Bible`, архивами, индексами, каталогами знаний и миграционными скриптами приостановлены до отдельного указания. Текущие проверки Bible остановлены; данные не перемещались, не удалялись и не перезаписывались.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: изменено только рабочее ограничение; файловая структура Bible не менялась.

## Phase 4 — Account/Storage read-only smoke при замороженной Bible — 2026-11-16

Bible не затрагивалась. Account Server suite: **10 тестов, 3 PASS, 7 SKIPPED**; пропуски требуют изолированного PostgreSQL или запущенного local Account API и не объявляются PASS. Email provider и Google validator локальные проверки прошли. Импорты `account` и `account_server` — PASS. `StoragePaths` подтвердил отдельные логические пути `jarvis_state.sqlite3`, `jarvis.sqlite3`, `account_state.sqlite3` и `filesystem_index.db`; миграции и production БД не запускались.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: выполнены только read-only/import-тесты, структура и данные не менялись.

## Phase 4 — read-only inventory локальных хранилищ — 2026-11-16

Без записи и миграций повторно проверены локальные базы: `jarvis_state.sqlite3` (chat messages/sessions/attachments/reactions), `jarvis.sqlite3` (request state), `account_state.sqlite3` (identity/device/outbox/sync metadata) и `filesystem_index.db` (специализированный filesystem index). Схемы и наличие таблиц читаются корректно; специализированный индекс не объединялся. Bible не затрагивалась. Production данные не изменялись.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: только read-only inventory существующих Storage путей.

## Phase 4 — SQLite backup/rollback gate на текущих хранилищах — 2026-11-16

Запущен `backend/scripts/storage_migration_harness.py --source-root .` из проектного venv. Harness использовал SQLite online backup API, не писал в источники, создал временные копии и rollback-копии для четырёх зарегистрированных хранилищ: `chat_state`, `request_history`, `account_state`, `filesystem_index`. Все четыре копии прошли `PRAGMA integrity_check` и проверку логического hash; временный каталог удалён самим harness после завершения. Bible не читалась и не изменялась.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: проверен существующий reversible Storage harness без изменения дерева и данных.

## Phase 4 — адресная регрессия независимых компонентов — 2026-11-16

Без тестов Bible выполнен адресный набор: Account foundation/persistent **9/9 PASS**, Storage registry **2/2 PASS**, provider adapters **10/10 PASS**, VoiceRuntime isolated/lifecycle **5/5 PASS**, Fish TTS routing **4/4 PASS**, ChatStore **3/3 PASS**, CORS **1/1 PASS**. Все семь групп завершились кодом 0 с `ResourceWarning` как ошибкой. Bible-каталоги и индексы не импортировались и не изменялись.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: только адресная регрессия независимых компонентов.

## Phase 4 — compile smoke и обнаруженные ошибки замороженного Knowledge-слоя — 2026-11-16

Общий `py_compile` собственных Python-файлов выявил syntax errors в незакоммиченных Knowledge-генераторах: `backend/knowledge3/generate_audio_cards.py:76` и затем `backend/knowledge3/generate_programming_audio.py:34`. Эти файлы не исправлялись и не перезаписывались по прямому указанию пользователя не вмешиваться в Bible/Knowledge Library. После исключения `backend/knowledge/**` и `backend/knowledge3/**` compile smoke остальных **175** runtime-файлов прошёл с кодом 0. Ошибки зафиксированы как внешний участок для последующей ручной обработки владельцем библиотеки.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: обнаружены ошибки в уже существующих незакоммиченных Knowledge-файлах; изменения в них не вносились.

## Phase 4 — read-only проверка backend boundary — 2026-11-16

Вне замороженного Knowledge-слоя подтверждены две отдельные FastAPI-точки: `backend/main.py` — основной локальный Jarvis Backend с `uvicorn` entrypoint, и `backend/account_server/app.py`/`main.py` — отдельный Account Server с PostgreSQL boundary. В основном backend найден один `FastAPI()` и один `uvicorn.run`; Account Server имеет собственный `create_app()`, router и отдельный `uvicorn` entrypoint. Это соответствует принятой границе local backend versus cloud/account infrastructure; объединение процессов не выполнялось.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: read-only архитектурная проверка без изменения кода и данных.

## Phase 4 — launcher contract regression — 2026-11-16

Добавлен `backend/tests/test_launcher_contract.py`. Тесты подтверждают: backend child запускается через текущий `sys.executable`, API endpoint/port остаются конфигурируемыми, а несовместимый listener не завершается через `taskkill`. Результат: **3/3 PASS** с `ResourceWarning` как ошибкой. Обновлены project tree и DOCX technical map; ZIP-структура DOCX проверена.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED**
- PROJECT TREE TXT: **UPDATED**
- Причина: добавлен новый регрессионный тест launcher.

## Phase 4 — read-only security scan CORS/process termination — 2026-11-16

Проверены активные backend/frontend исходники вне замороженного Knowledge-слоя. Wildcard CORS origin не найден: основной backend использует явный loopback/file-origin allow-list; wildcard присутствует только в `allow_headers`, не в origins. Принудительное завершение чужого listener через `taskkill` отсутствует. Единственный `.kill()` находится в launcher cleanup и применяется только к собственному дочернему backend после неудачного запуска.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: read-only security scan, исходники не менялись.

## Phase 4 — Account PostgreSQL boundary оставлен без вмешательства — 2026-11-16

Read-only проверка обнаружила уже работающий контейнер Account Server PostgreSQL на `127.0.0.1:5433`. Процесс не запускался и не останавливался; Account integration tests against this endpoint не выполнялись, поскольку не подтверждена отдельная изолированная test database и выполнение могло бы записать в существующее хранилище. Значения конфигурации и секреты в документацию не копировались.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: только read-only inventory, без подключения к базе и без изменений.

## Phase 4 — Fish Audio status diagnostics corrected — 2026-11-16

Исправлена подтверждённая ошибка в `backend/voice_engine/voice_models.py`: после неудачного Fish inference `status()` мог показывать общий словарь ошибок или сообщение о найденном ключе вместо фактической причины. Теперь выбирается ошибка конкретного профиля, а `ready` остаётся `false` до успешного inference.

Проверка текущего процесса: выбран `fish_jarvis`, `available=true`, `ready=false`, `inference_verified=false`; фактический Fish inference не подменяется XTTS. TTS routing tests: **4/4 PASS**. Внешний TLS/inference blocker остаётся отдельным: статус теперь сообщает его явно, без ложного `ready`.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED CURRENT TURN**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**
- Причина: исправлена runtime-логика голосового статуса и диагностический контракт Fish Audio.

## Phase 4 — Fish Audio real inference re-verified — 2026-11-16

Выполнен один короткий реальный inference через выбранный профиль `fish_jarvis` без XTTS fallback и без записи пользовательского текста в лог. Результат: **PASS**, получен WAV с заголовком `RIFF`, размер **200748 байт**; после запроса `available=true`, `ready=true`, `inference_verified=true`, `actual_engine=fish_audio_s2_1_pro_free`.

Предыдущий TLS-сбой не воспроизвёлся в текущем процессе и не подтверждает внутреннюю ошибку маршрутизации. Фактическое слышимое воспроизведение через пользовательское устройство всё ещё требует ручного подтверждения; этот inference не выдаётся за доказательство слышимости.

Дополнительная техническая проверка playback PASS: Fish WAV декодирован как mono 44.1 kHz, `sd.play` стартовал, `sd.wait` завершился, затем `sd.stop` подтвердил освобождение устройства. Физическая слышимость человеком не подтверждалась автоматически.

Синхронизирован верхний runtime bug registry: исторические RT-005/RT-006 больше не помечены как полностью BLOCKED; Fish inference/playback теперь подтверждены. Открытыми оставлены HUD screenshot/GLES3 acceptance, изолированный UI repeat, полный live spoken STT acceptance и внешний Google OAuth.

Уточнение: RT-005 и RT32-004 получили статус `PASS / BASELINE`: ранее подтверждённая пользовательская фраза `хочешь спать` реально прошла через Minifuse → Silero VAD → Vosk → ConversationResolver и была сохранена в изолированном chat. Полный multi-turn voice → Ollama сценарий по-прежнему не объявлен PASS.

Ручная acceptance-проверка владельца выполнена 16.11.2026: пользователь подтвердил, что услышал повтор штатного маршрута `fish_jarvis → Fish Audio → playback`. Выполнен вызов `voice_engine.tts.speak(..., model_id="fish_jarvis")`, процесс завершился `playback=completed`. Fish voice/playback acceptance теперь **PASS**.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED CURRENT TURN**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**

## Phase 4 — Bible user view finalized and runtime paths repaired — 2026-11-15

`data/Bible/library` is the sole user-facing library. Categories are now `CPU` (52), `Computer` (384), `Audio`, `Music`, `Responses` (246), `Literature` and `Psychology`. The generated `General` view was removed from the active view because its records are now classified into their actual categories.

The internal provenance tree remains only at `data/Bible/.internal`; no knowledge material or WAV was deleted. Active generators, `KnowledgeIndexService`, `KnowledgeSearchService`, and `knowledge3/bible_paths.py` now write/read the internal canonical locations instead of recreating `Bible/sources` or `Bible/audio/...`.

The manifest fingerprints were refreshed after path metadata updates: 5,833 records verified. Tests: Bible unittest **3/3 PASS**, knowledge variations **14/14 PASS**, full backend unittest **78/78 PASS**. `git diff --check` has no errors; only existing LF/CRLF warnings remain.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменены пользовательская структура Bible, классификация категорий и активные генераторы/пути runtime.

## Phase 4 — Bible приведена к одной пользовательской библиотеке — 2026-11-15

По запросу владельца устранено визуальное ощущение трёх параллельных библиотек. Материалы физически не дублировались и не удалялись:

- `data/Bible/library/` стал единственной пользовательской точкой входа;
- созданы категории `CPU`, `Computer`, `Audio`, `Music`, `General`, `Literature`, `Psychology`;
- `CPU` отделяет процессоры и компьютерные материалы от общего `Computer`;
- прежние `knowledge3`, `offline_knowledge`, `voice_responses` перемещены в `data/Bible/.internal` как техническое provenance-хранилище;
- старые generated views перенесены в `data/archive/bible_reorganization_20261115/previous_knowledge_views`;
- создан обратимый metadata backup и сохранён исходный `physical_manifest` с обновлёнными canonical paths;
- `build_bible_catalog.py` теперь всегда пересоздаёт именно `Bible/library`, поэтому старые views не вернутся после регенерации;
- единый каталог остался источником истины: **7 250 записей**, runtime resolver подтвердил старые logical aliases.

Проверки:

- `KnowledgeSearchService.catalog()` — 7 250 записей;
- `Bible/library/CPU/catalog.json` — 52 записи;
- `Bible/library/Computer/catalog.json` — 367 записей;
- legacy paths `data/knowledge3/...` и `data/offline_knowledge/...` разрешаются в `Bible/.internal`;
- `py_compile` для resolver, migration script и catalog generator — PASS;
- pytest в текущем `jarvis_env` не запустился: в окружении отсутствует `pytest`; это ограничение среды, а не ошибка приложения.

Ограничение: `.internal` оставлен намеренно для provenance, rollback и совместимости. Пользовательский выбор материалов должен идти через `Bible/library` или API `/knowledge/catalog`, а не через `.internal`.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **UPDATED CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменены физические пути Bible, пользовательская навигация, resolver и генератор каталога.
## Phase 4 — архивирование верхнеуровневых legacy roots — 2026-11-15

Без остановки работающего backend `18081` выполнена независимая обратимая часть миграции: `data/offline_knowledge`, `data/knowledge3` и `data/voice_responses` перемещены в `data/archive/bible_legacy_sources_20261115`. Файлы не удалялись и не перезаписывались. `physical_manifest.json` получил статус `STAGED_WITH_LEGACY_ARCHIVE`, список архива и пустой `legacy_roots_present`.

Канонические source-зеркала внутри `data/Bible/materials` и `data/Bible/audio` пока не перемещены, поскольку живой backend уже держит эти пути; remaining physical move count — 6. Мигратор теперь динамически показывает 6 pending moves, а не ошибочно 9. Верхний `data` больше не содержит три конкурирующих legacy-корня.

Проверки: `test_bible_physical_consolidation.py` — 1/1 PASS; dry-run manifest SHA-256 — PASS; полный backend suite после архивирования — **76/76 PASS** с `-W error::ResourceWarning`.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменилось физическое дерево `data`, архив и статус миграции.
## Phase 4 — archive-era Bible resolver hardening — 2026-11-15

После перемещения верхних legacy roots обнаружено, что пустые каталоги без файловых записей (`coding_projects` и аналогичные) не разрешались через physical manifest и могли откатываться к уже архивированным путям. `backend/services/bible_paths.py` теперь кеширует manifest, индексирует file/prefix aliases и имеет fallback для активных Bible `materials`/`sources` roots. `KnowledgeIndexService` использует тот же resolver.

Проверено: `/knowledge/integrity`-логика возвращает честный `PARTIAL` без ошибок; адресный integrity test — PASS; полный backend suite — **76/76 PASS** с `-W error::ResourceWarning`. Это исправление не перемещает канонические зеркала и не останавливает текущий backend.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменились фактические runtime-связи resolver после архивирования legacy roots.
## Phase 4 — Bible migration archive reuse hardening — 2026-11-15

Мигратор `apply_bible_physical_consolidation.py` теперь повторно использует уже созданный `data/archive/bible_legacy_sources_20261115`, указанный в manifest, вместо создания нового пустого архива. Это сохраняет единый rollback-контур при последующем применении оставшихся шести перемещений. `py_compile` и dry-run (5833 records, 6 pending moves) — PASS.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**
## Phase 4 — актуальный backend smoke после архивирования legacy roots — 2026-11-15

Старый listener `18081` оставлен работающим и не останавливался. Для проверки актуального кода поднят task-owned backend на `127.0.0.1:18082`, затем корректно завершён. Read-only acceptance: `/health` — HTTP 200; `/knowledge/integrity` — `PARTIAL` с 0 errors; `/knowledge/catalog` — 7250 записей; `/knowledge/search?query=Intel 8086` вернул корректную карточку; `/voice/status` подтвердил `fish_jarvis` выбранным по умолчанию; startup warmup `qwen3:8b` выполнен.

Это подтверждает, что новый resolver и архив верхних legacy roots не ломают свежий backend. Старый `18081` продолжает показывать устаревшую реализацию и требует отдельного штатного окна для перезапуска.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**
## Phase 4 — физическая консолидация Bible завершена — 2026-11-15

После подтверждения, что `18081` был task-owned изолированным backend, его дерево было штатно завершено. Применён `backend/knowledge/apply_bible_physical_consolidation.py --apply`: шесть оставшихся зеркал перемещены, пустой `data/Bible/materials` удалён. Активная структура теперь единая:

- `data/Bible/sources/knowledge3`
- `data/Bible/sources/offline_knowledge`
- `data/Bible/sources/voice_responses`
- `data/Bible/audio/library/knowledge3`
- `data/Bible/audio/library/offline_knowledge`
- `data/Bible/audio/responses`

Старые физические корни сохранены только в `data/archive/bible_legacy_sources_20261115`. Manifest имеет статус `PHYSICALLY_CONSOLIDATED`, `originals_preserved=true`, 5 833 исходных файла, 5 832 уникальных canonical-файла, повторный dry-run показывает `planned_moves=0`. `library_catalog.json` пересобран после перемещения; устаревшие JSON/path references в активной Bible устранены.

Свежий backend на `18082` после миграции проверен read-only: `/health` 200, `/knowledge/integrity` `PARTIAL` с 0 errors, roots указывают на `Bible/sources`, каталог 7250 записей, поиск Intel 8086 успешен, `fish_jarvis` выбран по умолчанию, warmup `qwen3:8b` выполнен. Task-owned backend завершён корректно.

Полный backend suite после физической миграции: **76/76 PASS** с `-W error::ResourceWarning`. Пользовательские базы, WAV и архив не удалялись.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: физическое дерево Bible и активные пути полностью изменились.
## Phase 4 — единый каталог Bible выровнен с API — 2026-11-15

Устранено расхождение между навигацией и backend: `build_bible_catalog.py` теперь строит `data/Bible/index/library_catalog.json` непосредственно из `KnowledgeSearchService.catalog()`. Каталог и тематические views содержат одинаковые **7 250 записей**, то есть полный фактический API-реестр, а не только 727 parent-карточек. `test_knowledge_variations.py` — 14/14 PASS; JSON count/structure — PASS.

Это сохраняет один `source_of_truth` для навигации Bible и endpoint `/knowledge/catalog`, при этом физические материалы и аудио остаются в единой consolidated Bible.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **UPDATED**
- Причина: изменился фактический объём единого каталога и генератор domain views.
## Phase 4 — удалена старая ветка генерации сокращённого Bible-каталога — 2026-11-15

После выравнивания каталога удалена неиспользуемая legacy-ветка генератора, которая строила отдельный набор из 727 parent-карточек. `backend/knowledge/build_bible_catalog.py` теперь содержит один активный путь: строит Bible catalog и domain views из `KnowledgeSearchService.catalog()` (7250 записей). `py_compile`, генератор каталога и полный backend suite **76/76 PASS**.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **PENDING CURRENT TURN**
- PROJECT TREE TXT: **NO STRUCTURAL CHANGE**

## Phase 4 — Bible maintenance freeze by owner — 2026-11-16

По прямому указанию владельца дальнейшие изменения `data/Bible`, архивов исходных материалов, индексов, каталогов, генераторов, миграций и связанных Knowledge-путей приостановлены. Библиотека наполняется и упорядочивается владельцем вручную. До отдельного возобновления этой работы Codex не изменяет Bible/Knowledge и не удаляет старые источники.

Независимые задачи Jarvis можно продолжать только в областях, не затрагивающих библиотеку: UI, runtime, voice, launcher, backend-контракты, storage harness и документация состояния.

Documentation Update:
- HANDOFF: **UPDATED**
- PROJECT MAP DOCX: **NO CHANGE**
- PROJECT TREE TXT: **NO CHANGE**
- Причина: зафиксировано ограничение работ; дерево и архитектура не изменялись.
