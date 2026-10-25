from TTS.api import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

tts.tts_to_file(
    text="Здравствуйте сэр. Я готов к работе.",
    speaker_wav="voice_dataset/voice1.wav",
    language="ru",
    file_path="jarvis_voice.wav"
)