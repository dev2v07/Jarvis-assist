# Архитектура Проекта Хель

## Слои

### 1. Frontend
Electron + HTML/CSS/JS.
- отправляет сообщения в backend
- показывает планы, запросы разрешений и ответы
- управляет режимами работы ассистента

### 2. API слой
FastAPI предоставляет REST endpoints:
- `POST /chat`
- `POST /permission_response`
- `POST /plan_approval`
- `GET /health`
- `GET /modes`

### 3. Ядро orchestration
- `MessageBus` — внутренняя асинхронная шина
- `MainAgent` — координация итогового ответа
- `PlannerAgent` — разбиение задачи на шаги
- `ExecutorAgent` — выполнение шагов и маршрутизация в tool-агенты
- `CriticAgent` — пост-проверка результата
- `PolicyManager` — разрешения на сеть/файлы/опасные операции

### 4. Доменные агенты
Каждый агент реализует единый интерфейс `Agent.handle_message`.
- `MemoryAgent`
- `NetworkAgent`
- `FileAgent`
- `VisionAgent`
- `VoiceAgent`
- `PerformanceAgent`
- `SocialAgent`
- `GameCoachAgent`
- `BackupAgent`

### 5. Сервисы
- `llm_service.py` — единая точка работы с LLM/локальной заглушкой
- `storage_service.py` — факты, документы, простое персистентное хранение
- `tool_router.py` — сопоставление шагов плана и исполнителя

## Поток сообщения
1. Frontend отправляет запрос в `POST /chat`.
2. API создаёт `msg_id` и кладёт future в `MainAgent`.
3. `PlannerAgent` строит список шагов исходя из режима.
4. Frontend подтверждает план.
5. `ExecutorAgent` по шагам вызывает нужные доменные агенты.
6. `CriticAgent` делает финальную проверку качества.
7. `MainAgent` возвращает итог в HTTP-ответ.

## Безопасность
- операции записи вне workspace требуют подтверждения
- системные каталоги запрещены
- сетевые запросы могут быть ограничены whitelist-моделью
- резервное копирование отделено в отдельный агент
