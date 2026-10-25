import os
import time
import re
import random
import traceback
import requests

from voice_engine.voice_player import play_voice
from voice_engine.tts import speak as tts_speak
from voice_engine.record_command import record_command
from voice_engine.wakeword_engine import wait_wakeword

from computer_control import run_command
from config import VA_NAME


# ------------------------------------------------
# PATHS
# ------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
VOICE_DIR = os.path.join(BASE_DIR, "sound")

print("VOICE_DIR:", VOICE_DIR)


# ------------------------------------------------
# STATE
# ------------------------------------------------

IS_SPEAKING = False


# ------------------------------------------------
# LOAD VOICES
# ------------------------------------------------

def load_voices():

    if not os.path.exists(VOICE_DIR):
        print("Voice directory not found")
        return []

    voices = [
        f for f in os.listdir(VOICE_DIR)
        if f.endswith(".wav")
    ]

    print("Загружено голосов:", len(voices))

    return voices


voices = load_voices()


# ------------------------------------------------
# RESPONSES
# ------------------------------------------------

RESPONSES = {

    "wake": [
        "да сэр",
        "к вашим услугам сэр",
        "всегда к вашим услугам сэр"
    ],

    "thinking": [
        "загрузка",
        "начинаю диагностику системы"
    ],

    "success": [
        "есть",
        "запрос выполнен"
    ],

    "error": [
        "я вас не понял сэр",
        "повторите пожалуйста",
        "команда не распознана"
    ]
}


# ------------------------------------------------
# VOICE SEARCH
# ------------------------------------------------

def find_voice(keyword):

    keyword = keyword.lower()

    for voice in voices:

        name = voice.lower()

        if keyword in name:

            return os.path.join(VOICE_DIR, voice)

    return None


# ------------------------------------------------
# PLAY WAV
# ------------------------------------------------

def say(keyword):

    global IS_SPEAKING

    voice_path = find_voice(keyword)

    if not voice_path:
        print("Voice not found:", keyword)
        return False

    try:

        IS_SPEAKING = True

        play_voice(voice_path)

        return True

    except Exception as e:

        print("Voice error:", e)

        return False

    finally:

        time.sleep(0.2)

        IS_SPEAKING = False


# ------------------------------------------------
# EVENT SPEECH
# ------------------------------------------------

def speak(event):

    if event not in RESPONSES:
        return

    keyword = random.choice(RESPONSES[event])

    ok = say(keyword)

    if not ok:
        tts_speak(keyword)


# ------------------------------------------------
# AI SPEECH
# ------------------------------------------------

def speak_ai(text):

    global IS_SPEAKING

    try:

        IS_SPEAKING = True

        print("AI:", text)

        tts_speak(text)

    except Exception as e:

        print("TTS error:", e)

    finally:

        time.sleep(0.2)

        IS_SPEAKING = False


# ------------------------------------------------
# AI REQUEST
# ------------------------------------------------

def ask_ai(command):

    try:

        r = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": command},
            timeout=20
        )

        if r.status_code != 200:

            print("AI HTTP error:", r.status_code)

            return None

        data = r.json()

        return data.get("response")

    except Exception as e:

        print("AI error:", e)

        return None


# ------------------------------------------------
# TEXT NORMALIZE
# ------------------------------------------------

def normalize(text):

    text = text.lower()

    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


# ------------------------------------------------
# COMMAND PROCESS
# ------------------------------------------------

def process_command(text):

    command = normalize(text)

    print("Команда:", command)

    try:

        result = run_command(command)

        if result:

            speak("success")

            return True

    except Exception as e:

        print("run_command error:", e)

    return False


# ------------------------------------------------
# MAIN LOOP
# ------------------------------------------------

def main():

    print(f"{VA_NAME} готов")

    while True:

        try:

            print("\nОжидание 'Jarvis'")

            wait_wakeword()

            speak("wake")

            time.sleep(0.3)

            text = record_command()

            if not text:

                speak("error")
                continue

            print("Услышано:", text)

            speak("thinking")

            if process_command(text):
                continue

            answer = ask_ai(text)

            if answer:

                speak_ai(answer)

            else:

                speak("error")

        except Exception as e:

            print("Main loop error:", e)
            traceback.print_exc()


# ------------------------------------------------
# START
# ------------------------------------------------

if __name__ == "__main__":

    while True:

        try:

            main()

        except Exception as e:

            print("Jarvis restart:", e)
            traceback.print_exc()

            time.sleep(2)