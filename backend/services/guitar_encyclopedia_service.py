"""Search and compare source-linked guitar cards."""

from __future__ import annotations

import json
import re
from pathlib import Path

from services.bible_paths import resolve


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", str(value or "").lower().replace("ё", "е")).split())


class GuitarEncyclopediaService:
    def __init__(self, backend_dir: Path) -> None:
        self.path = resolve(backend_dir, "data/knowledge3/guitar/catalog.json")

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"models": [], "read_only": True}

    def search(self, query: str, limit: int = 20) -> list[dict]:
        needle = normalize(query)
        if not needle:
            return []
        result = []
        for row in self.read().get("models", []):
            haystack = normalize(" ".join(str(value) for value in row.values()))
            if needle in haystack or all(token in haystack for token in needle.split()):
                result.append(row)
        return result[: max(1, min(int(limit), 100))]

    def compare(self, ids: list[str]) -> list[dict]:
        wanted = {str(item) for item in ids}
        return [row for row in self.read().get("models", []) if row.get("id") in wanted]

    def summary(self) -> dict:
        rows = self.read().get("models", [])
        return {"models": len(rows), "brands": sorted({row.get("brand") for row in rows}), "read_only": True}
