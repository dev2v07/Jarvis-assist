import sounddevice as sd
import numpy as np
import os


def record_command(duration=2, samplerate=16000, mic_index=None):

    print("🎤 слушаю команду...")

    if mic_index is None:
        configured = os.getenv("JARVIS_MICROPHONE_INDEX", "-1")
        mic_index = None if configured in ("", "-1") else int(configured)

    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=mic_index
    )

    sd.wait()

    return np.squeeze(audio)
