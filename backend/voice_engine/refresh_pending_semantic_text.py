"""Improve only not-yet-generated variants in the semantic queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data" / "Bible" / "materials" / "voice_responses" / "questions.json"

TEMPLATES = {
    "instant": (
        "«{primary}» — хороший повод разложить всё по полочкам.",
        "Сначала отвечу коротко; затем поясню, что важно учесть в теме «{primary}».",
        "У меня есть план: начать с сути вопроса «{primary}» и перейти к практическим деталям.",
        "Готовлю для вас разбор. В центре внимания — «{primary}».",
    ),
    "ack": (
        "Запрос услышан: «{primary}». Перехожу к делу.",
        "Сейчас займусь этим поручением — «{primary}».",
        "Отмечаю задачу и начинаю работу. Речь о запросе «{primary}».",
        "Поручение принято. Проверяю первый шаг для «{primary}».",
    ),
    "dynamic": (
        "«{primary}» — хороший вопрос; разложу ответ по понятным пунктам.",
        "Сначала дам основу, затем добавлю нюансы к теме «{primary}».",
        "Подбираю содержательный ответ. Отправная точка — вопрос «{primary}».",
        "Сейчас проведу небольшой разбор: в центре будет «{primary}».",
    ),
}


def main() -> int:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    changed = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for intent in data.get("intents", []):
        rows = [row for row in intent.get("responses", []) if str(row.get("status")) in {"pending", "generating"}]
        if not rows:
            continue
        templates = TEMPLATES.get(str(intent.get("class", "dynamic")), TEMPLATES["dynamic"])
        primary = str(intent.get("primary_question", "ваш вопрос")).strip().rstrip(".!?")
        for row, template in zip(rows, templates):
            text = template.format(primary=primary)
            if row.get("text") != text:
                row["text"] = text
                row["created_at"] = row.get("created_at") or now
                changed += 1
    temporary = QUESTIONS.with_suffix(QUESTIONS.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(QUESTIONS)
    print(json.dumps({"changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
