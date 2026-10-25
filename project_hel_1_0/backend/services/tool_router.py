from __future__ import annotations

ROUTES = {
    'backup': ['копи', 'backup', 'резерв'],
    'files': ['файл', 'каталог', 'директор', 'прочитай', 'сохрани', 'запиши', 'создай', 'workspace', '.txt', '.md', '.json'],
    'network': ['сайт', 'url', 'http', 'интернет', 'домен', 'api'],
    'system': ['cpu', 'ram', 'система', 'производительность', 'диск', 'память'],
    'vision': ['изображ', 'скриншот', 'картинк'],
    'voice': ['голос', 'аудио', 'звук'],
}


def pick_route(step: str, mode: str) -> str:
    s = step.lower()
    if mode == 'backup':
        return 'backup'
    if mode == 'file':
        return 'files'
    if mode == 'game':
        return 'vision'
    if mode == 'sysadmin':
        return 'system'
    for route, tokens in ROUTES.items():
        if any(token in s for token in tokens):
            return route
    return 'general'
