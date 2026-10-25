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
# PATHS
# ------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
VOICE_DIR = os.path.join(BASE_DIR, "sound")

print("VOICE_DIR:", VOICE_DIR)


# ------------------------------------------------
# STATES
# ------------------------------------------------

IS_SPEAKING = False

samplerate = 16000
CHUNK = 1280


# ------------------------------------------------
# MICROPHONE
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

    return MICROPHONE_INDEX


MIC_INDEX = show_microphones()


# ------------------------------------------------
# WHISPER
# ------------------------------------------------

print("Загрузка Whisper...")

model = WhisperModel(
    "tiny",
    compute_type="int8"
)

print("Whisper готов")


# ------------------------------------------------
# WAKE WORD MODEL
# ------------------------------------------------

print("Загрузка wakeword модели...")

wake_model = Model(
    wakeword_models=["hey_jarvis_v0.1"]
)

print("Wake word модель готова")


# ------------------------------------------------
# VOICES
# ------------------------------------------------

voices = []

if os.path.exists(VOICE_DIR):
    voices = [v for v in os.listdir(VOICE_DIR) if v.endswith(".wav")]


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
# VOICE OUTPUT
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

    finally:

        time.sleep(0.4)
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

    finally:

        time.sleep(0.4)
        IS_SPEAKING = False


# ------------------------------------------------
# RECORD COMMAND
# ------------------------------------------------

def record_command(duration=1.6):

    print("🎤 Jarvis слушает команду...")

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
# TRANSCRIBE
# ------------------------------------------------

def transcribe(audio):

    print("🧠 Whisper обрабатывает аудио...")

    segments, _ = model.transcribe(
        audio,
        language="ru",
        beam_size=1,
        vad_filter=True
    )

    text = ""

    for seg in segments:
        text += seg.text

    text = text.lower().strip()

    print("🧠 Whisper услышал:", text)

    return text


# ------------------------------------------------
# AI
# ------------------------------------------------

def ask_ai(command):

    print("📡 Отправка команды в AI:", command)

    try:

        r = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": command},
            timeout=10
        )

        answer = r.json().get("response")

        print("🤖 AI ответ:", answer)

        return answer

    except Exception as e:

        print("AI error:", e)
        return None


# ------------------------------------------------
# WAKE WORD LISTENER
# ------------------------------------------------

def wait_wakeword():

    print("\n🟢 Jarvis слушает (ожидание wake word)")

    with sd.InputStream(
        samplerate=samplerate,
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

            audio = audio.flatten()

            prediction = wake_model.predict(audio)

            if not prediction:
                continue

            score = max(prediction.values())

            print("🎧 Wake model слышит:", prediction, "max:", score)

            if score > 0.35:

                print("⚡ Jarvis активирован")

                return


# ------------------------------------------------
# MAIN LOOP
# ------------------------------------------------

def main():

    while True:

        wait_wakeword()

        speak("wake")

        audio = record_command()

        text = transcribe(audio)

        if not text:
            print("⚠ Whisper ничего не понял")
            continue

        print("📢 Команда:", text)

        speak("thinking")

        command = re.sub(r"[^\w\s]", "", text).strip().lower()

        print("⚙ Обработанная команда:", command)

        try:

            print("🔎 Проверка YAML команд...")

            result = run_command(command)

            if result:
                print("✅ Команда выполнена через YAML")
                speak("success")
                continue

        except Exception as e:

            print("run_command error:", e)

        print("🧠 YAML не нашёл команду, отправляем в AI")

        answer = ask_ai(command)

        if answer:
            speak_ai(answer)
        else:
            speak("error")


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