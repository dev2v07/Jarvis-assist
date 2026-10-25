replace = {
    "a": "а",
    "c": "с",
    "e": "е",
    "o": "о",
    "p": "р",
    "x": "х",
    "y": "у",
    "d": "д",
    "k": "к",
    "m": "м",
    "t": "т",
    "b": "в",
    "h": "н"
}

lines = []

with open("metadata.csv", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        wav = parts[0]
        text = parts[1].lower()

        # если есть третья колонка
        norm = parts[2].lower() if len(parts) > 2 else text

        for latin, rus in replace.items():
            text = text.replace(latin, rus)
            norm = norm.replace(latin, rus)

        lines.append(f"{wav}|{text}|{norm}")

with open("metadata_fixed.csv", "w", encoding="utf-8") as f:
    for l in lines:
        f.write(l + "\n")

print("Готово. metadata_fixed.csv создан.")