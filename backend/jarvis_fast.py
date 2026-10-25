import pvporcupine
import pyaudio
import struct
import numpy as np
import requests
import os

from faster_whisper import WhisperModel
from computer_control import run_command
from voice_player import play_voice


ACCESS_KEY = os.getenv("PICOVOICE_TOKEN")

if not ACCESS_KEY:
    raise RuntimeError("PICOVOICE_TOKEN is required to start the wake-word engine")

WAKE_WORD = "jarvis"

porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keywords=["jarvis"]
)

pa = pyaudio.PyAudio()

stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

print("Jarvis активирован")


whisper = WhisperModel("base", compute_type="int8")


def listen_command():

    print("Слушаю команду...")

    samplerate = 16000
    duration = 3

    audio = np.frombuffer(
        stream.read(samplerate * duration),
        dtype=np.int16
    )

    segments, _ = whisper.transcribe(audio)

    text = ""

    for seg in segments:
        text += seg.text

    return text.lower().strip()


def ask_ai(command):

    try:

        r = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": command}
        )

        return r.json()["response"]

    except:

        return None


while True:

    pcm = stream.read(porcupine.frame_length)

    pcm = struct.unpack_from(
        "h" * porcupine.frame_length,
        pcm
    )

    keyword_index = porcupine.process(pcm)

    if keyword_index >= 0:

        print("Jarvis!")

        play_voice("Есть.wav")

        command = listen_command()

        print("Команда:", command)

        action = run_command(command)

        if action:

            play_voice("Запрос выполнен сэр.wav")
            continue

        answer = ask_ai(command)

        if answer:

            print("Ответ:", answer)
            play_voice("Есть.wav")

        else:

            play_voice("К сожалению его невозможно синтезировать.wav")
