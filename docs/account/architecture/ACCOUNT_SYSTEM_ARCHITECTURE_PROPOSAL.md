# Jarvis Account System — утвержденная архитектура Phase 0.5

Статус: дизайн-фриз для Personal Account. Это proposal для будущей реализации; существующий код и API не изменены.

## 1. Зафиксированная цель

Jarvis остается local-first помощником, но получает единый облачный account plane для одного личного аккаунта пользователя и нескольких устройств. Household/team — только будущая совместимая возможность, не часть текущей версии.

```text
Windows / Android / iOS / TV / Auto / Browser client
        -> local runtime: cache + outbox + voice + local AI
        -> HTTPS API: auth + sync + account resources
        -> PostgreSQL + S3-compatible object storage
        -> background worker + email + monitoring + encrypted backups
```

Текущий Windows backend остается execution engine для Ollama, voice, agents и локальных capabilities. Облачный слой не получает произвольные Windows-команды, абсолютные пути или локальные секреты.

## 2. Три класса данных

| Класс | Содержимое | Правило |
|---|---|---|
| Cloud Synced | все выбранные conversations/messages, attachments, archive, favorites, sync metadata, selected preferences, AI conversation records | синхронизируется между авторизованными устройствами |
| Device Only | local models, voice models/WAV cache, local provider keys, device capabilities, local runtime cache/outbox, local-only data | не покидает устройство автоматически |
| Excluded | absolute paths, filesystem indexes, raw microphone recordings, system data, unrelated temporary data, shared knowledge catalog | не импортируется и не синхронизируется account service |

Персональная memory — отдельная категория Cloud Synced только после явного consent. Она не является автоматической частью All Sync.

## 3. Local Mode и Account Mode

Local Mode сохраняет текущую работу без регистрации и сети: локальный chat store, local settings, voice, Ollama and local memory.

Account Mode добавляет account identity, device registration, sessions, encrypted cloud cache и durable outbox. У пользователя есть явное управление sync preferences, cloud AI consent и memory sync consent.

### Local-to-Account import

1. Создать/подключить email account.
2. Зарегистрировать устройство и получить `device_id`.
3. Сделать read-only inventory локальных sessions, messages, attachments, settings и memory.
4. Показать counts и раздельные previews; excluded data явно показать как не импортируемые.
5. Выбрать набор данных и подтвердить импорт.
6. Создать один `import_id`; подготовить manifest с локальными source IDs и SHA-256 для файлов.
7. Загрузить import job через authenticated API; повтор того же `import_id` возвращает прежний результат.
8. Дождаться server confirmation per item/job.
9. Сохранить локальную копию. Удаление локальных данных — отдельное действие и отдельное подтверждение.

Никакого silent merge по содержимому. Сервер сохраняет `source_local_id`/`client_message_id`; повторная отправка не создает duplicate.

## 4. Authentication и authorization

Personal account включает registration, email verification, email/password login, reset, logout, password change, active device/session list and per-device revoke. Passwords — Argon2id. Access token короткоживущий; refresh token opaque, rotating, hashed server-side, с reuse detection and revocation.

Каждый resource query получает `account_id` из validated token. Client-supplied account IDs не являются источником authorization. Device/session context не расширяет права account автоматически.

## 5. Full sync protocol

REST/HTTPS — источник истины для push/pull и CRUD. WebSocket/SSE допускается только как “changes available” hint; после reconnect клиент всегда делает cursor pull.

```text
local mutation
  -> outbox(operation_id, account_id, device_id, entity_id, base_revision)
  -> POST /v1/sync/push
  -> committed | duplicate(previous result) | conflict | rejected
  -> GET /v1/sync/pull?cursor=...
  -> apply ordered changes and advance cursor
```

Message append использует client-generated stable ID. Conversation title/preferences используют optimistic concurrency. Archive/favorite/delete — explicit set operations, не blind toggles. Deletion распространяется tombstone, пока все допустимые offline devices не смогут получить его.

## 6. Вложения

Файл передается только authenticated upload flow, никогда не через local absolute path. Сервер выдает short-lived upload URL или принимает streaming upload; object storage хранит opaque object key.

Проверки до commit:

- allowlist MIME + extension policy;
- size limit per file and per account quota;
- detected MIME не доверяет только client header;
- SHA-256 сравнивается с manifest/client checksum;
- malware/content scan hook;
- attachment status `pending -> accepted` или `rejected`;
- message references accepted attachment ID, а не path.

Проектный default для согласования: 25 MiB/file, 1 GiB/account, 100 files/message. Это не утвержденные финальные лимиты.

Удаление создает tombstone, блокирует выдачу, затем object garbage collection после retention. Account export включает accepted attachments либо manifest по выбранной policy.

## 7. AI Routing Policy

Каждый запрос получает effective policy из device settings + account settings + per-request consent. Default — Local Preferred, Cloud Disabled until enabled.

| Ситуация | Маршрут по умолчанию | Cloud consent | Передаваемые данные |
|---|---|---|---|
| простая команда Windows, device capability, offline knowledge | Local AI/Local tool | не нужен | текст запроса локально |
| обычный чат при доступном Ollama | Local AI | не нужен | локальный context |
| обычный чат без local model, cloud разрешен | Cloud AI | account setting + visible notice | только conversation context, необходимый для ответа |
| cloud disabled/offline | Local fallback или честная ошибка | запрещено | ничего не уходит |
| sensitive category, files, system actions | Local preferred | per-request confirmation if cloud needed | минимизированный redacted payload |
| third-party provider | только allowlisted provider | отдельное provider consent | provider-specific minimized context |

Settings должны позволять: preferred mode `local/cloud/hybrid`, allow cloud processing, allowed categories, allowed third-party providers, send conversation content, cost budget. Перед отправкой за устройство UI/voice must say/show that data leaves the device. Local files, system data, absolute paths and keys не прикладываются автоматически; для файла требуется отдельное explicit attachment consent.

Cost limit, provider unavailable and timeout must fail closed to local/offline fallback, not silently switch to another external provider.

## 8. Server architecture — VPS First

Containerized modular monolith:

- TLS reverse proxy/API edge;
- auth/account/sync modules in one deployable application;
- PostgreSQL;
- S3-compatible object storage;
- background worker for email, imports, export, deletion, scanning and compaction;
- SMTP/email adapter;
- monitoring/logging/health;
- encrypted backup jobs.

Docker Compose is the initial topology. Provider-specific SDKs are hidden behind PostgreSQL/S3/SMTP adapters. Deployment must be portable to a self-owned server by moving volumes, secrets and images—not by rewriting domain data.

## 9. Future platform compatibility

All clients use versioned auth, devices, conversations/messages, sync cursors, preferences, memory consent, attachments and AI policy contracts. Platform-specific actions remain capability-scoped. Household/team expansion later adds membership/roles around `account_id`; it does not change current personal resource IDs or message identity rules.

## 10. First-version security boundary

TLS in transit, server-side encryption at rest, encrypted backups, Argon2id, rotating refresh tokens, OS-protected local credentials, rate limits, strict ownership checks and audit events are required. E2EE is Later: first version does not cryptographically hide synced message content from the server. Data model reserves device public keys/key enrollment fields for a future phase, but no E2EE behavior is implied now.

## 11. Explicit non-goals

Не реализуются сейчас household/team, E2EE, local knowledge replication per account, automatic memory extraction into synced memory, automatic cloud fallback for every request, remote execution of Windows tools, and changes to current `/chat` or local SQLite schema.
