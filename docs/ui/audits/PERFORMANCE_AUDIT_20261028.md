# Jarvis Assist — performance audit and voice-input handoff

Дата: 2026-10-28

## Архитектура

- UI: PySide6, `frontend/jarvis_ui.py`, нативный композер в
  `frontend/chat_composer.py` и отдельный QtWebEngine-рендерер
  `frontend/assets/CHAT/chat.html`.
- Backend: FastAPI + asyncio, SQLite через `backend/services/chat_store.py`,
  MessageBus с Planner → Executor → specialist → Critic.
- Модель: нормализованные provider adapters в
  `backend/services/provider_adapters.py`; Ollama теперь поддерживает native
  JSON-lines streaming.
- App Server: локальный JSON-RPC/WebSocket фасад в
  `backend/services/app_server.py` с thread/turn/event lifecycle.
- Iron: отдельный wake-word/command runtime в
  `backend/services/voice_runtime.py`. Кнопка Iron `START` и его функции не
  изменялись. Диктовка композера — отдельный frontend QThread.
- AGENTS.md в текущем репозитории не обнаружен.

## Подтверждённые проблемы и исправления

1. Короткий ответ проходил через искусственный порог в CriticAgent и получал
   служебную приписку. Убрано в `backend/agents/critic_agent.py`.
2. SocialAgent видел только текущую реплику. Передаются последние 12 сообщений
   в порядке диалога; пользовательские инструкции и prompt чата проходят через
   Planner и Executor.
3. Кнопка остановки запроса была отключена после отправки. Теперь она вызывает
   `/chat/cancel/{turn_id}`, скрывает processing bubble и отбрасывает поздний
   результат. Очистка ожидания backend добавлена в `backend/main.py`.
4. Копирование вложений выполнялось внутри event loop. Регистрация и копирование
   вынесены в `asyncio.to_thread`; содержимое файлов не меняется и не удаляется.
5. Большие изображения могли синхронно декодироваться в превью композера.
   Превью создаётся только для файлов до 8 MiB, большие файлы остаются
   доступными как вложения без блокирующего декодирования.
6. При streaming delta повторный Markdown-рендер всего накопленного текста был
   дорогим. Во время потока рендерится только экранированный plain text с
   пакетированием примерно 60 ms; финальный Markdown строится один раз.
7. Добавлен local push-to-record voice input в композер на Vosk. Запись идёт в
   отдельном QThread, использует `backend/voice_engine/model_small`, не создаёт
   постоянный аудиофайл и не отправляет текст автоматически.

## Решения, взятые из Codex

- thread/turn lifecycle и отдельные события вместо неявного состояния;
- delta-события с идентификатором turn и отбрасывание поздних событий после
  отмены или переключения чата;
- явная отмена операции по `turn_id`, а не только скрытие индикатора UI;
- постраничное чтение истории и разделение состояния потока от сохранённого
  transcript;
- стабильные JSON-RPC ошибки и отсутствие секретов/текста переписки в
  диагностических сообщениях.

Полная архитектура Codex не переносилась: Jarvis сохраняет PySide6, FastAPI,
SQLite и MessageBus.

## Изменённые файлы

- `backend/main.py`
- `backend/agents/social_agent.py`
- `backend/services/provider_adapters.py`
- `backend/services/llm_service.py`
- `backend/services/app_server.py`
- `backend/services/chat_store.py` — используется существующий bounded history
- `frontend/jarvis_ui.py`
- `frontend/chat_composer.py`
- `frontend/assets/CHAT/chat.html`
- `frontend/voice_input.py`
- `backend/tests/test_provider_adapters.py`
- `frontend/tests/test_voice_input.py`

## Измерения и проверки

- Synthetic SQLite run: 1000 сообщений; latest page 25 — около 0.026 s,
  page 500 — около 0.70 s на текущем Windows окружении. Это измерение
  загрузки данных, не полное измерение WebEngine DOM.
- Backend tests: `19/19 OK`.
- Voice helper tests: `4/4 OK`.
- `compileall backend frontend`: пройдено.
- JavaScript `node --check` для извлечённого script block: пройдено.
- `/health`: Ollama доступна.
- App Server `initialize`: успешно; capabilities включают threads, turns,
  events и interrupt.
- Доступные аудиоустройства перечисляются через `sounddevice`; русская Vosk
  модель существует.
- UI запускается. Предупреждения `cv2` и GLES3 относятся к необязательному
  video/GPU окружению и не блокируют текстовый чат или диктовку.

## Непроверенные сценарии и риски

- Реальное распознавание русской фразы требует ручной проверки с выбранным
  микрофоном; в автоматическом окружении нельзя подтвердить качество речи,
  пунктуацию и шумоустойчивость без записи пользователя.
- Native Ollama stream проверен mock-тестом и подключён к runtime/UI delta
  каналу; полноценный live turn с моделью не запускался в тестовой переписке,
  чтобы не добавлять искусственные сообщения в пользовательскую историю.
- Прерывание HTTP-запроса к конкретному provider может физически завершиться
  только после его socket timeout: UI и ожидание turn уже отменяются, поздний
  результат отбрасывается. Нативная отмена Ollama transport требует отдельного
  provider-level client.
- Полная виртуализация DOM не включалась: текущая реализация уже грузит историю
  страницами и подгружает старые сообщения при прокрутке. Изменение DOM-модели
  без runtime-профиля создало бы риск поломки поиска, pinned-сообщений и media.

## Ручная проверка Windows

1. Открыть чат, набрать часть текста, поставить курсор в середину и нажать
   микрофон.
2. Произнести русскую фразу, нажать микрофон повторно; убедиться, что текст
   добавился к черновику и не отправился.
3. Во время записи нажать Escape; убедиться, что черновик не изменился.
4. Отправить длинный ответ Ollama и проверить плавное появление текста,
   отсутствие повторного Markdown-рендера и работу отмены кнопкой stop.
5. Переключить чат во время генерации; поздний delta/final не должен попасть
   в другой чат.
6. Проверить Iron `START` отдельно: его wake-word и command runtime должны
   работать ровно как до этой правки.
