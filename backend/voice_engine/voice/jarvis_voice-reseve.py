import sounddevice as sd
import numpy as np
import random
import requests
import os
import re
import time
import traceback

from faster_whisper import WhisperModel
from openwakeword.model import Model

from voice_engine.voice_player import play_voice
from voice_engine.tts import speak as tts_speak
from computer_control import run_command

from config import WAKE_WORDS, MICROPHONE_INDEX, VA_NAME


# ------------------------------------------------
# пути
# ------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
VOICE_DIR = os.path.join(BASE_DIR, "sound")

print("VOICE_DIR:", VOICE_DIR)


# ------------------------------------------------
# состояния
# ------------------------------------------------

IS_SPEAKING = False


# ------------------------------------------------
# микрофоны
# ------------------------------------------------

def show_microphones():

    devices = sd.query_devices()

    print("\n====== МИКРОФОНЫ ======\n")

    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            print(f"[{i}] {dev['name']}")

    print()

    if MICROPHONE_INDEX is None:

        default = sd.default.device[0]

        print("Используется системный микрофон:")
        print(f"[{default}] {devices[default]['name']}\n")

        return default

    try:

        print("Используется микрофон:")
        print(f"[{MICROPHONE_INDEX}] {devices[MICROPHONE_INDEX]['name']}\n")

        return MICROPHONE_INDEX

    except:

        print("Ошибка выбора микрофона. Используется системный.")

        return sd.default.device[0]


MIC_INDEX = show_microphones()


# ------------------------------------------------
# Whisper
# ------------------------------------------------

print("Загружаю модель распознавания...")

model = WhisperModel(
    "tiny",
    compute_type="int8"
)

samplerate = 16000

print(f"{VA_NAME} готов\n")


# ------------------------------------------------
# WakeWord
# ------------------------------------------------

wake_model = Model(
    inference_framework="onnx"
)

CHUNK = 1280


# ------------------------------------------------
# загрузка голосов
# ------------------------------------------------

voices = []

if os.path.exists(VOICE_DIR):
    voices = [v for v in os.listdir(VOICE_DIR) if v.endswith(".wav")]


# ------------------------------------------------
# ответы
# ------------------------------------------------

RESPONSES = {

    "wake": [
        "да сэр",
        "к вашим услугам сэр",
        "всегда к вашим услугам сэр"
    ],

    "thinking": [
        "загружаю сэр",
        "начинаю диагностику системы"
    ],

    "success": [
        "есть",
        "выполнено сэр"
    ],

    "error": [
        "другой информации нет",
        "к сожалению сэр"
    ]
}


# ------------------------------------------------
# голос
# ------------------------------------------------

def get_voice(keyword):

    matches = [v for v in voices if keyword in v.lower()]

    if not matches:
        return None

    return random.choice(matches)


def say(keyword):

    global IS_SPEAKING

    voice = get_voice(keyword)

    if not voice:
        print("voice not found:", keyword)
        return

    try:

        IS_SPEAKING = True
        play_voice(voice)

    except Exception as e:

        print("voice error:", e)

    finally:

        IS_SPEAKING = False


def speak(event):

    if event not in RESPONSES:
        return

    keyword = random.choice(RESPONSES[event])
    say(keyword)


def speak_ai(text):

    global IS_SPEAKING

    try:

        IS_SPEAKING = True
        print("🧠 TTS:", text)
        tts_speak(text)

    except Exception as e:

        print("TTS error:", e)

    finally:

        IS_SPEAKING = False


# ------------------------------------------------
# запись команды
# ------------------------------------------------

def record_command(duration=2):

    print("🎤 слушаю команду...")

    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=MIC_INDEX
    )

    sd.wait()

    return np.squeeze(audio)


# ------------------------------------------------
# распознавание
# ------------------------------------------------

def transcribe(audio):

    segments, _ = model.transcribe(
        audio,
        language="ru",
        beam_size=1,
        vad_filter=True
    )

    text = ""

    for seg in segments:
        text += seg.text

    return text.lower().strip()


# ------------------------------------------------
# AI
# ------------------------------------------------

def ask_ai(command):

    try:

        r = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": command},
            timeout=10
        )

        return r.json().get("response")

    except Exception as e:

        print("AI error:", e)

        return None


# ------------------------------------------------
# wake word
# ------------------------------------------------

def wait_wakeword():

    print("🟢 Ожидание wake word...")

    with sd.InputStream(
        samplerate=16000,
        channels=1,
        blocksize=CHUNK,
        dtype="int16",
        device=MIC_INDEX
    ) as stream:

        while True:

            if IS_SPEAKING:
                time.sleep(0.1)
                continue

            audio, _ = stream.read(CHUNK)

            audio = np.frombuffer(audio, dtype=np.int16)

            prediction = wake_model.predict(audio)

            if not prediction:
                continue

            score = max(prediction.values())

            if score > 0.6:

                print("⚡ wake word:", prediction)

                return


# ------------------------------------------------
# главный цикл
# ------------------------------------------------

def main():

    while True:

        wait_wakeword()

        speak("wake")

        audio = record_command(2)

        text = transcribe(audio)

        if not text:
            continue

        print("📢 команда:", text)

        speak("thinking")

        command = re.sub(r"[^\w\s]", "", text).strip().lower()

        try:

            result = run_command(command)

            if result:
                speak("success")
                continue

        except Exception as e:

            print("run_command error:", e)

        answer = ask_ai(command)

        if answer:
            speak_ai(answer)
        else:
            speak("error")


# ------------------------------------------------
# запуск
# ------------------------------------------------

if __name__ == "__main__":

    while True:

        try:

            main()

        except Exception as e:

            print("Jarvis restart:", e)
            traceback.print_exc()
            time.sleep(2)