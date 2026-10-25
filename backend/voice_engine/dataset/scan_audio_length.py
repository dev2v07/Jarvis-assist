import os
import librosa

dataset = "wavs"

bad = []

for file in os.listdir(dataset):
    if file.endswith(".wav"):
        path = os.path.join(dataset, file)

        audio, sr = librosa.load(path, sr=None)

        duration = len(audio) / sr

        if duration < 1.2:
            print("Слишком короткий:", file, duration)
            bad.append(file)

print("Найдено:", len(bad))