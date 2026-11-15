"""Build the single human-facing Bible catalog from the active search registry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.knowledge_search_service import KnowledgeSearchService


ROOT = Path(__file__).resolve().parents[2]
BIBLE = ROOT / "data" / "Bible"

GROUP_BY_KIND = {
    "topic": "Computer", "conversational": "Responses",
    "programming_lesson": "Programming", "voice_production": "Audio",
    "guitar": "Music", "psychology": "Psychology", "literature": "Literature",
    "audio_lesson": "Audio", "plugin": "Audio", "mixing": "Audio", "daw": "Audio",
    "local_track": "Music", "local_artist": "Music", "local_album": "Music",
}


def user_category_for(record: dict) -> str:
    kind = str(record.get("kind") or "").lower()
    haystack = " ".join(str(record.get(key) or "").lower() for key in ("kind", "category", "title"))
    if kind == "topic" and any(word in haystack for word in ("процессор", "компьютер", "intel", "amd", "cpu", "pentium", "ryzen", "старые компьютеры")):
        return "CPU"
    if kind in {"intent", "conversational"}:
        return "Responses"
    if kind in {"topic", "programming", "programming_lesson"} or any(word in haystack for word in ("computer", "technology", "технолог")):
        return "Computer"
    if kind in {"plugin", "mixing", "daw", "audio_lesson", "voice_production"}:
        return "Audio"
    if kind in {"guitar", "music_reference", "local_track", "local_artist", "local_album"}:
        return "Music"
    if kind == "psychology":
        return "Psychology"
    if kind == "literature":
        return "Literature"
    if kind == "conversational":
        return "Responses"
    return "General"


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    service = KnowledgeSearchService(ROOT / "backend")
    records = service.catalog()["records"]
    domains: dict[str, dict] = {}
    for record in records:
        group = GROUP_BY_KIND.get(str(record.get("kind")), "General")
        section = str(record.get("category") or record.get("kind") or "Unsorted")
        domain = domains.setdefault(group, {"sections": {}, "count": 0})
        section_data = domain["sections"].setdefault(section, {"count": 0, "records": []})
        section_data["records"].append(record)
        section_data["count"] += 1
        domain["count"] += 1

    write(BIBLE / "index" / "library_catalog.json", {
        "version": 2, "status": "CANONICAL_HUMAN_CATALOG",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_of_truth": "data/Bible/index/library_catalog.json",
        "record_count": len(records), "records": records, "domains": domains,
        "legacy_archive": "data/archive/bible_legacy_sources_20261115",
        "note": "All active knowledge records are exposed through one catalog; source files remain under Bible/sources and audio links under Bible/audio.",
    })
    user_groups: dict[str, list[dict]] = {}
    for record in records:
        user_groups.setdefault(user_category_for(record), []).append(record)
    for group, rows in sorted(user_groups.items()):
        write(BIBLE / "library" / group / "catalog.json", {
            "version": 1, "group": group,
            "source_of_truth": "data/Bible/index/library_catalog.json",
            "record_count": len(rows), "records": rows,
        })
    write(BIBLE / "library" / "catalog.json", {
        "version": 1, "status": "USER_FACING_SINGLE_BIBLE_VIEW",
        "source_of_truth": "data/Bible/index/library_catalog.json",
        "categories": {key: len(value) for key, value in sorted(user_groups.items())},
        "internal_storage": "data/Bible/.internal",
    })
    write(BIBLE / "index" / "domain_map.json", {
        "version": 2, "source_of_truth": "data/Bible/index/library_catalog.json",
        "domains": {group: sorted(data["sections"]) for group, data in domains.items()},
    })
    print(json.dumps({"records": len(records), "domains": {key: value["count"] for key, value in domains.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
