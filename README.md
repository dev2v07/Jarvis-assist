# Jarvis Assist

Jarvis Assist — локальный персональный AI-ассистент для Windows с прозрачным
HUD-интерфейсом, текстовым чатом, голосовым runtime и расширяемыми агентами.
Проект находится в активной разработке и сейчас готовится к публичному релизу.

![Jarvis Assist — интерфейс](docs/images/jarvis-preview.jpg)

Превью показывает реальный визуальный стиль интерфейса Jarvis Assist.

## Возможности

- PySide6 desktop UI и переключаемый режим полноценного окна / прозрачного
  виджета;
- локальный FastAPI backend с планировщиком, executor/critic и прикладными
  агентами;
- Ollama и совместимые LLM-провайдеры через настройки приложения;
- команды Jarvis и отдельный router действий;
- faster-whisper/Silero VAD/TTS-адаптеры при установленных дополнительных
  зависимостях;
- реальный выбор микрофона, voice runtime и статусы голосовых моделей;
- камера/OpenCV и capability API для дополнительных устройств;
- сохранение настроек через QSettings и опциональный автозапуск Windows для
  текущего пользователя.
- локальная библиотека быстрых разговорных WAV-ответов с вариативным выбором;
  неизвестные, динамические и требующие расчёта вопросы по-прежнему передаются
  Ollama или профильному инструменту.

## Состояние релиза

Это pre-release. Основное приложение и backend проходят автоматические
проверки, но полноценный тест установленного EXE, удаления и запуска после
перезагрузки Windows остаётся обязательным release gate.

Собственная голосовая модель Jarvis ещё обучается и не включается в релиз.
Профиль Kesha — временный адаптер стандартного Silero `ru_v3` с диктором
`aidar`, а не персонально обученная модель.

## Запуск из исходников

Установите Python 3.11+ и зависимости:

```powershell
python -m pip install -r backend/requirements-core.txt
python -m pip install -r backend/requirements-optional.txt
```

Единый launcher запускает backend и desktop client:

```powershell
python frontend/launch_jarvis.py
```

Он ждёт `GET http://127.0.0.1:8000/health`, затем открывает интерфейс. Второй
запуск блокируется lock-файлом пользователя.

## Windows installer

Рецепт сборки находится в `packaging/`. Он создаёт backend- и desktop-сборки
PyInstaller, а при наличии Inno Setup — `Jarvis-Assistant-Setup.exe` с ярлыками
на рабочем столе и в меню Пуск. Локальные модели, датасеты, checkpoints и
обучение намеренно не включаются.

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

До первого публичного релиза нужно отдельно подтвердить установку, запуск,
удаление и очистку записи автозапуска на этой машине.

## Настройки и автозапуск

В разделе «Настройки → Общие» доступен параметр «Запускать Jarvis вместе с
Windows». Он использует только `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
и не требует прав администратора. В разделе «Голос AI» выбирается микрофон и
голосовой профиль; состояние модели берётся из backend, а не из одного лишь
значения UI.

## Разработка и проверки

```powershell
python -m compileall -q backend frontend core
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -p "test_*.py" -v
```

Архитектурный аудит: [docs/RELEASE_AUDIT_20261113.md](docs/RELEASE_AUDIT_20261113.md)

Дорожная карта: [ROADMAP.md](ROADMAP.md)

Журнал текущих голосовых и runtime-изменений: [docs/HANDOFF_ASSIST.md](docs/HANDOFF_ASSIST.md)

## Локальная библиотека голосовых ответов

База намерений находится в `data/voice_responses/questions.json`, а её текущий
статус — в `data/voice_responses/manifest.json`. Для мгновенных бытовых фраз
Jarvis выбирает один из готовых WAV и не обращается к Ollama. Истории, знания,
расчёты и команды не подменяются устаревшими статическими ответами.

После добавления или изменения текста базу можно пересобрать:

```powershell
python backend/voice_engine/build_voice_library.py
```

Генерация Fish Audio возобновляется с последнего готового файла и сохраняет
прогресс после каждого ответа:

```powershell
python backend/voice_engine/generate_voice_library.py --limit 24
python backend/voice_engine/generate_voice_library.py --all
```

Локальные WAV-файлы не являются исходным кодом и не добавляются в Git; они
остаются в `data/voice_responses/` на рабочей машине.

## Структура

```text
backend/     FastAPI, агенты, сервисы и voice runtime
frontend/    PySide6 UI, HUD, настройки и launcher
core/        общие контракты и message bus
docs/        handoff, аудит и пользовательская документация
packaging/   сценарии PyInstaller/Inno Setup
```

## Лицензия

Исходный код распространяется по [MIT License](LICENSE). Сторонние модели,
голоса, звуковые пакеты и внешние зависимости могут иметь собственные
лицензии; проверяйте их перед распространением сборки.
