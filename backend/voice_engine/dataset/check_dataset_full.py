import os

meta = "metadata.csv"
wav_folder = "wavs"

with open(meta, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):

        parts = line.strip().split("|")

        if len(parts) < 2:
            print("ПЛОХАЯ СТРОКА:", i)
            continue

        wav = parts[0]
        text = parts[1]

        path = os.path.join(wav_folder, wav + ".wav")

        if not os.path.exists(path):
            print("НЕТ WAV:", wav)

        if len(text.strip()) == 0:
            print("ПУСТОЙ ТЕКСТ:", i)