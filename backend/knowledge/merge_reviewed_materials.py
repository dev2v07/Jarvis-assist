"""Merge reviewed offline materials without changing existing catalog topics."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "Bible" / ".internal" / "sources" / "offline_knowledge" / "catalog.json"
REVIEWED = ROOT / "data" / "Bible" / ".internal" / "sources" / "offline_knowledge" / "reviewed_materials.json"


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    reviewed = json.loads(REVIEWED.read_text(encoding="utf-8"))
    by_id = {str(topic.get("id")): topic for topic in catalog.get("topics", [])}
    inserted = 0
    updated = 0
    for material in reviewed.get("materials", []):
        topic_id = str(material.get("id", ""))
        if not topic_id:
            continue
        if topic_id in by_id:
            by_id[topic_id].update(material)
            updated += 1
        else:
            catalog.setdefault("topics", []).append(material)
            by_id[topic_id] = material
            inserted += 1
    catalog["version"] = max(int(catalog.get("version", 1)), 2)
    catalog["updated_from_reviewed_materials"] = True
    tmp = CATALOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CATALOG)
    print(f"inserted={inserted} updated={updated} total={len(catalog.get('topics', []))}")


if __name__ == "__main__":
    main()
