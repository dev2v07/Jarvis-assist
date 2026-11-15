"""Local bibliography and copyright-aware literature search."""

from __future__ import annotations

import json
import re
from pathlib import Path

from services.bible_paths import resolve


class LiteratureService:
    def __init__(self, backend_dir: Path) -> None:
        self.path = resolve(backend_dir, "data/knowledge3/literature/catalog.json")

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"works": [], "copyright_policy": "protected_works_use_summaries_and_analysis_only"}

    def works(self, author: str = "") -> list[dict]:
        value = str(author or "").strip().lower()
        return [row for row in self.read().get("works", []) if not value or value in str(row.get("author", "")).lower()]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        needle = " ".join(re.sub(r"[^\w\s-]", " ", str(query or "").lower()).split())
        if not needle:
            return []
        result = []
        for row in self.works():
            haystack = " ".join(str(row.get(key, "")) for key in ("author", "title", "summary", "topics")).lower()
            if needle in haystack or all(word in haystack for word in needle.split()):
                result.append(row)
        return result[: max(1, min(int(limit), 100))]

