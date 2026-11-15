# Account System Phase 2.2 — Google OAuth 2.0

Статус: реализовано в коде, реальная авторизация Google ещё не выполнялась.

## Выбранная архитектура

Windows-клиент использует OAuth 2.0 Authorization Code Flow с PKCE и системным браузером. Клиент получает authorization code, затем передаёт code, PKCE verifier и loopback URI на Account Server. Только Account Server обменивает code на Google tokens с server-only Client Secret.

```text
http://127.0.0.1:8765/
```

Если настроенный порт занят локальным процессом или запрещён Windows, клиент автоматически выбирает свободный loopback-порт только на время текущей OAuth-сессии. В authorization request и token exchange используется один и тот же фактически выбранный URI. Внешняя публикация listener не выполняется.

Перед открытием браузера генерируются одноразовые `state` и PKCE `code_verifier`. После callback клиент проверяет `state`, обменивает authorization code на Google tokens с `code_verifier`, закрывает listener и передаёт только полученный Google ID token на сервер:

```text
POST /api/v1/auth/google/exchange
```

Google access token не используется как Jarvis token. Account Server самостоятельно проверяет подпись и claims ID token через `google-auth`, включая issuer, audience, expiration, `sub` и `email_verified`, после чего выдаёт собственные Jarvis access/refresh tokens.

## Google Cloud настройки

Для Windows-клиента нужен OAuth Client типа **Desktop app** (public client). В Google Cloud Console необходимо разрешить redirect URI:

```text
http://127.0.0.1:8765/
```

Используемые scopes:

```text
openid
email
profile
```

`GOOGLE_CLIENT_SECRET` в Windows-клиент не добавляется. Для текущего Google Client ID он хранится только на Account Server в `backend/account_server/.env` и не попадает в Jarvis frontend, Windows environment или репозиторий.

## Конфигурация

Безопасные переменные клиента и сервера:

```dotenv
GOOGLE_AUTH_ENABLED=false
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8765/
```

`GOOGLE_CLIENT_SECRET` — server-only параметр. Его значение не передаётся клиенту.

Для включения интеграции владелец проекта должен самостоятельно внести публичный Client ID в локальную конфигурацию клиента и включить функцию. `GOOGLE_CLIENT_ID` не является секретом, но его значение не должно подменяться фиктивным. Серверная конфигурация должна использовать тот же Client ID для проверки audience. Секреты SMTP и прочие server-only значения остаются только в server `.env`.

## Связь Google identity с Jarvis Account

Добавлена сущность `external_identities`:

- `provider = google`;
- `provider_subject = Google sub`;
- `account_id` с foreign key на `accounts.id`;
- `email_at_link`;
- `created_at`, `last_login_at`;
- уникальность пары `(provider, provider_subject)`.

Если identity уже существует, вход выполняется в связанный Personal Account. Если identity отсутствует, но нормализованный email уже принадлежит другому аккаунту, автоматического merge нет: сервер возвращает безопасный конфликт `google_email_conflict`. Если email свободен, Account и identity создаются транзакционно, после чего выпускается Jarvis session.

## Изменённые компоненты

- `backend/account_server/google_identity.py` — проверка Google ID token claims.
- `backend/account_server/models.py` — модель `ExternalIdentity` и связь с Account.
- `backend/account_server/service.py` — Google exchange, linking/creation и конфликт email.
- `backend/account_server/api.py`, `schemas.py`, `app.py` — endpoint и wiring.
- `backend/account_server/migrations/versions/0002_external_identities.py` — Alembic migration.
- `backend/account/application/google_oauth.py` — loopback PKCE client.
- `backend/account/application/auth_client.py`, `account_coordinator.py` — client boundary.
- `frontend/account_ui.py` — кнопка «Войти через Google» и состояния операции.
- `.env.example` и `requirements.txt` — конфигурация и `google-auth`.

Основная SQLite, ChatStore, `/chat`, Voice Engine, Knowledge Library, MemoryAgent, SMTP Yandex и Cloud Sync в этой фазе не изменялись.

## Тестирование

Добавлены mock-тесты для:

- создания нового аккаунта и external identity;
- повторного входа по существующей identity;
- конфликта занятого email без автоматического объединения;
- неверной подписи;
- неверного issuer;
- неподтверждённого email.

Автоматические тесты не требуют настоящего Google аккаунта и не создают OAuth credentials. Реальный браузерный OAuth flow и live Google ID token ещё не проверялись.

## Ограничения и следующие действия

До первого реального входа необходимо:

1. Создать в Google Cloud OAuth Client типа Desktop app.
2. Для Desktop Client использовать loopback redirect `http://127.0.0.1:<port>/`; фактический порт выбирается Jarvis во время запуска OAuth.
3. Внести Client ID в локальную конфигурацию Windows-клиента.
4. Включить `GOOGLE_AUTH_ENABLED=true` только после проверки локального Account Server.
5. Перезапустить клиент после изменения конфигурации.

Реальный Google OAuth в этой фазе не заявляется выполненным. Cloud Sync, импорт истории и синхронизация памяти остаются отдельными фазами.
