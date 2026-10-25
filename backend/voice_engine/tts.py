import sounddevice as sd
import soundfile as sf
import tempfile
from TTS.api import TTS

# модель XTTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

# WAV с твоим голосом
VOICE_SAMPLE = "voice_dataset/voice.wav"


def speak(text: str):

    try:

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name

        tts.tts_to_file(
            text=text,
            speaker_wav=VOICE_SAMPLE,
            language="ru",
            file_path=path
        )

        audio, sr = sf.read(path)

        sd.play(audio, sr)
        sd.wait()

    except Exception as e:

        print("TTS ошибка:", e)