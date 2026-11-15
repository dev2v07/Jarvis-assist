"""Add a bounded first batch of semantic response variants.

Only new response records and new WAV paths are added. Existing records and
audio files are left byte-for-byte untouched; generation is performed later by
``generate_voice_library.py`` in a bounded batch.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data" / "Bible" / "materials" / "voice_responses" / "questions.json"

VARIANTS = {
    "greetings_001": [
        "Привет, сэр. Я уже в строю — с чего начнём?",
        "Рад вас слышать. Jarvis готов заняться делом.",
        "С возвращением, сэр. Могу принять первую задачу.",
        "Приветствую. Я на связи и внимательно слушаю.",
    ],
    "presence_001": [
        "Да, сэр, я здесь и внимательно вас слушаю.",
        "На связи. Можете говорить, я готов принять запрос.",
        "Я рядом, сэр. Голосовой канал работает.",
        "Слышу вас отлично и готов продолжать.",
    ],
    "mood_001": [
        "Системы в норме, настроение рабочее. Чем займёмся?",
        "Всё стабильно, сэр. Готов помочь или просто поговорить.",
        "Я в отличной форме и настроен продуктивно.",
        "Работаю спокойно и уверенно. Спасибо, что спросили.",
    ],
    "gratitude_001": [
        "Всегда рад помочь, сэр.",
        "Обращайтесь — для этого я и здесь.",
        "Рад, что пригодился. Продолжаем, когда будете готовы.",
        "С удовольствием. Если понадобится ещё что-то — скажите.",
    ],
    "farewell_001": [
        "До связи, сэр. Я останусь готов к следующему обращению.",
        "Хорошего дня. Возвращайтесь, когда понадобится помощь.",
        "До скорого, сэр. Рабочий канал можно считать закрытым.",
        "Отдыхайте. Jarvis будет ждать следующей задачи.",
    ],
}


def main() -> int:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = 0
    for intent in data.get("intents", []):
        intent_id = str(intent.get("id", ""))
        texts = VARIANTS.get(intent_id, [])
        if not texts:
            continue
        existing = {str(item.get("text", "")).strip() for item in intent.get("responses", [])}
        semantic_group = intent_id.rsplit("_", 1)[0]
        for offset, text in enumerate(texts, start=7):
            if text in existing:
                continue
            response_id = f"response_{offset:02d}"
            if any(item.get("id") == response_id for item in intent.get("responses", [])):
                continue
            intent.setdefault("responses", []).append({
                "id": response_id,
                "response_id": f"{intent_id}:{response_id}",
                "text": text,
                "wav": f"{semantic_group}/{intent_id}_response_{offset:02d}.wav",
                "status": "pending",
                "generation_status": "AUDIO_PENDING",
                "error": "",
                "semantic_group": semantic_group,
                "context_tags": [semantic_group, str(intent.get("class", "instant")), str(intent.get("category", ""))],
                "enabled": True,
                "created_at": now,
            })
            existing.add(text)
            added += 1
    temporary = QUESTIONS.with_suffix(QUESTIONS.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(QUESTIONS)
    print(json.dumps({"added": added, "intents": len(data.get("intents", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
