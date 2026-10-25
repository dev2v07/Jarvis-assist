allowed = set(" абвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789!?.,:%-()")

clean_lines = []

with open("metadata.csv", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        wav = parts[0]
        text = parts[1].lower()

        text = "".join(c for c in text if c in allowed)

        if len(parts) == 3:
            clean_lines.append(f"{wav}|{text}|{text}")
        else:
            clean_lines.append(f"{wav}|{text}")

with open("metadata_clean.csv", "w", encoding="utf-8") as f:
    for l in clean_lines:
        f.write(l + "\n")

print("Готово! metadata_clean.csv создан.")