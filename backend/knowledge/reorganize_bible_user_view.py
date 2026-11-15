"""Reorganize the Bible's human-facing view without duplicating user materials.

The three historical namespaces are kept as internal storage because runtime
records and rollback manifests still need their provenance.  The user-facing
tree is rebuilt as Bible/library/<category>, where each catalog is a view over
the single canonical index rather than another copy of the knowledge.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIBLE = ROOT / "data" / "Bible"
ARCHIVE = ROOT / "data" / "archive" / "bible_reorganization_20261115"


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_paths(path: Path, replacements: list[tuple[str, str]]) -> None:
    if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
        return
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")


def move_once(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if target.exists():
        raise RuntimeError(f"Refusing to merge non-empty Bible paths: {source} -> {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def category_for(record: dict) -> str:
    kind = str(record.get("kind") or "").lower()
    category = str(record.get("category") or "").lower()
    title = str(record.get("title") or "").lower()
    haystack = f"{kind} {category} {title}"
    if kind == "topic" and (
        "процессор" in haystack or "компьютер" in haystack or "intel" in haystack
        or "amd" in haystack or "cpu" in haystack or "pentium" in haystack
        or "ryzen" in haystack or "старые компьютеры" in haystack
    ):
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


def main() -> None:
    BIBLE.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    metadata = ARCHIVE / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)

    for name in ("catalog.json", "library_catalog.json", "domain_map.json", "physical_manifest.json"):
        source = BIBLE / "index" / name
        if source.exists():
            shutil.copy2(source, metadata / name)

    # Keep provenance, but move it below an explicitly internal namespace.
    move_once(BIBLE / "sources", BIBLE / ".internal" / "sources")
    move_once(BIBLE / "audio" / "library", BIBLE / ".internal" / "audio" / "library")
    move_once(BIBLE / "audio" / "responses", BIBLE / ".internal" / "audio" / "responses")

    old_view = BIBLE / "knowledge"
    if old_view.exists():
        move_once(old_view, ARCHIVE / "previous_knowledge_views")

    replacements = [
        ("data/Bible/sources/", "data/Bible/.internal/sources/"),
        ("data/Bible/audio/library/", "data/Bible/.internal/audio/library/"),
        ("data/Bible/audio/responses/", "data/Bible/.internal/audio/responses/"),
    ]
    for path in [BIBLE / "index", BIBLE / ".internal"]:
        for file in path.rglob("*"):
            replace_paths(file, replacements)

    manifest_path = BIBLE / "index" / "physical_manifest.json"
    manifest = read_json(manifest_path, {})
    if isinstance(manifest, dict):
        for record in manifest.get("records", []):
            if isinstance(record, dict) and record.get("canonical"):
                for old, new in replacements:
                    record["canonical"] = str(record["canonical"]).replace(old, new)
        manifest["user_view"] = "data/Bible/library"
        manifest["internal_storage"] = "data/Bible/.internal"
        manifest["reorganized_at"] = stamp
        write_json(manifest_path, manifest)

    catalog = read_json(BIBLE / "index" / "library_catalog.json", {})
    records = catalog.get("records", []) if isinstance(catalog, dict) else []
    groups: dict[str, list[dict]] = {}
    for record in records:
        if isinstance(record, dict):
            groups.setdefault(category_for(record), []).append(record)

    library = BIBLE / "library"
    library.mkdir(parents=True, exist_ok=True)
    for group, rows in sorted(groups.items()):
        write_json(library / group / "catalog.json", {
            "version": 1,
            "group": group,
            "source_of_truth": "data/Bible/index/library_catalog.json",
            "record_count": len(rows),
            "records": rows,
        })
    write_json(library / "catalog.json", {
        "version": 1,
        "status": "USER_FACING_SINGLE_BIBLE_VIEW",
        "source_of_truth": "data/Bible/index/library_catalog.json",
        "categories": {key: len(value) for key, value in sorted(groups.items())},
        "internal_storage": "data/Bible/.internal",
        "note": "Категории содержат навигационные представления, а не дубликаты исходных материалов.",
    })
    (library / "README.md").write_text(
        "# Bible — единая пользовательская библиотека\n\n"
        "Открывайте категории здесь: `CPU`, `Computer`, `Audio`, `Music`, `Responses` и другие.\n"
        "Все карточки связаны с единым индексом `../index/library_catalog.json`.\n"
        "Папка `.internal` хранит происхождение файлов и служебное аудио; это не отдельные библиотеки.\n",
        encoding="utf-8",
    )
    print(json.dumps({"categories": {key: len(value) for key, value in sorted(groups.items())}, "records": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
