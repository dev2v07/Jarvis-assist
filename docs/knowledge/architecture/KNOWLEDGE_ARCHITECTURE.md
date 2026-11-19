# Jarvis Knowledge Architecture 3.0

Новая ветка знаний подключается отдельным реестром `data/knowledge3/module_registry.json` и не изменяет текущие `data/voice_responses` или очередь Fish Audio.

Порядок поиска:

1. Conversational Library.
2. Offline Knowledge Library.
3. Специализированные модули Knowledge 3.0.
4. Ollama для свободного диалога и динамических задач.
5. Внешний поиск только для актуальных сведений.

Каждый материал хранит идентификатор, категорию, тему, варианты формулировок, текст, источники, дату проверки, версию, уровень достоверности, статус и ссылки на аудио.

Неподтверждённые черновики не выдаются runtime. Записи о психологии не являются диагнозом или медицинским назначением. Coding Developer работает только в отдельном проекте или sandbox после подтверждения пользователя.
## Runtime source order and audio linking

Физические хранилища остаются раздельными:

- `data/offline_knowledge/` — проверенные офлайн-материалы и их WAV;
- `data/knowledge3/` — специализированные модули, уроки и метаданные Knowledge 3.0;
- `data/voice_responses/` — существующая библиотека быстрых разговорных ответов.

`KnowledgeSearchService` связывает эти источники логически. Runtime сначала проверяет
готовый `offline_knowledge` ответ и его существующий WAV, затем локальные материалы
Knowledge 3.0 (например, Programming Mentor), и только после этого передаёт запрос
динамическому Ollama/LLM маршруту. Пустые, отсутствующие или незавершённые WAV не
считаются готовым ответом. `/knowledge/answer` используется для проверки этой цепочки.

## SELF_LEARNING chat mode

The existing chat `Самообучение` is bound by its persistent chat ID to the
`SELF_LEARNING` mode. Mode metadata is stored in the same Jarvis state database
as chat sessions, so a rename does not detach it and ordinary chat IDs remain
on the normal planner path.

Learning turns are processed by `backend/services/self_learning_service.py`.
The service requests a structured draft from the configured LLM, records
`user_provided` provenance and uncertainty, deduplicates by a stable content
identifier, and writes to the single Bible source
`data/Bible/.internal/sources/self_learning/catalog.json`. It then uses the
existing `build_bible_catalog.py` generator and `KnowledgeSearchService`; no
second index or search implementation is created. New drafts are explicitly
marked `NEEDS_REVIEW` and are not treated as verified facts. The chat reports
created, updated, duplicate, source, save, and index states to the user.
