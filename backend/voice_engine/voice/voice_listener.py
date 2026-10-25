import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel


print("Загружаю модель распознавания...")

model = WhisperModel("base", compute_type="int8")

samplerate = 16000
duration = 3


def listen():

    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    audio = np.squeeze(audio)

    segments, _ = model.transcribe(audio)

    text = ""

    for segment in segments:
        text += segment.text

    return text.lower().strip()