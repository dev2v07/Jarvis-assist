"""Idempotently extend the local Programming Mentor curriculum.

The seed is deliberately small and reviewable. It never edits an existing
lesson, never touches audio files, and can be run again after adding more
lessons to the list.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from bible_paths import INDEX
from bible_paths import material
LESSONS = material("programming", "lessons.json")


def lesson(lesson_id: str, language: str, title: str, summary: str, explanation: str,
           example: str, exercise: str, source_url: str, source_title: str) -> dict:
    return {
        "id": lesson_id,
        "language": language,
        "level": "beginner",
        "title": title,
        "summary": summary,
        "explanation": explanation,
        "example": example,
        "exercise": exercise,
        "check": {"type": "manual", "criteria": ["решение запускается", "использована тема урока", "результат выведен или возвращён"]},
        "sources": [{"url": source_url, "title": source_title}],
        "generated_by": "main_model",
        "status": "VERIFIED",
        "audio_status": "AUDIO_PENDING",
        "audio_path": None,
        "version": 1,
    }


NEW_LESSONS = [
    lesson("html-001-document", "HTML", "HTML: структура документа", "Каркас страницы и семантические элементы.", "HTML-документ состоит из объявления типа, элемента html, секций head и body. Семантические теги помогают браузеру и вспомогательным технологиям понимать структуру страницы.", "<!doctype html>\n<html lang='ru'>\n  <head><meta charset='utf-8'><title>Jarvis</title></head>\n  <body><main><h1>Привет</h1></main></body>\n</html>", "Создай страницу с заголовком, основным содержимым и ссылкой.", "https://developer.mozilla.org/ru/docs/Learn/HTML/Introduction_to_HTML/Getting_started", "MDN: Начало работы с HTML"),
    lesson("html-002-form", "HTML", "HTML: форма и доступность", "Поля формы, labels и безопасная структура ввода.", "У каждого поля формы должна быть понятная label, а тип input должен соответствовать данным. Это улучшает доступность и проверку браузером.", "<form><label for='email'>Почта</label><input id='email' name='email' type='email' required><button type='submit'>Отправить</button></form>", "Создай форму имени и email с подписями и обязательным email.", "https://developer.mozilla.org/ru/docs/Learn/Forms", "MDN: Формы"),
    lesson("php-001-syntax", "PHP", "PHP: переменные и функции", "Базовый синтаксис серверного скрипта.", "В PHP переменные начинаются со знака доллара, а функция принимает параметры и может вернуть значение через return.", "<?php\nfunction greet(string $name): string { return \"Привет, $name\"; }\necho greet('Jarvis');", "Напиши функцию, которая принимает цену и количество и возвращает сумму.", "https://www.php.net/manual/ru/language.basic-syntax.phpsyntax.php", "PHP Manual: Синтаксис"),
    lesson("php-002-pdo", "PHP", "PHP: безопасный запрос через PDO", "Параметризованные запросы и работа с базой.", "PDO позволяет использовать подготовленные выражения. Значения пользователя нельзя склеивать в SQL-строку напрямую.", "$stmt = $pdo->prepare('SELECT * FROM users WHERE id = :id');\n$stmt->execute(['id' => $id]);", "Составь параметризованный SELECT по email.", "https://www.php.net/manual/ru/pdo.prepared-statements.php", "PHP Manual: Подготовленные выражения PDO"),
    lesson("wordpress-001-hooks", "WordPress", "WordPress: hooks и shortcode", "Как подключать поведение без изменения ядра.", "Actions сообщают о событии, filters изменяют значение. Плагин должен подключаться через API WordPress и не править ядро.", "add_action('init', function () { add_shortcode('hello', fn() => 'Привет'); });", "Создай небольшой shortcode, возвращающий безопасный текст.", "https://developer.wordpress.org/plugins/hooks/", "WordPress Developer Resources: Hooks"),
    lesson("wordpress-002-rest", "WordPress", "WordPress: REST API", "Получение данных через зарегистрированный endpoint.", "REST endpoint должен проверять права, валидировать входные данные и возвращать структурированный ответ.", "add_action('rest_api_init', function () { register_rest_route('jarvis/v1', '/ping', ['methods' => 'GET', 'callback' => fn() => ['ok' => true], 'permission_callback' => '__return_true']); });", "Опиши endpoint, который возвращает версию плагина без раскрытия секретов.", "https://developer.wordpress.org/rest-api/extending-the-rest-api/adding-custom-endpoints/", "WordPress Developer Resources: Custom Endpoints"),
    lesson("react-001-component", "React", "React: компонент и props", "Разделение интерфейса на переиспользуемые компоненты.", "Компонент получает входные данные через props и возвращает JSX. Состояние не следует дублировать без необходимости.", "function Greeting({ name }) { return <h1>Привет, {name}</h1>; }", "Создай компонент карточки проекта с props title и status.", "https://react.dev/learn/your-first-component", "React: Your First Component"),
    lesson("react-002-state", "React", "React: состояние и обработчик", "Изменение интерфейса через useState.", "useState возвращает текущее значение и функцию обновления. Обновление состояния должно происходить через setter.", "const [count, setCount] = useState(0);\n<button onClick={() => setCount(count + 1)}>{count}</button>", "Сделай счётчик задач с кнопками плюс и минус.", "https://react.dev/learn/state-a-components-memory", "React: State"),
    lesson("react-native-001-screen", "React Native", "React Native: экран и стиль", "Базовый экран мобильного приложения.", "React Native использует View и Text вместо DOM-элементов. Стили задаются объектами StyleSheet и применяются через style.", "import { View, Text } from 'react-native';\nexport default function App() { return <View><Text>Jarvis</Text></View>; }", "Создай экран профиля с именем и кнопкой действия.", "https://reactnative.dev/docs/getting-started", "React Native: Getting Started"),
    lesson("react-native-002-fetch", "React Native", "React Native: запрос API", "Загрузка данных и состояние ожидания.", "Сетевой запрос нужно сопровождать состояниями loading и error, чтобы пользователь понимал, что происходит.", "const response = await fetch(url);\nconst data = await response.json();", "Опиши функцию загрузки списка задач с обработкой ошибки.", "https://reactnative.dev/docs/network", "React Native: Networking"),
    lesson("flutter-001-widget", "Flutter", "Flutter: StatelessWidget", "Структура виджета и build.", "StatelessWidget подходит для интерфейса, который не хранит изменяемое локальное состояние. Метод build возвращает дерево виджетов.", "class Hello extends StatelessWidget { const Hello({super.key}); @override Widget build(BuildContext context) => const Text('Jarvis'); }", "Создай виджет карточки с заголовком и описанием.", "https://docs.flutter.dev/get-started/flutter-for/declarative", "Flutter: Declarative UI"),
    lesson("flutter-002-state", "Flutter", "Flutter: состояние StatefulWidget", "Изменяемый экран и setState.", "StatefulWidget отделяет конфигурацию виджета от объекта State. setState сообщает Flutter, что дерево нужно перестроить.", "setState(() { counter += 1; });", "Сделай счётчик на StatefulWidget и обновляй его кнопкой.", "https://docs.flutter.dev/get-started/flutter-for/declarative", "Flutter: State"),
    lesson("git-001-branch", "Git", "Git: ветки и безопасное изменение", "Изолирование работы через ветки.", "Ветка позволяет менять код отдельно от основной линии. Перед объединением нужно посмотреть diff и проверить тесты.", "git switch -c feature/mentor\ngit diff\ngit status", "Составь последовательность команд для новой функции без commit и push.", "https://git-scm.com/book/ru/v2/Основы-Git-Ветвление-в-Git", "Pro Git: Ветвление"),
    lesson("git-002-recovery", "Git", "Git: просмотр истории и восстановление", "Поиск причины изменения без разрушительных команд.", "Сначала используют log, show и diff. Сброс с потерей изменений нельзя выполнять без явного подтверждения.", "git log --oneline -5\ngit show HEAD -- path/to/file\ngit diff", "Опиши безопасный порядок анализа неожиданного изменения файла.", "https://git-scm.com/book/ru/v2/Основы-Git-Просмотр-истории-коммитов", "Pro Git: История"),
    lesson("sql-001-select", "SQL", "SQL: SELECT и фильтрация", "Выбор строк и ограничение результата.", "SELECT получает столбцы, WHERE фильтрует строки, ORDER BY задаёт порядок, LIMIT ограничивает объём.", "SELECT name, status FROM tasks WHERE status = 'open' ORDER BY name LIMIT 20;", "Составь запрос открытых задач, отсортированных по дате.", "https://www.postgresql.org/docs/current/tutorial-select.html", "PostgreSQL: Querying a Table"),
    lesson("sql-002-join", "SQL", "SQL: связи таблиц и JOIN", "Объединение связанных данных.", "JOIN связывает таблицы по ключу. Условие связи должно быть явным, иначе можно получить декартово произведение.", "SELECT users.name, tasks.title FROM users JOIN tasks ON tasks.user_id = users.id;", "Выведи имя пользователя и название его задач через JOIN.", "https://www.postgresql.org/docs/current/tutorial-join.html", "PostgreSQL: Joins"),
    lesson("fastapi-001-route", "FastAPI", "FastAPI: маршрут и Pydantic", "Типизированный HTTP endpoint.", "FastAPI использует аннотации и Pydantic-модели для валидации входа и формирования понятного API.", "class Item(BaseModel): name: str\n@app.post('/items')\ndef create(item: Item): return item", "Создай endpoint, принимающий имя проекта и возвращающий его в JSON.", "https://fastapi.tiangolo.com/tutorial/body/", "FastAPI: Request Body"),
    lesson("fastapi-002-errors", "FastAPI", "FastAPI: ошибки и статус ответа", "Предсказуемые ошибки API.", "Клиенту нужно возвращать корректный HTTP-статус и безопасное сообщение, не раскрывая traceback и секреты.", "if not item: raise HTTPException(status_code=404, detail='Not found')", "Добавь обработку отсутствующего проекта с кодом 404.", "https://fastapi.tiangolo.com/tutorial/handling-errors/", "FastAPI: Handling Errors"),
    lesson("html-003-accessibility", "HTML", "HTML: доступность и landmarks", "Семантическая разметка, landmarks и текстовые альтернативы.", "Используй main, nav и button по назначению, а изображения снабжай осмысленным alt. Доступность нельзя исправлять только визуальными стилями.", "<nav aria-label='Основное меню'><a href='/'>Главная</a></nav>\n<main><h1>Курс</h1></main>", "Сделай разметку страницы с nav, main и доступной кнопкой.", "https://developer.mozilla.org/ru/docs/Learn/Accessibility", "MDN: Accessibility"),
    lesson("php-003-validation", "PHP", "PHP: валидация входных данных", "Проверка и нормализация данных формы.", "Сначала нормализуй вход, затем валидируй тип, длину и формат. Ошибки должны быть понятны пользователю и не содержать секретов.", "$email = filter_input(INPUT_POST, 'email', FILTER_VALIDATE_EMAIL);\nif ($email === false) { http_response_code(422); }", "Опиши обработку невалидного email с безопасным ответом.", "https://www.php.net/manual/ru/filter.filters.validate.php", "PHP Manual: Фильтры валидации"),
    lesson("wordpress-003-security", "WordPress", "WordPress: nonce и права", "Базовая защита действий администратора.", "Для изменяющих действий проверяй capability и nonce. Экранируй вывод в момент вывода, а не полагайся на доверие к форме.", "if (! current_user_can('manage_options')) { wp_die('Недостаточно прав'); }\ncheck_admin_referer('jarvis_save');", "Составь безопасную проверку сохранения настройки плагина.", "https://developer.wordpress.org/apis/security/nonces/", "WordPress: Nonces"),
    lesson("python-004-testing", "Python", "Python: тестируем функцию", "Изолированный тест и проверяемый результат.", "Тест должен проверять наблюдаемое поведение функции и быть независимым от случайного состояния окружения.", "def add(a, b): return a + b\nassert add(2, 3) == 5", "Напиши два assert-теста для функции, которая считает скидку.", "https://docs.python.org/3/library/unittest.html", "Python: unittest"),
    lesson("react-003-form", "React", "React: контролируемая форма", "Состояние поля и обработка submit.", "Контролируемое поле получает value из state и обновляется через onChange. На submit нужно отменить перезагрузку страницы и проверить данные.", "const [name, setName] = useState('');\n<form onSubmit={e => { e.preventDefault(); save(name); }}><input value={name} onChange={e => setName(e.target.value)} /></form>", "Создай форму поиска с контролируемым input и обработчиком submit.", "https://react.dev/learn/responding-to-events", "React: Responding to Events"),
    lesson("react-native-003-permissions", "React Native", "React Native: состояния разрешений", "Понятный UX для недоступной функции устройства.", "Состояния denied, granted и unavailable нужно различать и показывать пользователю безопасный следующий шаг вместо падения приложения.", "if (status === 'denied') return <Text>Разрешение отключено в настройках</Text>;", "Опиши экран, который показывает разные состояния разрешения микрофона.", "https://reactnative.dev/docs/permissionsandroid", "React Native: PermissionsAndroid"),
    lesson("flutter-003-async", "Flutter", "Flutter: FutureBuilder и ошибка", "Отображение загрузки, результата и ошибки.", "Асинхронный экран должен явно обрабатывать waiting, data и error, не оставляя пользователя на бесконечном спиннере.", "FutureBuilder(future: load(), builder: (context, snapshot) { if (snapshot.hasError) return Text('Ошибка'); return Text('${snapshot.data}'); })", "Составь состояния виджета загрузки списка проектов.", "https://api.flutter.dev/flutter/widgets/FutureBuilder-class.html", "Flutter: FutureBuilder"),
    lesson("git-003-tag", "Git", "Git: теги и воспроизводимый релиз", "Фиксация версии без изменения рабочей директории.", "Annotated tag помогает обозначить проверенный релиз. Перед созданием тега нужно проверить status и историю.", "git status\ngit log --oneline -3\ngit tag -a v0.1.0 -m 'release'", "Составь безопасную последовательность подготовки локального тега без push.", "https://git-scm.com/book/ru/v2/Основы-Git-Основы-работы-с-тегами", "Pro Git: Теги"),
    lesson("sql-003-transaction", "SQL", "SQL: транзакция и откат", "Атомарное изменение нескольких таблиц.", "Транзакция группирует изменения: commit фиксирует всё, rollback откатывает всё при ошибке.", "BEGIN;\nUPDATE accounts SET balance = balance - 10 WHERE id = 1;\nCOMMIT;", "Опиши перевод средств с проверкой ошибки и rollback.", "https://www.postgresql.org/docs/current/tutorial-transactions.html", "PostgreSQL: Transactions"),
    lesson("fastapi-003-dependency", "FastAPI", "FastAPI: dependency и проверка доступа", "Переиспользуемая проверка контекста запроса.", "Dependencies позволяют централизовать получение пользователя и проверку доступа, не копируя безопасность в каждом endpoint.", "def require_user(token: str = Header()):\n    if not token: raise HTTPException(401)\n    return token", "Составь dependency, которая отклоняет запрос без токена кодом 401.", "https://fastapi.tiangolo.com/tutorial/dependencies/", "FastAPI: Dependencies"),
]


def main() -> None:
    rows = json.loads(LESSONS.read_text(encoding="utf-8")) if LESSONS.exists() else []
    existing = {str(row.get("id")) for row in rows}
    added = [row for row in NEW_LESSONS if row["id"] not in existing]
    if added:
        LESSONS.write_text(json.dumps(rows + added, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            index = json.loads(INDEX.read_text(encoding="utf-8"))
            programming = index.setdefault("programming", {})
            final_rows = rows + added
            programming["lessons"] = len(final_rows)
            programming["languages"] = sorted({str(row.get("language")) for row in final_rows if row.get("language")})
            INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
    print(json.dumps({"existing": len(rows), "added": len(added), "total": len(rows) + len(added)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
