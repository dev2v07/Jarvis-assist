"""Safety-bounded local Psychology & Emotional Support cards."""

from __future__ import annotations

import json
import re
from pathlib import Path

from services.bible_paths import resolve


class PsychologyService:
    def __init__(self, backend_dir: Path) -> None:
        self.path = resolve(backend_dir, "data/knowledge3/psychology/cards.json")

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"cards": [], "safety": {"no_diagnosis": True, "no_prescriptions": True}}

    def cards(self, topic: str = "") -> list[dict]:
        value = str(topic or "").strip().lower()
        return [row for row in self.read().get("cards", []) if not value or str(row.get("topic", "")).lower() == value]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        needle = " ".join(re.sub(r"[^\w\s-]", " ", str(query or "").lower()).split())
        if not needle:
            return []
        result = []
        for row in self.cards():
            haystack = " ".join(str(row.get(key, "")) for key in ("topic", "title", "text", "exercise")).lower()
            if needle in haystack or all(word in haystack for word in needle.split()):
                result.append(row)
        return result[: max(1, min(int(limit), 100))]

    def safety(self) -> dict:
        return self.read().get("safety", {})
