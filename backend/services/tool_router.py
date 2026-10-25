from __future__ import annotations

ROUTES = {

    # --------------------------------
    # backup agent
    # --------------------------------
    'backup': [
        'копи', 'backup', 'резерв',
        'резервная копия', 'бэкап'
    ],

    # --------------------------------
    # file agent
    # --------------------------------
    'files': [
        'файл', 'каталог', 'директор',
        'прочитай', 'открой файл',
        'сохрани', 'запиши',
        'создай файл',
        'workspace',
        '.txt', '.md', '.json', '.py'
    ],

    # --------------------------------
    # network agent (HTTP / API)
    # --------------------------------
    'network': [
        'api', 'endpoint',
        'запрос', 'headers',
        'json', 'rest',
        'http', 'url',
        'ping', 'проверь сайт'
    ],

    # --------------------------------
    # web agent (браузер / поиск)
    # --------------------------------
    'web': [
        'браузер', 'browser',
        'сайт', 'website',
        'google', 'гугл',
        'youtube', 'ютуб',
        'поиск', 'найди',
        'search', 'интернет',
        'открой сайт'
    ],

    # --------------------------------
    # system agent
    # --------------------------------
    'system': [
        'cpu', 'ram',
        'нагрузка', 'память',
        'диск', 'gpu',
        'система',
        'производительность'
    ],

    # --------------------------------
    # vision agent
    # --------------------------------
    'vision': [
        'изображ', 'картинка',
        'скриншот', 'скрин',
        'экран', 'screen'
    ],

    # --------------------------------
    # voice agent
    # --------------------------------
    'voice': [
        'голос', 'аудио',
        'звук', 'микрофон',
        'скажи', 'озвучь'
    ],

    # --------------------------------
    # memory agent
    # --------------------------------
    'memory': [
        'запомни', 'запиши в память',
        'remember',
        'вспомни', 'помнишь',
        'memory'
    ],

    # --------------------------------
    # game coach agent
    # --------------------------------
    'game': [
        'игра', 'game',
        'cs', 'cs2',
        'dota', 'valorant',
        'как играть',
        'тактика', 'стратегия',
        'гайд', 'build'
    ],

    # --------------------------------
    # social agent (разговоры)
    # --------------------------------
    'social': [
        'привет', 'здравствуй',
        'как дела', 'как ты',
        'кто ты', 'что ты умеешь',
        'расскажи', 'шутк',
        'поговори',
        'спасибо', 'благодарю',
        'пока'
    ],

}


def pick_route(step: str, mode: str) -> str:

    s = step.lower()

    # режимы
    if mode == "backup":
        return "backup"

    if mode == "file":
        return "files"

    if mode == "game":
        return "game"

    if mode == "sysadmin":
        return "system"

    # приоритет маршрутов
    ROUTE_PRIORITY = [
        "vision",
        "files",
        "network",
        "web",
        "system",
        "voice",
        "memory",
        "game",
        "backup",
        "social"
    ]

    for route in ROUTE_PRIORITY:
        tokens = ROUTES.get(route, [])
        for token in tokens:
            if token in s:
                return route

    # fallback
    if "http" in s or "www" in s:
        return "network"

    if "файл" in s:
        return "files"

    if "google" in s or "youtube" in s:
        return "web"

    if any(x in s for x in ["как", "почему", "что", "кто", "зачем"]):
        return "social"

    return "social"