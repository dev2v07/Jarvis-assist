"""Repair the first library schema where intents shared the same WAV names."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "data" / "Bible" / "materials" / "voice_responses"
QUESTIONS = LIBRARY / "questions.json"
MANIFEST = LIBRARY / "manifest.json"


def main() -> None:
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    total = 0
    for intent in data.get("intents", []):
        category = str(intent["id"]).split("_", 1)[0]
        for response in intent.get("responses", []):
            response_number = str(response["id"]).rsplit("_", 1)[-1]
            response["wav"] = f"{category}/{intent['id']}_response_{response_number}.wav"
            response["status"] = "pending"
            response["duration"] = None
            response.pop("samplerate", None)
            response.pop("channels", None)
            response["error"] = ""
            total += 1
    QUESTIONS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST.write_text(json.dumps({
        "version": data.get("version", 1), "intents": len(data["intents"]),
        "responses": total, "ready": 0, "pending": total, "errors": 0,
        "note": "Rebuilt with unique intent-specific WAV paths",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"repaired intents={len(data['intents'])} responses={total}")


if __name__ == "__main__":
    main()
