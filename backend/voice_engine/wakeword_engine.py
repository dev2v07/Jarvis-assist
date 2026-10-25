import sounddevice as sd
import numpy as np
import time
import librosa
import torch

from openwakeword.model import Model
from silero_vad import load_silero_vad, get_speech_timestamps


# ------------------------------------------------
# CONFIG
# ------------------------------------------------

MODEL_SR = 16000
CHUNK = 2048
THRESHOLD = 0.40

COOLDOWN = 1.2


# ------------------------------------------------
# LOAD MODELS
# ------------------------------------------------

print("Загрузка wakeword модели...")

wake_model = Model(
    wakeword_models=["hey_jarvis_v0.1"]
)

print("Загрузка VAD...")

vad_model = load_silero_vad()

print("Wakeword система готова")


# ------------------------------------------------
# FIND MICROPHONE
# ------------------------------------------------

def find_microphone():

    devices = sd.query_devices()

    for i, dev in enumerate(devices):

        if dev["max_input_channels"] > 0:

            print(f"Микрофон найден: {dev['name']} (id={i})")

            return i, int(dev["default_samplerate"])

    raise RuntimeError("Микрофон не найден")


DEVICE_ID, DEVICE_SR = find_microphone()


# ------------------------------------------------
# RESAMPLE
# ------------------------------------------------

def resample(audio):

    if DEVICE_SR == MODEL_SR:
        return audio

    return librosa.resample(
        audio,
        orig_sr=DEVICE_SR,
        target_sr=MODEL_SR
    )


# ------------------------------------------------
# VAD CHECK
# ------------------------------------------------

def has_voice(audio):

    timestamps = get_speech_timestamps(
        torch.from_numpy(audio),
        vad_model,
        sampling_rate=MODEL_SR
    )

    return len(timestamps) > 0


# ------------------------------------------------
# WAKEWORD LOOP
# ------------------------------------------------

def wait_wakeword():

    print("🟢 Jarvis слушает...")

    last_trigger = 0

    with sd.InputStream(
        samplerate=DEVICE_SR,
        channels=1,
        blocksize=CHUNK,
        dtype="float32",
        device=DEVICE_ID
    ) as stream:

        while True:

            audio, status = stream.read(CHUNK)

            if status:
                print("Audio warning:", status)

            audio = np.squeeze(audio)

            audio = resample(audio)

            if not has_voice(audio):
                continue

            prediction = wake_model.predict(audio)

            if not prediction:
                continue

            score = max(prediction.values())

            print("wake score:", round(score, 3))

            now = time.time()

            if score > THRESHOLD and now - last_trigger > COOLDOWN:

                print("⚡ Jarvis активирован")

                last_trigger = now

                return