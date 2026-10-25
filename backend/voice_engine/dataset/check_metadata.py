with open("metadata.csv", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        parts = line.strip().split("|")

        if len(parts) < 2:
            print("ПЛОХАЯ СТРОКА:", i)
            continue

        text = parts[1].strip()

        if len(text) < 2:
            print("СЛИШКОМ КОРОТКИЙ ТЕКСТ:", i, text)