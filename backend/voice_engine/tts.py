import sounddevice as sd
import soundfile as sf
import io
import tempfile
import os
import threading
from pathlib import Path
try:
    from .voice_models import VoiceModelManager
except ImportError:  # legacy scripts import this module from voice_engine directly
    from voice_models import VoiceModelManager
try:
    from TTS.api import TTS
    TTS_IMPORT_ERROR = None
except ImportError as error:
    TTS = None
    TTS_IMPORT_ERROR = error

# Load XTTS lazily so the backend can start while the voice model is warming up.
_tts = None
_voice_models = VoiceModelManager(Path(__file__).resolve().parent.parent)
TTS_MODEL = os.getenv("JARVIS_TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
VOICE_SAMPLE = os.getenv(
    "JARVIS_VOICE_SAMPLE",
    str(Path(__file__).resolve().parent / "sound" / "Да сэр.wav"),
)


def _get_tts():
    global _tts
    if TTS is None:
        raise RuntimeError(f"TTS dependency is unavailable: {TTS_IMPORT_ERROR}")
    if _tts is None:
        _tts = TTS(TTS_MODEL)
    return _tts


def voice_models_status():
    return _voice_models.status()


def select_voice_model(model_id: str):
    return _voice_models.select(model_id)


def close_voice_models():
    _voice_models.close()


def _play_audio(audio, sr: int):
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    sd.play(audio, sr)
    waiter = threading.Thread(target=sd.wait, name="jarvis-tts-wait", daemon=True)
    waiter.start()
    playback_timeout = max(8.0, min(45.0, len(audio) / float(sr) + 8.0))
    waiter.join(timeout=playback_timeout)
    if waiter.is_alive():
        sd.stop()


def speak(text: str, model_id: str | None = None):
    selected_id = model_id or _voice_models.selected_id
    if selected_id == "kesha":
        audio, sample_rate = _voice_models.synthesize_kesha(text)
        _play_audio(audio, sample_rate)
        return
    if selected_id in {"fish_jarvis", "fish_dean"}:
        profile = "dean" if selected_id == "fish_dean" else "jarvis"
        audio_bytes = _voice_models.synthesize_fish(text, profile=profile)
        audio, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        _play_audio(audio, sample_rate)
        return

    sample = Path(VOICE_SAMPLE)
    if not sample.is_file():
        raise FileNotFoundError(f"Voice sample not found: {sample}")

    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name

        _get_tts().tts_to_file(
            text=text,
            speaker_wav=str(sample),
            language="ru",
            file_path=path,
        )

        audio, sr = sf.read(path)
        _play_audio(audio, sr)
    finally:
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
