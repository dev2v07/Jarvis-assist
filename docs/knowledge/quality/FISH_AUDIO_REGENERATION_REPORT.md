# Fish Audio regeneration + WAV cleanup + Sleep/Wake

Дата: 2026-11-18. Проект: Jarvis.

## 1. Генерация

- Групп: **6**; ответов: **60**; сгенерировано WAV: **60**; ошибок после повторов: **0**.
- Старых WAV заменено: **21**; новых (ранее без аудио): **39**.
- Все файлы: 44.1 kHz, mono, длительность ≥0.3 c, проверены SoundFile.
- Промежуточные сбои Fish Audio: 10 (SSL/timeout), все повторены успешно. Прогресс сохраняется в staging-манифесте.

## 2. Очистка WAV

- Кандидатов из CSV: **234**.
- Проверены все источники: questions.json, offline/knowledge3 каталоги, library_catalog, physical_manifest (как fingerprint), код.
- Подтверждено и перемещено в карантин: **204**.
- Защищено действующими ссылками: **30** (в т.ч. переозвученные greetings_002/farewell_004).
- Карантин: `data/Bible/.internal/audio/quarantine_20261118/` + `quarantine_manifest.csv` (SHA256, размер, исходный путь).
- Физического удаления нет.

## 3. Sleep/Wake

- Состояния: ACTIVE / SLEEP / WAKING; `status()` отдаёт `mode` и `sleeping`.
- Триггеры сна: прощание (intent `farewell_*`), «Спокойной ночи», «Выключись» (intent off).
- Сон наступает после завершения TTS/WAV; процесс и микрофонный поток остаются живы.
- Пробуждение: «Jarvis», «Jarvis, включись», «Jarvis, привет», «Джарвис …»; wake-фраза не маршрутизируется как команда.
- При пробуждении история и pending-вопрос очищаются; новая сессия.
- ConversationResolver не менялся в части farewell-ответов; цепочки продолжения сохранены.

## 4. Тесты

- Всего: **114/114 OK** (включая 5 новых Sleep/Wake и 9 тестов групп).
- Живой микрофон/динамик не проверялся (нет live-сессии).

## 5. Изменённые компоненты

- `backend/knowledge3/regenerate_conversational_audio.py` (new), `quarantine_conversational_orphans.py` (new).
- `backend/services/voice_runtime.py` (SLEEP/WAKING, wake-фразы, sleep-after-farewell).
- `backend/tests/test_voice_sleep_wake.py` (new), `test_conversational_groups.py` (audio assertion).
- `questions.json`, `physical_manifest.json`, `library_catalog.json` + views; staging/quarantine manifests.
- Остальные категории и их WAV не изменялись (сегодня изменены только 60 файлов шести групп).

## 6. Ограничения

- Fish Audio: только 60 ответов шести групп; остальные категории не переозвучивались.
- Удаление карантина не выполнялось.
- LLM fallback, `/chat`, голос Fish Audio не менялись; git commit/push нет.