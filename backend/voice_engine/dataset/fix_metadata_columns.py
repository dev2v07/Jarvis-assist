lines = []

with open("voice_engine/dataset/metadata.csv", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("|")

        if len(parts) == 2:
            audio = parts[0]
            text = parts[1]

            lines.append(f"{audio}|{text}|{text}")

        elif len(parts) >= 3:
            lines.append(line.strip())

with open("voice_engine/dataset/metadata_fixed.csv", "w", encoding="utf-8") as f:
    for l in lines:
        f.write(l + "\n")

print("Готово. Строк:", len(lines))