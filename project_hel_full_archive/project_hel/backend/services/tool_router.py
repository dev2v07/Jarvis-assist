from __future__ import annotations
import re

ROUTES = {
    'backup': ['копи', 'backup', 'резерв'],
    'files': ['файл', 'каталог', 'директор', 'прочитай', 'сохрани'],
    'network': ['сайт', 'url', 'http', 'интернет'],
    'system': ['cpu', 'ram', 'система', 'производительность'],
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
