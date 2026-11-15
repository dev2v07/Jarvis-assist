# Jarvis Programming Mentor

## Назначение

Голосовой и текстовый режим обучения программированию. Mentor объясняет тему, выдаёт небольшое задание, проверяет результат и сохраняет прогресс. Он не изменяет проект пользователя без отдельного режима Coding Developer.

## Карта курсов

- HTML/CSS/JavaScript: структура, семантика, формы, DOM, accessibility, адаптивная вёрстка.
- PHP/WordPress: синтаксис, ООП, PDO, REST, темы, плагины, hooks, WP-CLI, безопасность.
- Python: язык, ООП, async, файлы/JSON/SQLite, FastAPI, PySide6, тесты, упаковка и PyInstaller.
- React/TypeScript: JSX, компоненты, state/hooks, Router, API, Vite и доступность.
- React Native: навигация, состояние, storage, камера, permissions и APK.
- Flutter/Dart: widgets, navigation, Provider/Riverpod/Bloc, API, SQLite и APK/AAB.
- Инженерные навыки: Git, Docker, SQL, REST/WebSocket, архитектура, тестирование, CI/CD и документация.

## Контракт урока

`уровень -> тема -> объяснение -> пример -> задание -> тест -> разбор ошибки -> прогресс`.

Прогресс должен храниться отдельно по языку и курсу. Актуальные API сверяются с официальной документацией; Ollama формулирует объяснение, но не является источником факта.

## Текущий статус

MVP подключён: уроки доступны через `/mentor/programming/lessons`, отдельный урок — через `/mentor/programming/lessons/{lesson_id}`, прогресс сохраняется в `data/knowledge3/programming/progress.json`. Практическое задание проверяется через `/mentor/programming/lessons/{lesson_id}/check`: код сначала запускается в ограниченном Python sandbox, затем проходят детерминированные критерии урока. Полноценный голосовой учебный сценарий и более глубокая проверка остаются следующим этапом.

