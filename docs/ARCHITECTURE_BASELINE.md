# Jarvis architecture baseline — queue 0114

Дата: 2026-10-26  
Исполнитель: `Schrodinger`

## Задача очереди

Зафиксировать первый практический, платформо-независимый слой основного ТЗ.
Очередь не меняет перенос Crazy Tad и не подключает новые контракты к текущему
чат-пайплайну. Это отдельная точка опоры перед развитием web/mobile/device
клиентов.

## Зафиксированная схема

```text
Client adapter (desktop/web/mobile/smart-home/speaker)
              -> RequestContext
              -> Jarvis core / agents / tools
              -> AgentResult + RuntimeEvent
              -> client adapter

LLM providers -> ProviderStatus -> settings/health/UI
```

### Контракты

`backend/core/contracts.py` содержит только JSON-совместимые dataclass-модели:

- `RequestContext` — request/session identity, client, platform, mode, locale и
  расширяемые metadata;
- `AgentResult` — единый completed/failed результат агента или tool adapter;
- `RuntimeEvent` — версионированный envelope для будущих SSE/WebSocket/IPC/MQTT
  каналов;
- `ProviderStatus` — нормализованный health/status провайдера;
- `new_request_context()` — генерация request id на границе адаптера.

Контракт не импортирует Qt, FastAPI, Crazy Tad, chat storage или конкретную
LLM-библиотеку. Поэтому его можно использовать в desktop, web, mobile и
smart-home адаптерах без переноса UI-зависимостей в ядро.

## Что намеренно не входит в очередь

- `frontend/assets/CHAT/chat.html`;
- `frontend/chat_composer.py`;
- `backend/services/chat_store.py`;
- текущие chat/media/emote routes и их payload;
- исходный проект `C:\projects\Crazy Tad\.crazy_tad_system`;
- фактическое переключение Planner/Executor на новые dataclass-контракты.

Последний пункт выделен в отдельную миграционную очередь: сначала потребуется
описать совместимый adapter между текущими словарями MessageBus и новыми
контрактами, а затем покрыть его runtime-тестами.

## Следующий безопасный порядок

1. Добавить `RuntimeContractAdapter` на границе MessageBus с сохранением старых
   словарных сообщений.
2. Вывести provider status в отдельный backend endpoint, не меняя `/chat`.
3. Подключить request/session lifecycle и cancellation к core runtime.
4. Только после этого переводить отдельные агенты на typed result/event.

## Проверка

Запуск тестов выполняется из корня проекта с `PYTHONPATH=backend`:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -p "test_*.py" -v
```
