import os
import librosa

meta = "metadata.csv"
wav_dir = "wavs"

good_lines = []

with open(meta, encoding="utf-8") as f:
    for line in f:
        name = line.split("|")[0]
        path = os.path.join(wav_dir, name + ".wav")

        if not os.path.exists(path):
            continue

        audio, sr = librosa.load(path, sr=None)
        duration = len(audio) / sr

        if duration >= 1.2:
            good_lines.append(line)

with open("metadata_filtered.csv", "w", encoding="utf-8") as f:
    for l in good_lines:
        f.write(l)

print("Оставили:", len(good_lines))