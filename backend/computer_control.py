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

    command = command.lower()


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

    intent = find_intent(command)


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
