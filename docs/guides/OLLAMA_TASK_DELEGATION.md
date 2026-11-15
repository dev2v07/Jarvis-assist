# Ollama Task Delegation

## Фактическое состояние

- Локальный Ollama-провайдер подключён через `backend/services/provider_adapters.py` и `backend/services/llm_service.py`.
- Фактически доступна модель `qwen3:8b`; также локально обнаружена `phi3:latest`.
- Настройка модели берётся из `HEL_OLLAMA_MODEL`, runtime-конфигурации или профиля приложения.
- Ollama получает сообщения и system prompt, но не получает права записи файлов, запуска процессов или выполнения команд ОС.
- Отдельного проверяемого web/search pipeline с сохранением source-документов в текущем backend нет. `WebAgent` может открыть/найти страницу, но это не считается источником, пока URL и текст не сохранены и не проверены.

## Разделение ответственности

Codex/основной разработчик выполняет архитектуру, код, интеграцию, файловые операции, тесты и проверку результата. Ollama выполняет анализ переданных документов, конспекты, уроки, FAQ, классификацию и черновики. Реальные действия выполняются только безопасными сервисами Jarvis.

## Контракт

`backend/services/ollama_task_contract.py` задаёт единый envelope задачи: `task_id`, `task_type`, `module`, `goal`, `context`, `source_documents`, `source_urls`, `constraints`, `expected_output_schema`, `language`, `model`, `priority`, `timeout`, `status`.

Результат обязан содержать `task_id`, `status`, `summary`, `content`, `claims`, `source_mapping`, `uncertainties`, `contradictions`, `missing_information` и `needs_human_review`. Невалидный JSON не становится знанием. `confidence` никогда не переводит материал в `VERIFIED` автоматически.

## Статусы

`QUEUED -> RUNNING -> COMPLETED/NEEDS_REVIEW/FAILED/TIMEOUT`. Для знаний отдельно применяются `DISCOVERED`, `SOURCES_COLLECTED`, `OLLAMA_DRAFT`, `NEEDS_REVIEW`, `VERIFIED`, `INDEXED`, `OUTDATED`, `REJECTED`.

## Источники

Правильный pipeline: поиск/получение источника -> сохранение URL и извлечённого текста -> передача Ollama -> source mapping -> проверка URL и утверждений -> запись в общий индекс. Если source pipeline недоступен, результат остаётся черновиком.

## Пилоты и ограничение текущего этапа

Механизм контракта и проверки добавлен. Три сквозных пилота Programming Mentor, Music Production и Personal Music Intelligence пока не объявляются выполненными: в текущем backend нет полноценного source-fetch/index-review маршрута. Массовые задания Ollama и WAV-генерация не запускались.
