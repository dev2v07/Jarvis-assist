import os
import librosa
import soundfile as sf
import numpy as np

DATASET_DIR = r"C:\projects\Jarvis\backend\voice_engine\dataset"
SOURCE_DIR = os.path.join(DATASET_DIR, "wavs-исходники")

TARGET_DIR = os.path.join(DATASET_DIR, "wavs")

os.makedirs(TARGET_DIR, exist_ok=True)

files = [f for f in os.listdir(SOURCE_DIR) if f.endswith(".wav")]

metadata = []

TARGET_SR = 22050


def normalize(audio):

    peak = np.max(np.abs(audio))

    if peak > 0:
        audio = audio / peak

    return audio


for i, file in enumerate(files):

    src = os.path.join(SOURCE_DIR, file)

    new_name = f"{i:04d}.wav"

    dst = os.path.join(TARGET_DIR, new_name)

    print("processing:", file)

    audio, sr = librosa.load(src, sr=None)

    audio = librosa.to_mono(audio)

    audio = librosa.resample(audio, orig_sr=sr, target_sr=TARGET_SR)

    audio = normalize(audio)

    sf.write(dst, audio, TARGET_SR)

    text = file.replace(".wav", "")

    metadata.append(f"{new_name}|{text}|{text}")


with open(os.path.join(DATASET_DIR, "metadata.csv"), "w", encoding="utf8") as f:

    f.write("\n".join(metadata))


print("\nDataset готов")
print("Файлов обработано:", len(files))