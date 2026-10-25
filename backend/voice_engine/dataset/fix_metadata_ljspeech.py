import csv

inp = "metadata.csv"
out = "metadata_fixed.csv"

rows = []

with open(inp, encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("|")
        if len(parts) >= 2:
            wav = parts[0].replace(".wav","") + ".wav"
            text = parts[1]
            rows.append(f"{wav}|{text}|{text}")

with open(out, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(r + "\n")

print("готово")