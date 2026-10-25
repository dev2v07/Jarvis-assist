import sounddevice as sd
import numpy as np


def record_command(duration=2, samplerate=16000, mic_index=None):

    print("🎤 слушаю команду...")

    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=mic_index
    )

    sd.wait()

    return np.squeeze(audio)