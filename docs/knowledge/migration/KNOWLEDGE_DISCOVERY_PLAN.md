# JARVIS Knowledge 3.0 — Phase 0.5
## Knowledge Discovery & Research Plan

Дата: 2026-11-14

## Правила статусов

Регистрация модуля не означает, что он изучен.

`DISCOVERED` — обнаружен объект или направление.  
`RESEARCH_PLANNED` — определены источники и вопросы исследования.  
`RESEARCHED` — собраны материалы, но требуется проверка.  
`INDEXED` — материал занесён в локальный индекс.  
`READY` — материал проверен и разрешён для runtime.  
`DYNAMIC` — сведения требуют периодического обновления.

Текущая Fish Audio-очередь и существующие библиотеки не изменяются. Массовая генерация WAV по Knowledge 3.0 на Phase 0.5 не запускается.

## 1. Фактическое состояние среды

Источник: `data/knowledge3/environment_audit.json`, read-only аудит.

### Уже обнаружено

- Реестр Windows: 294 записи установленного ПО.
- `E:\Музыка` существует; обнаружено 5733 аудиотрека, 37 папок исполнителей и 328 папок альбомов.
- Форматы в коллекции: MP3, FLAC, JPG/PNG, GP5, PDF, CUE и служебные файлы. Оригиналы не изменялись.
- Steinberg: Cubase 13 `13.0.20`, Cubase 15 `15.0.5`, Nuendo 12 `12.0.52`, Steinberg Library Manager `3.2.40`, Generic Lower Latency ASIO Driver `1.0.30`.
- REAPER `7.85`.
- VST2-каталог: 170 файлов, включая `Ample Metal R.dll`, `Omnisphere.dll`, `TSE_808_2.0_x64.dll`; это обнаружение файлов, не подтверждение корректной загрузки в DAW.
- VST3-каталог: 172 файла, включая каталоги Arturia, AudioThing, Bogren Digital, Cymatics, FabFilter, IK Multimedia, Initial Audio, iZotope, Native Instruments, Neural DSP, Nuro Audio, oeksound, Session Loops, Sonic Academy, Toontrack, uJAM и ValhallaDSP.
- Отдельно зарегистрированы: FabFilter Total Bundle `2025.5`, FabFilter Pro-Q 2 `2.2.3`, iZotope Ozone 9 `9.12.0`, iZotope Nectar 3 `3.00`, Native Instruments Guitar Rig 5 `5.1.0.2641`, Guitar Rig 6 `6.2.4`, Kontakt 7 `7.3.2.0`, Kontakt 8 `8.1.0.0`, EZdrummer 3 `3.0.0 CE`, MODO BASS 2 `2.0.2`, Waves Ultimate `2023.07.31`, Addictive Keys `1.1.8`, XO `1.4.5.9`, Cinesamples Drums Of War 3 `1.0.0.1`.
- В реестре также есть AudioThing Effect Bundle, Initial Audio 808 Studio II, Relay и другие записи. Их лицензия и фактическая доступность требуют отдельной проверки.

### Ограничения обнаружения

Инвентаризация не доказывает наличие лицензии, корректную работу плагина, установленную документацию или совместимость версии. Точный список VST3-продуктов нужно получить из bundle metadata и сканирования Cubase, не загружая плагины в проект.

Полный машинно-читаемый список программ, путей, расширений и версий сохранён в `data/knowledge3/environment_audit.json`. В этом плане перечислены все обнаруженные DAW и основные аудиопродукты, а JSON является источником истины для полного перечня 294 записей. Обнаруженные каталоги плагинов: `C:\Program Files\VstPlugins` (1 файл), `C:\Program Files\Steinberg\VstPlugins` (170 файлов, из них 151 DLL), `C:\Program Files\Common Files\VST3` (172 файла, из них 119 VST3). Отсутствующие каталоги x86 VST2 и Steinberg VST3 также зафиксированы, чтобы не считать их установленными.

Следующий шаг для «полного списка VST2/VST3» — read-only извлечение имён продуктов из файлов и bundle metadata. Текущий аудит по расширениям намеренно не объявляет каждый DLL отдельным плагином и не проверяет загрузку в DAW.

## 2. Реестр десяти модулей

| Модуль | Подкатегории | Уже обнаружено | Что изучать дальше | Локально | Обновление | Голосовые материалы | Ollama |
|---|---|---|---|---|---|---|---|
| Guitar Encyclopedia | Cort, Ibanez, Jackson, Fender, Gibson, ESP/LTD, Schecter, Yamaha, PRS, электроника, звукосниматели, модификации | В ТЗ задан приоритет Cort EVL-Z4 и серий; VST/музыкальные файлы обнаружены | Модели, годы, спецификации, схемы, совместимость деталей | Карточки моделей, сравнения, схемы, заметки | Новые модели, цены и наличие | Уроки выбора, диагностика, модификации | Сравнение вариантов и объяснение простым языком |
| Psychology & Emotional Support | КПТ, эмоциональный интеллект, границы, тревога, стресс, выгорание, отношения, конфликты | Требования безопасности и список авторов заданы ТЗ | Источники, упражнения, safety-границы, кризисные сценарии | Проверенные конспекты и дневник сессий с приватностью | Медицинские рекомендации и ресурсы помощи | Поддерживающие диалоги и упражнения | Персонализация диалога без диагнозов |
| Books & Literature | Карнеги, Вербер, Дефо, Жюль Верн, сюжеты, персонажи, идеи | Названы произведения и ограничения авторского права | Библиография, публичное достояние, конспекты | Метаданные, конспекты, легальные тексты | Новые издания и библиография | Обзоры, пересказы, вопросы по книге | Обсуждение и литературный анализ |
| Personal Music Intelligence | локальная коллекция, дискография, жанры, составы, связи, качество | 5733 аудиотрека, 37 папок исполнителей, 328 альбомных папок | ID3/FLAC tags, MusicBrainz IDs, дубликаты, полная дискография | Индекс коллекции, хэши и метаданные | Составы, релизы, актуальные новости | Обзор локального альбома | Сводка и сравнение после индекса |
| Programming Mentor | HTML, PHP, WordPress, Python, React, RN, Flutter, Git, SQL, API, тесты, DevOps | Проект сам написан на Python/FastAPI/PySide6; текущий backend-тестовый набор 25/25 | Учебные планы, задания, проверка кода, sandbox | Курсы, примеры, прогресс | Версии библиотек и API | Пошаговые уроки и разбор ошибок | Генерация объяснений/примеров в sandbox |
| Coding Developer | планирование, генерация, sandbox, тесты, README, preview, rollback | Существующий Jarvis умеет выполнять scoped изменения, но отдельного sandbox ещё нет | Изоляция, подтверждения, diff, тестовый запуск | Проекты, логи, отчёты | Зависимости, CVE, версии | Команды создания проекта и отчёт | Написание и исправление кода |
| Music Production | Cubase, FabFilter, iZotope, Guitar Rig, EZdrummer, MODO BASS, сведение, мастеринг | Найдены Steinberg, REAPER, FabFilter, iZotope, NI, Toontrack и VST-каталоги | Точные версии, manuals, функции, цепочки, лицензии | Справочники, пресеты только с разрешением, анализаторы | Версии плагинов, документация, цены | Уроки EQ/компрессии/мастеринга | Анализ и рекомендации, не выдумывать цепи |
| Voice Production Mentor | запись вокала, редактирование, компинг, tuning, шум, FX, микс | Голосовой runtime и Fish Audio работают; исходные дорожки отдельно не индексировались | Входные файлы, цепочки, безопасные операции, сравнение | Конспекты, проекты-копии, измерения | Версии плагинов и техники | пошаговое объяснение обработки | Разбор ситуации и план действий |
| DAW Control | Cubase MIDI Remote, Generic Remote, key commands, VST3, OSC/IPC, UI automation | Cubase 13/15 и Nuendo обнаружены; способ управления ещё не подтверждён | API, права, undo, проект-копия, видимость изменений | Скрипты, mappings, журналы | API и версии Cubase | команды «открой/покажи/настрой» | Планирование действий, не прямое выполнение |
| Mixing & Mastering Engineer | LUFS, True Peak, RMS, спектр, фаза, стерео, референсы, EQ, comp, limiter | Аудиоинструменты и DAW обнаружены; анализ миксов не проводился | Метрики, reference workflow, недеструктивность, валидация | Измерения и отчёты, копии проектов | стандарты доставки и платформы | обучение по измерениям и корректировкам | интерпретация измерений и рекомендации |

## 3. Предварительный каталог `E:\Музыка`

Сканирование выполняется только для чтения. На Phase 0.5 нужно сохранить два слоя:

1. `LOCAL_COLLECTION` — только то, что физически найдено: путь, размер, расширение, длительность, sample rate, codec, tags, hash и дата сканирования.
2. `FULL_DISCOGRAPHY` — отдельные внешние данные MusicBrainz/Discogs/официальных сайтов. Отсутствующий локальный альбом не является ошибкой и не должен добавляться в коллекцию.

Предварительный каталог уже имеет объём 5733 аудиофайлов, 37 папок исполнителей и 328 папок альбомов. Следующий read-only этап:

- извлечь теги MP3/FLAC;
- нормализовать исполнителя/альбом без переименования файлов;
- вычислить длительность и качество;
- найти дубликаты по hash и акустическому fingerprint;
- сформировать `artists.json`, `albums.json`, `tracks.json` и отчёт об ошибках тегов;
- затем сопоставить исполнителей с MusicBrainz IDs;
- внешнюю дискографию не смешивать с локальной коллекцией.

Для периодического обновления нужны новые релизы, составы, даты и ссылки. Для голосового обучения подходят обзоры имеющихся альбомов, сравнение качества и история исполнителя. Ollama нужна для сводки и диалога после того, как факты пришли из индекса.

## 4. Programming Mentor — карта курсов

Каждый курс должен иметь `уровень → темы → пример → задание → тест → разбор ошибки → прогресс`.

- HTML: структура документа, семантика, формы, мультимедиа, accessibility, SEO, DOM-связка.
- PHP: синтаксис, типы, функции, ООП, PDO, MySQL, REST, auth/session, Composer, безопасность.
- WordPress: темы, плагины, hooks, Gutenberg, CPT, таксономии, REST/WP-CLI, WooCommerce, SEO и performance.
- Python: базовый язык, ООП, async/threading, files/JSON/SQLite/PostgreSQL, requests, FastAPI/Flask, PySide6, tests, packaging, PyInstaller.
- React: ES6/TypeScript, JSX, components, state/hooks, Context, Router, forms, API, Vite/Next, Tailwind, accessibility.
- React Native: navigation, state, storage, permissions, camera/files, API, Expo/Bare, APK.
- Flutter/Dart: Dart, widgets, navigation, Provider/Riverpod/Bloc, API, SQLite, permissions, APK/AAB.
- Общая инженерия: Git/GitHub/Git Flow, Docker, REST/WebSocket, SQL, Redis, SOLID, patterns, MVC/MVVM/Clean, tests, CI/CD, logs, docs.

`CODING MENTOR` работает только с объяснением и учебными заданиями. `CODING DEVELOPER` требует отдельного sandbox, preview diff, резервной точки и подтверждения перед изменением существующего проекта.

Источники: официальная документация языка/фреймворка, MDN, PHP manual, WordPress Developer Resources, Python docs, React docs, React Native docs, Flutter docs, Git docs, Docker docs. Версии и API — динамические. Голосом можно объяснять устойчивые концепции, но актуальные API нужно получать через документацию/поиск.

## 5. Music Production — перечень исследования

### Уже обнаруженные продукты

Cubase 13 `13.0.20`, Cubase 15 `15.0.5`, Nuendo 12 `12.0.52`, REAPER `7.85`; FabFilter Total Bundle `2025.5`, Pro-Q 2 `2.2.3`; Ozone 9 `9.12.0`, Nectar 3 `3.00`, Relay `1.3.0`; Guitar Rig 5 `5.1.0.2641`, Guitar Rig 6 `6.2.4`; Kontakt 7/8; EZdrummer 3 `3.0.0 CE`; MODO BASS 2 `2.0.2`; Waves Ultimate `2023.07.31`; Addictive Keys, XO, AudioThing, Initial Audio и другие VST-каталоги.

### План изучения функций

- FabFilter Pro-Q 3: bands, dynamic EQ, spectrum, mid/side, phase, analyzer, automation.
- Pro-C 2: detector, sidechain, knee, attack/release, styles, lookahead.
- Saturn 2: distortion modes, multiband, modulation, dynamics.
- Pro-L: limiting modes, true peak, oversampling, loudness.
- Ozone 9: EQ, dynamics, exciter, imager, maximizer, metering.
- Nectar 3/R-Vox: vocal chain, gate, compression, de-essing, EQ, level control.
- Guitar Rig 5/6, Neural DSP и TSE: amp/cab/signal-chain concepts; не считать конкретный пресет универсальным.
- EZdrummer, MODO BASS, Kontakt, Addictive Keys/XO: инструменты, MIDI, humanize, routing.

Источники: официальные manuals, help centers, release notes, vendor knowledge bases, Steinberg manuals и VST SDK. Хранить локально можно определения, измерения и собственные конспекты; пресеты и защищённые manuals — только в пределах лицензии. Ollama нужна для объяснения цепи после выбора фактических установленных модулей.

## 6. Cubase 13 — отдельное исследование интеграции

Статус: `DISCOVERED`, но не `READY`.

Кандидаты, которые нужно проверять изолированно:

1. MIDI Remote API и driver scripts в `Documents\Steinberg\Cubase\MIDI Remote\Driver Scripts` — официальный скриптовый путь для контроллеров.
2. Generic Remote и Key Commands — ограниченное управление командами/параметрами.
3. VST3 — интерфейс плагинов, но не автоматический универсальный API управления проектом.
4. UI automation — крайний вариант, только видимые и обратимые действия.
5. Проектные копии, Undo и сохранение промежуточных вариантов.

Нужно проверить: доступность API именно в Cubase 13, чтение дорожек/маршрутизации, изменение параметров, undo, ошибки при закрытом проекте, права доступа и отсутствие фоновых необратимых изменений. Управление нельзя считать реализованным только по наличию Cubase. Официальные ориентиры: [Cubase MIDI Remote API](https://steinbergmedia.github.io/midiremote_api_doc/getting-started/), [Cubase Operation Manual](https://www.steinberg.help/api/khub/documents/T5ttKObCpFWiKd6dZ6c9fw/content), [VST3 SDK](https://github.com/steinbergmedia/vst3sdk).

## 7. Trivium и Arch Enemy

### Trivium — дискографический research set

Проверять по MusicBrainz, официальным/лейбловым страницам и интервью: `Ember to Inferno`, `Ascendancy`, `The Crusade`, `Shogun`, `In Waves`, `Vengeance Falls`, `Silence in the Snow`, `The Sin and the Sentence`, `What the Dead Men Say`, `In the Court of the Dragon`; новые релизы сверять отдельно по дате исследования. Сравнивать состав, продюсера, инженера, гитарный тон, вокал, барабаны, динамику и мастеринг только по подтверждённым материалам. Для продакшн-контекста использовать интервью и credits; например, production credits для `The Sin and the Sentence` доступны в профессиональной дискографии Josh Wilbur.

### Arch Enemy — дискографический research set

Проверять: `Black Earth`, `Stigmata`, `Burning Bridges`, `Wages of Sin`, `Anthems of Rebellion`, `Doomsday Machine`, `Rise of the Tyrant`, `The Root of All Evil`, `Khaos Legions`, `War Eternal`, `Will to Power`, `Deceivers`, `Blood Dynasty`; актуальные релизы и состав сверять перед использованием. Отдельно разделить периоды Johan Liiva, Angela Gossow и последующих составов. Для production analysis использовать официальные видео/credits, MusicBrainz и интервью; не придумывать плагины, кабинеты или цепи.

Источники: [MusicBrainz Trivium](https://musicbrainz.org/artist/1f5ff245-2837-4d4a-a609-e93e544478c3), [MusicBrainz Arch Enemy](https://musicbrainz.org/artist/e631bb92-3e2b-43e3-a2cb-b605e2fb53bd), официальные сайты/лейблы, Bandcamp/credits, интервью музыкантов и инженеров. Локально хранить только метаданные, ссылки и аналитические заметки; аудио не копировать.

## 8. Остальные исследовательские планы

### Guitar Encyclopedia

Начать с Cort EVL-Z4, затем Cort EVL/X/KX, Ibanez GIO/GRG/GRX/RG/S/AZ/ART и Jackson Dinky/Soloist/King V/Rhoads/Kelly/Warrior. Для каждой модели разделить подтверждённые спецификации, версии года, субъективное звучание и совместимые модификации. Источники: manuals, каталоги производителей, сервисные схемы, каталоги деталей и проверенные магазины. Цены и наличие — `DYNAMIC`.

### Psychology

Сначала safety policy: Jarvis не ставит диагнозы, не назначает лечение и предлагает экстренную помощь при риске. Затем evidence map по КПТ, эмоциональной регуляции, границам и отношениям. Источники: учебники/профессиональные организации и клинические рекомендации. Локально — конспекты и упражнения; личные сессии — отдельное приватное хранилище. Ollama отвечает только в рамках безопасного диалога.

### Literature

Для Дефо и Жюля Верна проверить public-domain edition и условия текста. Для Карнеги и Вербера хранить конспекты, анализ и библиографию, но не полные защищённые тексты. Сохранять персонажей, темы, связи и цитатные ограничения. Ollama помогает обсуждать, но не подменяет источник.

### Voice Production Mentor

Собрать локальные учебные карточки по записи, шуму, компингу, редактированию, pitch/timing и вокальной цепи. Привязать к фактически найденным плагинам, но не применять настройки автоматически. Голосовые уроки — короткие шаги, контрольный вопрос и возможность «повтори/верни шаг».

### DAW Control и Mixing/Mastering

Сначала offline-анализ WAV/проектных копий: LUFS, true peak, спектр, фаза, stereo correlation, clipping. Затем read-only анализ Cubase-проекта. Любое изменение — через preview, undo и подтверждение. Автоматический мастеринг и необратимое изменение оригинальных файлов пока `FUTURE`.

## 9. Что можно хранить локально и что обновлять

Локально: нормализованные metadata, source URLs, проверенные конспекты, учебные задания, измерения, индексы коллекции, копии проектов и WAV-ссылки.  
Периодически обновлять: версии программ, плагины, цены/наличие, составы групп, новые альбомы, актуальные API, документацию Cubase и стандарты loudness.  
Через Ollama: объяснение, диалог, сравнение и черновые материалы. Нельзя считать ответ Ollama подтверждением факта без источника или review status.

## 10. Оптимальная последовательность реализации

1. Завершить текущую Offline Fish Audio очередь и отдельно повторить её сетевые ошибки.
2. Зафиксировать read-only каталог `E:\Музыка` с тегами, длительностью и хэшами.
3. Превратить `environment_audit.json` в детальный plugin registry с bundle metadata и версиями.
4. Реализовать общий Knowledge Index и статусы материалов, не смешивая локальную коллекцию с внешней дискографией.
5. Завершить Programming Mentor: курсы, прогресс и безопасные задания.
6. Создать Coding Developer sandbox с preview/diff/rollback.
7. Подготовить Guitar, Literature и Psychology по источникам и safety-проверкам.
8. Подготовить Music Production cards для фактически обнаруженных плагинов.
9. Исследовать Cubase 13 read-only и MIDI Remote prototype.
10. Только после review запускать пакетную Fish Audio генерацию по приоритетным темам.
11. Собирать длинные лекции/истории отдельными очередями, не смешивая их с быстрыми ответами.

## Текущая граница Phase 0.5

На этом этапе выполнены discovery и планирование. Это не означает, что модули изучены или готовы для runtime. Следующий безопасный технический этап — детальный read-only индекс музыки и plugin registry; массовую WAV-генерацию по новому ТЗ запускать только после утверждения текстов и источников.
