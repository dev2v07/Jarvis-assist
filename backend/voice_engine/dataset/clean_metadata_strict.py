import re

allowed = re.compile(r"[а-яёА-ЯЁ .,!?-]")

clean = []

with open("metadata.csv", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("|")

        if len(parts) < 2:
            continue

        audio = parts[0]
        text = parts[1]

        text = "".join(c for c in text if allowed.match(c))
        text = text.strip()

        if len(text) < 3:
            continue

        clean.append(f"{audio}|{text}|{text}")

with open("metadata_clean.csv","w",encoding="utf-8") as f:
    for l in clean:
        f.write(l+"\n")

print("OK:", len(clean))