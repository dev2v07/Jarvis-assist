import re

path = r"C:\projects\Jarvis\backend\voice_engine\dataset\metadata.csv"

lines = open(path, encoding="utf8").read().splitlines()

fixed = []

for line in lines:

    parts = line.split("|")

    parts[0] = parts[0].replace(".wav", "")

    fixed.append("|".join(parts))

open(path, "w", encoding="utf8").write("\n".join(fixed))

print("metadata fixed")