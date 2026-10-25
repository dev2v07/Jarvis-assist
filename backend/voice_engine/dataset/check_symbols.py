allowed = set(" абвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789!?.,:%-()")

with open("metadata.csv", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        text = parts[1].lower()

        for c in text:
            if c not in allowed:
                print("НЕИЗВЕСТНЫЙ СИМВОЛ:", c)