# Jarvis — целевое техническое задание

## 1. Видение продукта

Jarvis — единая персональная AI-платформа, которая работает не только как локальное приложение-помощник, но и как распределённый ассистент на нескольких площадках:

- Windows desktop;
- web application in a browser;
- смартфон;
- умный дом;
- умная колонка;
- голосовые и визуальные устройства;
- единый backend и личная память пользователя.

Клиенты должны использовать общие возможности Jarvis, но иметь собственные адаптеры ввода, вывода, разрешений и аппаратных возможностей.

## 2. Основные пользовательские цели

Jarvis должен:

1. слышать обращение и понимать голосовые команды;
2. отвечать голосом исходных записей пользователя/персонажа;
3. воспроизводить оригинальные WAV/MP3 и синтезировать новые фразы тем же голосом;
4. вести текстовый и голосовой диалог;
5. планировать и выполнять многошаговые задачи через агентов;
6. работать с файлами, сетью, приложениями, экраном, камерой и умным домом;
7. использовать Ollama, Codex/OpenAI, Claude и FreeLLMAPI через единый слой провайдеров;
8. запоминать подтверждённые факты и историю действий;
9. работать в автономном режиме с понятным offline/fallback-состоянием;
10. масштабироваться от одного ПК до нескольких устройств пользователя.

## 3. Архитектурный принцип

Нельзя привязывать ядро Jarvis к Qt, Windows, конкретной LLM, микрофону или одному способу доставки ответа.

Целевая схема:

```text
Desktop / Web / Mobile / Smart Speaker / Smart Home
                         |
                 Device Gateway
                         |
              Auth + Session + Events
                         |
       Jarvis Core: Planner / Executor / Agents
                         |
       Tools / Memory / LLM Providers / Policies
```

## 4. Слои системы

### 4.1. Device Layer

Адаптеры конкретных устройств:

- микрофон;
- динамик;
- камера;
- экран;
- системные уведомления;
- GPIO/IoT-интеграции;
- Bluetooth/Wi-Fi;
- Android/iOS bridge;
- desktop window integration.

Для web-клиента этот слой включает browser permissions, Web Audio API, WebRTC при необходимости, push notifications и responsive UI. Браузер не получает прямой доступ к системным инструментам: опасные действия выполняются через backend policy layer или подключённый device node.

### 4.2. Transport Layer

Единые способы обмена:

- HTTP API для команд и настроек;
- WebSocket/SSE для прогресса и событий;
- MQTT или совместимый протокол для умного дома;
- локальный IPC для desktop-компонентов;
- push-канал для смартфона и колонки.

### 4.3. Application Core

Общее ядро, не зависящее от интерфейса:

- request/session manager;
- planner;
- executor;
- agent registry;
- message/event bus;
- permissions/policy engine;
- task cancellation;
- retries/timeouts;
- artifacts;
- audit log.

### 4.4. Intelligence Layer

Единый интерфейс для:

- Ollama;
- Codex/OpenAI;
- Claude;
- FreeLLMAPI;
- локальных stub/fallback-моделей;
- speech-to-text;
- text-to-speech;
- vision models;
- embeddings и поиска по памяти.

### 4.5. Storage Layer

Разделить:

- краткосрочный контекст;
- историю запросов;
- долговременную память;
- документы и embeddings;
- настройки;
- устройства;
- разрешения;
- голосовые модели;
- артефакты и резервные копии.

## 5. Требования к агентам

Каждый агент должен иметь единый контракт:

```python
class Agent:
    name: str

    async def handle(self, request, context) -> AgentResult:
        ...
```

Агент не должен напрямую зависеть от Qt, FastAPI или конкретного устройства. Для внешних действий он использует типизированные tools.

Обязательные свойства:

- timeout;
- cancellation;
- structured result;
- permission declaration;
- retry policy;
- logging;
- health status;
- idempotency по request_id;
- возможность локального или удалённого выполнения.

## 6. Приоритетные модули

### Фаза A — архитектурная стабилизация

- выбрать одну актуальную версию кода;
- убрать дублирующие поколения;
- исправить запуск агентов;
- привести конфигурацию к одному источнику истины;
- устранить рассинхрон frontend/backend;
- отделить обязательные и optional-зависимости;
- убрать секреты из репозитория;
- добавить smoke-тесты;
- включить Git/CI.

### Фаза B — Core Runtime

- request manager;
- task state machine;
- event schema;
- agent registry;
- executor;
- permissions;
- cancellation;
- recovery;
- audit log.

### Фаза C — Voice Runtime

- wake word;
- audio capture;
- speech-to-text;
- voice session;
- original WAV/MP3 playback;
- cloned voice TTS;
- interruption/barge-in;
- audio routing.

### Фаза D — LLM Runtime

- provider interface;
- Ollama adapter;
- Codex/OpenAI adapter;
- Claude adapter;
- FreeLLMAPI adapter;
- streaming;
- fallback;
- model selection;
- token/cost/time metrics.

### Фаза E — Clients

- autonomous desktop UI;
- web client with responsive chat, streaming events, settings, history and device/session management;
- Android/iOS client;
- smart speaker adapter;
- smart-home gateway;
- notifications;
- device pairing;
- offline mode.

### Web-клиент

Веб-версия должна быть отдельным frontend-клиентом, но не отдельной логикой Jarvis. Она использует:

- тот же API-контракт;
- WebSocket/SSE для потоковых событий;
- общие чаты и память;
- общие permissions;
- login и device pairing;
- адаптивную верстку для desktop/tablet/mobile;
- PWA-режим для установки как приложения;
- ограниченный offline-режим с локальной очередью команд.

Веб-клиент не должен выполнять произвольные команды на компьютере пользователя. Для этого используется подключённый desktop node или отдельный разрешённый device node.

### Фаза F — Vision and Smart Home

- camera capture;
- screen capture;
- OCR;
- object/scene recognition;
- vision agent;
- MQTT/Home Assistant integration;
- device discovery;
- scenes and automations;
- safety confirmations.

### Фаза G — Optimization and Delivery

- profiling;
- caching;
- worker pools;
- model lazy-loading;
- resource limits;
- packaging;
- installer/updater;
- telemetry only with explicit consent;
- backup and restore.

## 7. Правило развития

Каждая новая функция должна подключаться через общий runtime и иметь:

1. API/событие;
2. permission policy;
3. agent/tool contract;
4. UI/device representation;
5. logging;
6. test;
7. offline/error behavior.

Нельзя добавлять платформенный код напрямую в Planner или Executor.

## 8. Ближайший технический результат

Первый milestone:

```text
Один backend
→ работающие агенты
→ единый API
→ Qt UI подключён к API
→ текстовая команда выполняется
→ прогресс приходит в UI
→ команда отменяется
→ результат сохраняется в истории
```

Только после этого добавляются голосовой клон, новые LLM-провайдеры, смартфон, колонка и умный дом.
