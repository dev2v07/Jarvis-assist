import os
import librosa
import soundfile as sf
import numpy as np

dataset_path = "C:/projects/Jarvis/backend/voice_engine/dataset"
wav_path = os.path.join(dataset_path, "wavs")
meta_file = os.path.join(dataset_path, "metadata.csv")

files = sorted(os.listdir(wav_path))

new_lines = []

with open(meta_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

index = len(files)

for line in lines:

    name, text, text2 = line.strip().split("|")
    wav_file = os.path.join(wav_path, name)

    y, sr = librosa.load(wav_file, sr=None)

    variations = []

    # speed up
    variations.append(librosa.effects.time_stretch(y, rate=1.1))

    # slow down
    variations.append(librosa.effects.time_stretch(y, rate=0.9))

    # pitch up
    variations.append(librosa.effects.pitch_shift(y, sr=sr, n_steps=1))

    # pitch down
    variations.append(librosa.effects.pitch_shift(y, sr=sr, n_steps=-1))

    # louder
    variations.append(y * 1.1)

    # quieter
    variations.append(y * 0.9)

    for var in variations:

        new_name = f"{index:04d}"
        new_path = os.path.join(wav_path, f"{new_name}.wav")

        sf.write(new_path, var, sr)

        new_lines.append(f"{new_name}|{text}|{text2}\n")

        index += 1


with open(meta_file, "a", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Dataset augmented!")
print("New files:", len(new_lines))