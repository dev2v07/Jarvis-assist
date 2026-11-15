# JARVIS — Phase 3 Implementation Report

Дата: 2026-11-15  
Режим: реализация подтверждённых исправлений без commit/push/reset  
Рабочая директория: `C:\projects\Jarvis`

## Итог

В Phase 3 выполнены точечные исправления по подтверждённым проблемам аудита:

- проектное Python 3.11 окружение дополнено совместимыми `PySide6==6.10.2` и
  `GPUtil==1.4.0`; версии зафиксированы в `backend/requirements-optional.txt`;
- добавлена единая контекстная обработка проверенных реплик о сне для text и
  voice путей;
- VoiceRuntime сохраняет ограниченное окно диалога и передаёт историю в общий
  resolver;
- `/knowledge/integrity` сообщает `PARTIAL`, если аудио-группы готовы не
  полностью, и возвращает детальные статусы групп;
- все ChatStore SQLite-соединения теперь коммитятся/откатываются и закрываются
  детерминированно;
- shutdown/reboot вынесены за контролируемую границу `WindowsActionExecutor`
  с явным подтверждением;
- launcher документирован как единая точка запуска UI/backend;
- добавлены изолированные тесты голосовой сессии, chat_id-привязки,
  эксклюзивности сессии, conversation resolver и action executor.

## Запуск и окружение

Проверено: `backend/jarvis_env/Scripts/python.exe` — Python 3.11.9,
`PySide6` — 6.10.2, импорт `frontend/jarvis_ui.py` проходит. Launcher был
запущен из проектного venv. Он обнаружил уже работающий UI через lock-файл и не
создал конкурирующее окно/второй backend. Существующий backend на
`127.0.0.1:8000` не останавливался.

Известные QtWebEngine сообщения о GLES3/virtualization fallback сохранились;
sandbox/security-параметры не отключались. Визуальный acceptance остаётся
средовым блокером.

Команда запуска:

```powershell
backend\jarvis_env\Scripts\python.exe frontend/launch_jarvis.py
```

## Реализованные изменения

### Контекст разговора и голос

`backend/services/conversation_resolver.py` — единый локальный resolver для text
и voice. Он использует предыдущие реплики и не вызывает Ollama/cloud provider
для проверенного сценария. VoiceSessionManager сохраняет одного активного
владельца; изолированная SQLite-проверка подтверждает запись user/assistant в
правильный `chat_id`.

### Knowledge integrity

`KnowledgeIndexService.integrity()` возвращает агрегированный `READY`, `PARTIAL`
или `ERROR` и `audio_groups` с числом записей и готовых WAV. Для текущего дерева
результат — `PARTIAL`; `AUDIO_PENDING` не считается ошибкой текста.

### SQLite lifecycle

Причина блокировки временной БД на Windows подтверждена тестом: прежний контекст
sqlite3 завершал транзакцию, но не закрывал connection. `ChatStore._connect()`
теперь является закрывающим контекстным менеджером с commit/rollback.

### Windows actions

`WindowsActionExecutor` принимает только поддержанные power intents, требует
`confirmed=True` и передаёт команды списком аргументов. Тесты используют
инъецированный runner; реальные shutdown/reboot не выполнялись.

## Тесты

```powershell
$env:PYTHONPATH = "backend"
$env:PYTHONDONTWRITEBYTECODE = "1"
backend\jarvis_env\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -p "test_*.py" -v
```

Результат: **56/56 PASS**, `ResourceWarning` не возник. Диагностическое
предупреждение о недоступном `OPENAI_TOKEN` остаётся существующей особенностью
конфигурации и не является ошибкой тестов. Дополнительно подтверждены импорт
backend, explicit CORS origins и `integrity.status=PARTIAL`.

## Оставшиеся блокеры

1. Живой микрофон/VAD/STT, непрерывный voice chat и освобождение реального
   устройства не проверены в этой итерации.
2. Fish Audio inference и TTS playback остаются внешне заблокированными:
   `fish_jarvis` не имеет подтверждённого inference, платный запрос без лимита
   не выполнялся.
3. HUD geometry и screenshot acceptance не закрыты: захват окна ранее падал по
   `FrameArrived/window capture timed out`; QtWebEngine сообщает GLES3 fallback.
4. Live POST-сценарии по пользовательской БД не запускались, чтобы не менять
   текущую историю.
5. Полное разделение монолитов и физическое объединение knowledge-каталогов не
   выполнялись; сохранён безопасный фасад/адаптерный подход.

## Сохранность

Не выполнялись миграции, удаление/перемещение файлов, перезапись чатов, WAV,
`voice_responses`, `offline_knowledge` или `knowledge3`; не изменялись `.env` и
секреты; commit/push/reset не выполнялись. Установлены только зависимости в
существующее проектное виртуальное окружение.
