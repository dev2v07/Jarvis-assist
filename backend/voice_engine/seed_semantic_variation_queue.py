"""Queue four context-specific variants for intents still using shared text.

This only creates new pending records with new WAV names. It never edits an
existing response text or audio mapping, so the current runtime remains
backward compatible while the Fish Audio queue is processed in small batches.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data" / "Bible" / "materials" / "voice_responses" / "questions.json"
CORE_READY = {"greetings_001", "presence_001", "mood_001", "gratitude_001", "farewell_001"}

TEMPLATES = {
    "instant": (
        "Понял вопрос «{primary}». Отвечу по сути и без лишних отступлений.",
        "Давайте разберём тему «{primary}» — начну с главного.",
        "Вопрос принят. Сейчас сосредоточусь на теме «{primary}».",
        "Тема «{primary}» ясна. Подготовлю понятное объяснение.",
    ),
    "ack": (
        "Принято: «{primary}». Приступаю к выполнению.",
        "Задача «{primary}» у меня. Начинаю обработку.",
        "Понял поручение. Работаю над запросом «{primary}».",
        "Запрос зафиксирован — проверяю, как лучше выполнить «{primary}».",
    ),
    "dynamic": (
        "Хороший вопрос про «{primary}». Сейчас разложу ответ по шагам.",
        "Разберусь с темой «{primary}» и выделю самое полезное.",
        "Начинаю анализ вопроса «{primary}». Сначала дам краткую основу.",
        "Интересная тема: «{primary}». Подготовлю содержательный ответ.",
    ),
}


def main() -> int:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = 0
    for intent in data.get("intents", []):
        intent_id = str(intent.get("id", ""))
        if intent_id in CORE_READY:
            continue
        responses = intent.setdefault("responses", [])
        if len(responses) >= 10:
            continue
        intent_class = str(intent.get("class", "dynamic"))
        templates = TEMPLATES.get(intent_class, TEMPLATES["dynamic"])
        primary = str(intent.get("primary_question", "ваш вопрос")).strip().rstrip(".!?")
        semantic_group = intent_id.rsplit("_", 1)[0] or intent_id
        existing_texts = {str(item.get("text", "")).strip() for item in responses}
        next_number = 7
        for template in templates:
            if len(responses) >= 10:
                break
            text = template.format(primary=primary)
            if text in existing_texts:
                continue
            while any(str(item.get("id")) == f"response_{next_number:02d}" for item in responses):
                next_number += 1
            response_id = f"response_{next_number:02d}"
            responses.append({
                "id": response_id,
                "response_id": f"{intent_id}:{response_id}",
                "text": text,
                "wav": f"{semantic_group}/{intent_id}_response_{next_number:02d}.wav",
                "status": "pending",
                "generation_status": "AUDIO_PENDING",
                "error": "",
                "semantic_group": semantic_group,
                "context_tags": [semantic_group, intent_class, str(intent.get("category", ""))],
                "enabled": True,
                "created_at": now,
            })
            existing_texts.add(text)
            next_number += 1
            added += 1
    temporary = QUESTIONS.with_suffix(QUESTIONS.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(QUESTIONS)
    print(json.dumps({"added": added, "intents": len(data.get("intents", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
