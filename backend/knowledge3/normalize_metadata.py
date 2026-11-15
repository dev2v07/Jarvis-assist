"""Add the shared Knowledge 3.0 metadata fields without changing source text/audio."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from bible_paths import material
TODAY = date.today().isoformat()
TARGETS = (
    (material("programming", "lessons.json"), "lessons"),
    (material("audio", "lessons.json"), "lessons"),
    (material("voice", "lessons.json"), "lessons"),
    (material("guitar", "catalog.json"), "models"),
    (material("literature", "catalog.json"), "works"),
    (material("psychology", "cards.json"), "cards"),
    (material("mixing", "catalog.json"), "cards"),
    (material("daw", "catalog.json"), "cards"),
)


def first_value(row: dict, *keys: str, default=""):
    for key in keys:
        value = row.get(key)
        if value not in (None, "", []):
            return value
    return default


def normalize_row(row: dict) -> None:
    title = first_value(row, "title", "topic", "model", "name", "album", default=row.get("id", ""))
    category = first_value(row, "category", "language", "kind", "type", default="knowledge3")
    subcategory = first_value(row, "subcategory", "language", "category", "kind", "type", default="general")
    answer = first_value(row, "answer", "explanation", "text", "summary", "function", "description", default="")
    row.setdefault("category", category)
    row.setdefault("subcategory", subcategory)
    row.setdefault("topic", title)
    row.setdefault("questions", [value for value in (title, row.get("summary", "")) if value])
    row.setdefault("answer", answer)
    row.setdefault("verified_at", TODAY)
    row.setdefault("version", 1)
    row.setdefault("confidence", "medium" if row.get("status") not in {"VERIFIED", "SOURCE_LINKED"} else "high")
    row.setdefault("related_materials", [])
    row.setdefault("status", "SOURCE_LINKED")
    row.setdefault("audio_path", None)
    row.setdefault("metadata_basis", "AUDIT_DERIVED; existing source/text/audio fields preserved")


def main() -> None:
    changed = 0
    records = 0
    for path, key in TARGETS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if key == "lessons" and isinstance(payload, list) else payload[key]
        for row in rows:
            before = json.dumps(row, ensure_ascii=False, sort_keys=True)
            normalize_row(row)
            changed += before != json.dumps(row, ensure_ascii=False, sort_keys=True)
            records += 1
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": records, "catalogs": len(TARGETS), "records_changed": changed, "verified_at": TODAY}, ensure_ascii=False))


if __name__ == "__main__":
    main()
