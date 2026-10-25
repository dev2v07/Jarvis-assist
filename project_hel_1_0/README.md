# Проект Хель

Локальный desktop-first AI-ассистент с FastAPI backend, Electron frontend и модульным pipeline: план → подтверждение → выполнение → итоговый ответ.

## Что уже работает
- backend на FastAPI с отдельным lifecycle запроса
- Electron UI с опросом статуса, модалками плана и разрешений
- событийный execution pipeline через message bus
- режимы работы (`general`, `file`, `sysadmin`, `backup` и другие)
- файловый sandbox внутри workspace `~/hel_data`
- подтверждение опасных действий: file/network/backup
- настоящий LLM-провайдер через Ollama или OpenAI-compatible API
- реальные сетевые запросы через `NetworkAgent`
- persistent request state в SQLite
- скрипт упаковки Windows installer через PyInstaller + electron-builder
- structured logging в JSON-lines с ротацией
- retry/timeout policy для LLM и network
- авто-создание runtime-конфига на Windows и Linux/macOS
- smoke test для базового сценария

## Структура
- `backend/` — API, агенты, шина сообщений, сервисы
- `backend/services/state_store.py` — SQLite-хранилище состояний запросов
- `backend/utils/logging_setup.py` — настройка JSON-логов
- `.env.example` — шаблон конфигурации
- `package_windows.ps1` — сборка backend exe и NSIS installer под Windows
- `tests/smoke_test.py` — базовая интеграционная проверка
- `docs/architecture.md` — архитектура
- `start.bat` / `start.sh` — запуск проекта

## Runtime config
Приложение читает настройки из двух мест:
1. локальный `.env` в корне проекта
2. runtime `.env` в пользовательском каталоге конфигурации

По умолчанию runtime config создаётся автоматически:
- **Windows:** `%APPDATA%\ProjectHel\.env`
- **Linux/macOS:** `~/.config/project_hel/.env`

Чтобы настроить проект, скопируй шаблон:

```powershell
copy .env.example .env
```

Или просто запусти приложение: при первом старте runtime `.env` будет создан автоматически.



## Быстрая установка API ключа из интерфейса
Теперь ключ можно поставить прямо из приложения:
1. Запусти Хель
2. Нажми кнопку **LLM / API ключ** слева
3. Выбери провайдера: `Ollama` или `OpenAI-compatible`
4. Вставь ключ в поле **API key**
5. Нажми **Проверить подключение**
6. Нажми **Сохранить**

Хель сохранит настройки в runtime-файл:
- **Windows:** `%APPDATA%\ProjectHel\.env`
- **Linux/macOS:** `~/.config/project_hel/.env`

Ключ не нужно вручную искать в файлах, если используешь этот экран.

## Логи
Логи пишутся в JSON-lines и ротируются автоматически.

По умолчанию:
- **Windows:** `%APPDATA%\ProjectHel\logs\project_hel.log`
- **Linux/macOS:** `~/.config/project_hel/logs/project_hel.log`

Пример записи:

```json
{"ts":"2026-03-06T11:30:00","level":"INFO","logger":"hel.app","message":"chat_request_received","event":"chat_request_received","request_id":"...","status":"planning"}
```

## Полезные переменные окружения
```text
HEL_LLM_PROVIDER=stub|ollama|openai
HEL_OLLAMA_BASE_URL=http://127.0.0.1:11434
HEL_OLLAMA_MODEL=qwen2.5:7b-q4_K_M
HEL_OPENAI_BASE_URL=https://api.openai.com/v1
HEL_OPENAI_MODEL=gpt-4o-mini
HEL_OPENAI_API_KEY=...
HEL_LLM_REQUEST_TIMEOUT=45
HEL_LLM_MAX_RETRIES=2
HEL_NETWORK_REQUEST_TIMEOUT=20
HEL_NETWORK_MAX_RETRIES=2
HEL_RETRY_BACKOFF_SECONDS=1.5
HEL_LOG_LEVEL=INFO
```

## Быстрый старт на Windows
1. Установи Python 3.11+ и Node.js 20+
2. Открой PowerShell в корне проекта
3. Запусти backend:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Во втором окне:

```powershell
cd frontend
npm install
npm start
```

Или просто используй `start.bat`.

## Настройка LLM
По умолчанию работает локальный stub. Для реальной модели выставь переменные окружения в `.env`.

### Ollama

```powershell
HEL_LLM_PROVIDER=ollama
HEL_OLLAMA_MODEL=qwen2.5:7b
HEL_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

### OpenAI-compatible API

```powershell
HEL_LLM_PROVIDER=openai
HEL_OPENAI_API_KEY=your_key_here
HEL_OPENAI_MODEL=gpt-4o-mini
HEL_OPENAI_BASE_URL=https://api.openai.com/v1
```

Если внешний провайдер недоступен, Хель логирует ошибку и мягко уходит в stub, а не ломает сценарий целиком.

## Сетевые интеграции
`NetworkAgent` делает реальные HTTP/HTTPS-запросы после подтверждения разрешения. Он умеет:
- читать JSON API
- делать GET/HEAD запросы
- извлекать title и preview из HTML
- повторять запрос при временной ошибке

Пример запроса:

```text
Открой https://api.github.com и покажи ответ
```

## Persistent state
Состояние запросов хранится в SQLite:

```text
backend/data/hel_state.sqlite3
```

Даже после перезапуска можно читать историю через:
- `GET /requests/{id}`
- `GET /requests`

## Сборка Windows installer
На Windows открой PowerShell в корне проекта и запусти:

```powershell
./package_windows.ps1
```

Скрипт:
1. создаёт runtime `.env`, если его ещё нет
2. создаёт `hel_backend.exe` через PyInstaller
3. кладёт его в `backend_dist/`
4. собирает NSIS installer через `electron-builder`

Готовый установщик появится в:

```text
frontend/dist/
```

## Smoke test
После установки зависимостей backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
python tests/smoke_test.py
```

## Как работает текущий MVP
1. UI отправляет запрос в `/chat`
2. Backend создаёт `request_id`
3. Planner строит план
4. Пользователь подтверждает план
5. Executor проходит шаги по очереди
6. Для опасных действий спрашивается разрешение
7. Critic собирает финальный ответ
8. UI получает итог через `/requests/{id}`
9. История сохраняется в SQLite
10. Все ключевые события логируются в JSON-lines

## Workspace
Все файловые действия ограничены папкой:

```text
~/hel_data
```

Это снижает риск случайной записи в системные директории.


## Быстрая настройка API-ключа

Есть два удобных способа задать ключ один раз:

1. Внутри приложения: открой кнопку **LLM / API ключ**, выбери провайдера, вставь ключ и нажми **Сохранить**.
2. Через консоль на Windows: запусти `set_api_key.bat` или `powershell -ExecutionPolicy Bypass -File .\set_api_key.ps1`.

Ключ сохраняется локально в runtime-конфиг и автоматически подхватывается при следующих запусках.


## Что улучшено в стабильной сборке
- интерфейс больше не блокируется, если backend поднимается медленно
- добавлена кнопка «Обновить статус»
- в левой панели появилась история последних задач
- backend пишет логи запуска в папку Electron userData/logs


## Быстрый запуск на Windows
1. Установите Python 3.11+ и Node.js 20+.
2. Распакуйте архив.
3. Запустите `start.bat`.
4. Откройте кнопку **LLM / API ключ** и сохраните провайдера и ключ.

## Диагностика
Если приложение не поднимается:
- backend logs: `%APPDATA%/Project Hel/logs/backend.err.log` и `backend.out.log` в папке userData Electron
- runtime config: `%APPDATA%\ProjectHel\.env`
- проверка backend: `backend\.venv\Scripts\python.exe backend\doctor.py`

## Что реально работает
- desktop UI на Electron
- backend на FastAPI
- последовательное выполнение плана
- подтверждение плана и разрешений
- работа с файлами в workspace
- системный режим
- сохранение истории запросов в SQLite
- настройка OpenAI-compatible и Ollama через UI
