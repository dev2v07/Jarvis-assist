import csv
import string

allowed = set(
" абвгдеёжзийклмнопрстуфхцчшщьыъэюя"
"abcdefghijklmnopqrstuvwxyz"
"0123456789"
"!?,.:;%()-\"'"
)

bad_lines = []

with open(r"C:\projects\Jarvis\backend\voice_engine\dataset\metadata.csv", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter="|")

    for i,row in enumerate(reader):
        text = row[1]

        for c in text:
            if c not in allowed:
                bad_lines.append((i, c, text))

print("BAD LINES:")

for b in bad_lines:
    print(b)