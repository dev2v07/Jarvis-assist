# core/modes.py

DEFAULT_MODE = "general"


MODES = {
    "general": {
        "title": "Общий",
        "icon": "💬",
        "description": "Универсальный режим ассистента."
    },

    "game": {
        "title": "Игровой помощник",
        "icon": "🎮",
        "description": "Советы по играм и стратегиям."
    },

    "coder": {
        "title": "Программист",
        "icon": "👨‍💻",
        "description": "Генерация и анализ кода."
    },

    "file": {
        "title": "Файловый помощник",
        "icon": "📁",
        "description": "Работа с файлами и каталогами."
    },

    "analyst": {
        "title": "Аналитик",
        "icon": "📈",
        "description": "Таблицы, отчёты и анализ данных."
    },

    "translator": {
        "title": "Переводчик",
        "icon": "🌐",
        "description": "Перевод текста."
    },

    "tutor": {
        "title": "Репетитор",
        "icon": "🎓",
        "description": "Обучение и объяснение."
    },

    "sysadmin": {
        "title": "Системный администратор",
        "icon": "🖥️",
        "description": "Диагностика системы."
    },

    "office": {
        "title": "Офис-менеджер",
        "icon": "📊",
        "description": "Документы и организация задач."
    },
}


# ------------------------------------------------
# helpers
# ------------------------------------------------

def get_mode(mode: str):

    if mode not in MODES:
        return MODES[DEFAULT_MODE]

    return MODES[mode]


def is_valid_mode(mode: str):

    return mode in MODES


def list_modes():

    return list(MODES.keys())