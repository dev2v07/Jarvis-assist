import os
import webbrowser
import pyautogui
import datetime
import time
import re
import subprocess
from pathlib import Path
import yaml

from rapidfuzz import fuzz
from services.application_service import APP_ALIASES, ApplicationService
from services.filesystem_service import AmbiguousPathError, FileSystemService


# ---------------------------------------------
# пути
# ---------------------------------------------

BASE_DIR = os.path.dirname(__file__)
COMMANDS_FILE = os.path.join(BASE_DIR, "voice_engine", "commands.yaml")


# ---------------------------------------------
# загрузка YAML
# ---------------------------------------------

with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
    COMMANDS = yaml.safe_load(f)
FILESYSTEM = FileSystemService(Path(BASE_DIR))
APPLICATIONS = ApplicationService(Path(BASE_DIR))
COMMAND_FEEDBACK = ""


REMINDERS = []


# ---------------------------------------------
# память диалога
# ---------------------------------------------

LAST_CONTEXT = None
LAST_CONTEXT_TIME = 0
CONTEXT_TIMEOUT = 30


# ---------------------------------------------
# режим обучения
# ---------------------------------------------

LEARNING_MODE = False
UNKNOWN_COMMAND = None
PENDING_CONFIRMATION = None


# ---------------------------------------------
# действия
# ---------------------------------------------

def open_browser():
    webbrowser.open("https://google.com")


def open_google():
    webbrowser.open("https://google.com")


def open_youtube():
    webbrowser.open("https://youtube.com")


def open_music():
    global COMMAND_FEEDBACK
    try:
        item = APPLICATIONS.launch("яндекс музыка")
        COMMAND_FEEDBACK = f"Запускаю {item['name']}."
    except FileNotFoundError:
        COMMAND_FEEDBACK = "Приложение Яндекс Музыка не найдено, открываю сайт."
        webbrowser.open("https://music.yandex.ru")


def open_weather():
    webbrowser.open("https://yandex.ru/pogoda")


def open_dollar():
    webbrowser.open("https://www.google.com/search?q=курс+доллара")


def open_telegram():
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "Telegram Desktop" / "Telegram.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Telegram Desktop" / "Telegram.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            subprocess.Popen([str(candidate)])
            return
    try:
        os.startfile("tg://resolve")
        return
    except (OSError, AttributeError):
        # Keep the voice command useful when only Telegram Web is available.
        webbrowser.open("https://web.telegram.org/")


def open_discord():
    os.system("start discord")


def open_steam():
    os.system("start steam")


def open_settings():
    os.system("start ms-settings:")


def open_system_settings():
    global COMMAND_FEEDBACK
    COMMAND_FEEDBACK = "Открываю параметры Windows."
    open_settings()


def computer_info():
    global COMMAND_FEEDBACK
    try:
        import psutil
        memory_gb = psutil.virtual_memory().total / (1024 ** 3)
        COMMAND_FEEDBACK = f"Память компьютера: {memory_gb:.1f} гигабайт."
    except Exception:
        COMMAND_FEEDBACK = "Информация о компьютере временно недоступна."
    return True


def open_calculator():
    os.system("start calc.exe")


def open_task_manager():
    os.system("start taskmgr.exe")


def open_device_manager():
    os.system("start devmgmt.msc")


def open_disk_management():
    os.system("start diskmgmt.msc")


def open_bible():
    webbrowser.open("https://www.jw.org/ru/%D0%B1%D0%B8%D0%B1%D0%BB%D0%B8%D1%8F/")


def _target_after_prefix(command: str, prefixes: tuple[str, ...]) -> str:
    value = command.lower().strip()
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix):].strip(" ,.!?")
    return value


def open_folder_from_command(command: str) -> bool:
    global COMMAND_FEEDBACK
    target = _target_after_prefix(command, ("открой папку", "открой каталог", "найди папку", "покажи папку", "перейди в папку", "мне нужна папка"))
    try:
        path = FILESYSTEM.open_folder(target)
        COMMAND_FEEDBACK = f"Открываю папку {path.name}."
    except AmbiguousPathError as error:
        options = "; ".join(str(item) for item in error.candidates[:2])
        COMMAND_FEEDBACK = f"Нашёл несколько папок {error.query}. Уточните вариант: {options}."
    except FileNotFoundError:
        COMMAND_FEEDBACK = f"Папку {target} найти не удалось."
    return True


def launch_application_from_command(command: str) -> bool:
    global COMMAND_FEEDBACK
    target = _target_after_prefix(command, ("открой", "запусти", "включи"))
    try:
        item = APPLICATIONS.launch(target)
        COMMAND_FEEDBACK = f"Запускаю {item['name']}."
    except FileNotFoundError:
        COMMAND_FEEDBACK = f"Приложение {target} не найдено на этом компьютере."
    return True


def show_desktop():
    pyautogui.hotkey("win", "d")


def close_window():
    pyautogui.hotkey("alt", "f4")


def make_screenshot():

    screenshot = pyautogui.screenshot()

    filename = f"screenshot_{datetime.datetime.now().strftime('%H_%M_%S')}.png"

    screenshot.save(filename)

    print("Скриншот сохранен:", filename)


def shutdown_pc():
    os.system("shutdown /s /t 1")


def reboot_pc():
    os.system("shutdown /r /t 1")


def set_system_mute(muted):
    """Mute/unmute the current Windows output endpoint."""
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMute(1 if muted else 0, None)


def run_custom_command(script_name):
    """Run a bundled command script when the matching .exe/.ahk exists."""
    root = Path(BASE_DIR) / "voice_engine" / "custom-commands"
    for suffix in (".exe", ".ahk"):
        path = root / f"{script_name}{suffix}"
        if path.is_file():
            if suffix == ".exe":
                subprocess.Popen([str(path)])
            else:
                os.startfile(str(path))
            return
    raise FileNotFoundError(f"Командный скрипт не найден: {script_name}")


# ---------------------------------------------
# intent → действие
# ---------------------------------------------

ACTIONS = {

    "open_browser": open_browser,
    "open_google": open_google,
    "open_youtube": open_youtube,
    "music": open_music,
    "open_music_service": open_music,

    "open_telegram": open_telegram,
    "open_discord": open_discord,
    "open_steam": open_steam,
    "open_bible": open_bible,
    "open_system_settings": open_system_settings,
    "computer_info": computer_info,
    "open_productivity": open_calculator,

    "weather": open_weather,
    "currency_dollar": open_dollar,

    "show_desktop": show_desktop,
    "close_window": close_window,
    "screenshot": make_screenshot,

    "shutdown": shutdown_pc,
    "reboot": reboot_pc,
    "sound_on": lambda: set_system_mute(False),
    "sound_off": lambda: set_system_mute(True),
    "music_next": lambda: run_custom_command("Next music"),
    "music_prev": lambda: run_custom_command("Prev music"),
    "music_off": lambda: run_custom_command("Stop music"),
    "music_save": lambda: run_custom_command("Save music"),
    "gaming_mode_on": lambda: run_custom_command("Switch to gaming mode"),
    "gaming_mode_off": lambda: run_custom_command("Switch back to workspace"),
    "switch_to_headphones": lambda: run_custom_command("Switch to headphones"),
    "switch_to_dynamics": lambda: run_custom_command("Switch to dynamics"),
}


# ---------------------------------------------
# обучение новой команды
# ---------------------------------------------

def learn_command(command, intent):

    if intent not in COMMANDS:
        print("Неизвестный intent:", intent)
        return

    if command not in COMMANDS[intent]:

        COMMANDS[intent].append(command)

        with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(COMMANDS, f, allow_unicode=True)

        print("Jarvis выучил новую команду:", command)


# ---------------------------------------------
# поиск интента
# ---------------------------------------------

def find_intent(command):
    normalized = " ".join(str(command or "").lower().split())
    command_tokens = set(normalized.split())
    best_score = 0
    best_intent = None

    for intent, phrases in COMMANDS.items():
        for phrase in phrases:
            phrase_normalized = " ".join(str(phrase).lower().split())
            phrase_tokens = set(phrase_normalized.split())
            if not phrase_tokens:
                continue

            # Keep natural variants such as "открой браузер пожалуйста", but
            # do not route a conversation to a command merely because it
            # shares one generic word like "сегодня".
            contains_phrase = phrase_normalized in normalized
            overlap = len(command_tokens & phrase_tokens) / len(phrase_tokens)
            score = fuzz.token_set_ratio(normalized, phrase_normalized)
            accepted = contains_phrase or (overlap >= 0.75 and score >= 70)
            if accepted and score > best_score:
                best_score = score
                best_intent = intent

    return best_intent


# ---------------------------------------------
# контекстные команды
# ---------------------------------------------

def context_command(command):

    global LAST_CONTEXT

    if LAST_CONTEXT == "music":

        if "следующий" in command or "дальше" in command:
            os.system("Next_music.exe")
            return True

        if "предыдущий" in command:
            os.system("Prev_music.exe")
            return True

        if "стоп" in command:
            os.system("Stop_music.exe")
            return True

    return False


# ---------------------------------------------
# основной запуск команды
# ---------------------------------------------

def run_command(command):

    global LAST_CONTEXT
    global LAST_CONTEXT_TIME
    global LEARNING_MODE
    global UNKNOWN_COMMAND
    global COMMAND_FEEDBACK
    global PENDING_CONFIRMATION

    command = command.lower()
    COMMAND_FEEDBACK = ""

    if PENDING_CONFIRMATION:
        if command.strip() in {"да", "подтверждаю", "подтвердить", "выполняй"}:
            intent = PENDING_CONFIRMATION
            PENDING_CONFIRMATION = None
            action = ACTIONS.get(intent)
            if action:
                action()
                COMMAND_FEEDBACK = "Подтверждение получено. Команда выполнена."
                return True
        if command.strip() in {"нет", "отмена", "отменить", "не надо"}:
            PENDING_CONFIRMATION = None
            COMMAND_FEEDBACK = "Команда отменена."
            return True
        COMMAND_FEEDBACK = "Ожидаю подтверждение: скажите «да» или «нет»."
        return True


    # -----------------------------------------
    # режим обучения
    # -----------------------------------------

    if LEARNING_MODE:

        intent = command.strip()

        learn_command(UNKNOWN_COMMAND, intent)

        LEARNING_MODE = False
        UNKNOWN_COMMAND = None

        return True


    # -----------------------------------------
    # сброс контекста
    # -----------------------------------------

    if time.time() - LAST_CONTEXT_TIME > CONTEXT_TIMEOUT:
        LAST_CONTEXT = None

    # Local file/application actions are resolved before Ollama. Existing
    # exact command intents keep their established handlers.
    known_intent = find_intent(command)
    if any(command.startswith(prefix) for prefix in ("открой папку", "открой каталог", "найди папку", "покажи папку", "перейди в папку", "мне нужна папка")):
        return open_folder_from_command(command)
    if known_intent is None and any(command.startswith(prefix) for prefix in ("открой ", "запусти ", "включи ")):
        if APPLICATIONS.find(command) or any(alias in command for aliases in APP_ALIASES.values() for alias in aliases):
            return launch_application_from_command(command)


    # -----------------------------------------
    # google поиск
    # -----------------------------------------

    if "найди" in command:

        query = command.replace("найди", "").strip()

        if query:

            webbrowser.open(
                f"https://www.google.com/search?q={query}"
            )

        return True


    # -----------------------------------------
    # напоминание
    # -----------------------------------------

    if "напомни" in command:

        numbers = re.findall(r"\d+", command)

        if numbers:

            minutes = int(numbers[0])

            remind_time = time.time() + minutes * 60

            REMINDERS.append(remind_time)

            print(f"Напоминание через {minutes} минут")

        return True


    # -----------------------------------------
    # поиск интента
    # -----------------------------------------

    intent = known_intent or find_intent(command)

    if intent in {"shutdown", "reboot"}:
        PENDING_CONFIRMATION = intent
        COMMAND_FEEDBACK = "Это прерывающая системная команда. Подтвердите выполнение словами «да» или «нет»."
        return True


    # -----------------------------------------
    # если команда неизвестна
    # -----------------------------------------

    if not intent:

        if context_command(command):
            return True

        print("Jarvis: не знаю такую команду")

        LEARNING_MODE = True
        UNKNOWN_COMMAND = command

        print("Скажи intent команды")

        return True


    print("INTENT:", intent)


    action = ACTIONS.get(intent)

    if action:

        action()

        LAST_CONTEXT = intent
        LAST_CONTEXT_TIME = time.time()

        return True


    return False


def get_last_command_feedback() -> str:
    return COMMAND_FEEDBACK


def has_pending_confirmation() -> bool:
    return bool(PENDING_CONFIRMATION)
