bad = {
"0008","0009","0109","0110","0111","0112","0113",
"0114","0115","0117","0118","0119","0120","0157"
}

lines = []

with open("metadata.csv", encoding="utf-8") as f:
    for line in f:
        name = line.split("|")[0]

        if name not in bad:
            lines.append(line)

with open("metadata_fixed.csv","w",encoding="utf-8") as f:
    for l in lines:
        f.write(l)

print("Осталось:", len(lines))