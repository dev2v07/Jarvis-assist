# Knowledge Research Pipeline

## Поток данных

`Coordinator -> source retrieval -> source record -> Ollama analysis -> claim/source validation -> review -> shared index`.

Ollama получает только переданный контекст и документы. Внешнее знание модели не считается найденным источником. Утверждения без `source_mapping` остаются `NEEDS_REVIEW`.

## Source record

Минимальная запись источника: `source_id`, `url`, `title`, `author_or_organization`, `published_at`, `retrieved_at`, `source_type`, `extracted_text`, `availability`, `task_id`.

## Индекс

Общий foundation index: `data/knowledge3/index.json`. Локальная музыка: `data/knowledge3/music_catalog.json`. Offline Knowledge: `data/offline_knowledge/catalog.json`. Новые записи должны сохранять `generated_by`, `model_name`, `source_ids`, `source_urls`, `created_at`, `verified_at`, `status` и `version`.

## Безопасность

Ollama не получает произвольный доступ к рабочему дереву, запуску процессов или записи. Код проверяется в sandbox, DAW-действия выполняются только с preview/подтверждением/откатом, а оригинальная `E:\Музыка` индексируется только для чтения.

## Текущий статус

Контракт делегации и общий индекс подготовлены. Source-fetch, claim-level validation и Coordinator queue остаются следующим этапом; до их реализации пилоты нельзя объявлять полностью пройденными.
