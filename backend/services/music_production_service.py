"""Read-only Music Production registry and product search."""

from __future__ import annotations

import json
import re
from pathlib import Path

from services.bible_paths import resolve


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", str(value or "").lower()).split())


class MusicProductionService:
    def __init__(self, backend_dir: Path) -> None:
        self.path = resolve(backend_dir, "data/knowledge3/audio/plugin_registry.json")
        self.lessons_path = resolve(backend_dir, "data/knowledge3/audio/lessons.json")

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"products": [], "plugin_paths": {}, "read_only": True}

    def summary(self) -> dict:
        data = self.read()
        products = data.get("products", [])
        return {
            "products": len(products),
            "categories": sorted({str(row.get("category", "")) for row in products if row.get("category")}),
            "vst2_paths": len(data.get("plugin_paths", {}).get("vst2", [])),
            "vst3_paths": len(data.get("plugin_paths", {}).get("vst3", [])),
            "read_only": bool(data.get("read_only", True)),
            "lessons": len(self._lessons()),
        }

    def search(self, query: str, limit: int = 30) -> list[dict]:
        needle = normalize(query)
        if not needle:
            return []
        rows = []
        for row in self.read().get("products", []):
            haystack = normalize(" ".join(str(value) for value in row.values()))
            if needle in haystack or all(token in haystack for token in needle.split()):
                rows.append(row)
        for row in self._lessons():
            haystack = normalize(" ".join(str(value) for value in row.values()))
            if needle in haystack or all(token in haystack for token in needle.split()):
                rows.append(row)
        return rows[: max(1, min(int(limit), 100))]

    def _lessons(self) -> list[dict]:
        try:
            value = json.loads(self.lessons_path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []
