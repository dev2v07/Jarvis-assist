import torchaudio

torchaudio.set_audio_backend("soundfile")

print("Audio backend:", torchaudio.get_audio_backend())