allowed = set(" абвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789!?.,:%-()")

with open("metadata.csv", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):

        parts = line.strip().split("|")

        if len(parts) < 2:
            print("ПЛОХАЯ СТРОКА:", line)
            continue

        text = parts[1].lower()

        bad = [c for c in text if c not in allowed]

        if bad:
            print(f"СТРОКА {i}:")
            print("ТЕКСТ:", text)
            print("ПЛОХИЕ СИМВОЛЫ:", bad)
            print()