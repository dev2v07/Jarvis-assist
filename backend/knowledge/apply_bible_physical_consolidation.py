"""Verify and apply the reversible final Bible physical consolidation.

The operation moves only project-owned library directories. It never deletes
files: the pre-cutover roots are moved to ``data/archive`` and every move is
recorded. Run without ``--apply`` first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIBLE = ROOT / "data" / "Bible"
MANIFEST_PATH = BIBLE / "index" / "physical_manifest.json"
SOURCE_ROOTS = {
    "offline_knowledge": ROOT / "data" / "offline_knowledge",
    "knowledge3": ROOT / "data" / "knowledge3",
    "voice_responses": ROOT / "data" / "voice_responses",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    for item in manifest.get("records", []):
        canonical = ROOT / str(item.get("canonical", ""))
        if not canonical.is_file():
            errors.append(f"missing canonical: {canonical}")
            continue
        expected_size = int(item.get("canonical_size", item.get("size", -1)))
        if canonical.stat().st_size != expected_size:
            errors.append(f"size mismatch: {canonical}")
            continue
        expected_hash = str(item.get("canonical_sha256", item.get("sha256", "")))
        if digest(canonical) != expected_hash:
            errors.append(f"sha256 mismatch: {canonical}")
    return errors


def path_map() -> list[tuple[Path, Path]]:
    return [
        (BIBLE / "materials" / "offline_knowledge", BIBLE / ".internal" / "sources" / "offline_knowledge"),
        (BIBLE / "materials" / "knowledge3", BIBLE / ".internal" / "sources" / "knowledge3"),
        (BIBLE / "materials" / "voice_responses", BIBLE / ".internal" / "sources" / "voice_responses"),
        (BIBLE / "audio" / "offline_knowledge", BIBLE / ".internal" / "audio" / "library" / "offline_knowledge"),
        (BIBLE / "audio" / "knowledge3", BIBLE / ".internal" / "audio" / "library" / "knowledge3"),
        (BIBLE / "audio" / "voice_responses", BIBLE / ".internal" / "audio" / "responses"),
    ]


def rewrite(value, replacements: list[tuple[str, str]]):
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [rewrite(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: rewrite(item, replacements) for key, item in value.items()}
    return value


def apply() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = verify_manifest(manifest)
    if errors:
        raise RuntimeError("manifest verification failed:\n" + "\n".join(errors[:20]))
    recorded_archive = manifest.get("legacy_archive")
    if recorded_archive and (ROOT / str(recorded_archive)).is_dir():
        archive = ROOT / str(recorded_archive)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = ROOT / "data" / "archive" / f"bible_legacy_sources_{stamp}"
        archive.mkdir(parents=True, exist_ok=False)
    moves: list[dict[str, str]] = []
    for name, source in SOURCE_ROOTS.items():
        target = archive / name
        if source.is_dir():
            shutil.move(str(source), str(target))
            moves.append({"from": source.relative_to(ROOT).as_posix(), "to": target.relative_to(ROOT).as_posix()})
    for source, target in path_map():
        if not source.is_dir():
            if target.is_dir():
                continue
            raise RuntimeError(f"missing staged source: {source}")
        if target.exists():
            raise RuntimeError(f"destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        moves.append({"from": source.relative_to(ROOT).as_posix(), "to": target.relative_to(ROOT).as_posix()})

    replacements = [
        ("data/Bible/materials/offline_knowledge", "data/Bible/.internal/sources/offline_knowledge"),
        ("data/Bible/materials/knowledge3", "data/Bible/.internal/sources/knowledge3"),
        ("data/Bible/materials/voice_responses", "data/Bible/.internal/sources/voice_responses"),
        ("data/Bible/audio/offline_knowledge", "data/Bible/.internal/audio/library/offline_knowledge"),
        ("data/Bible/audio/knowledge3", "data/Bible/.internal/audio/library/knowledge3"),
        ("data/Bible/audio/voice_responses", "data/Bible/.internal/audio/responses"),
    ]
    for path in list((BIBLE / ".internal" / "sources").rglob("*.json")) + [BIBLE / "index" / "library_catalog.json"]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        path.write_text(json.dumps(rewrite(payload, replacements), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for item in manifest.get("records", []):
        item["canonical"] = str(rewrite(str(item["canonical"]), replacements))
    manifest["status"] = "PHYSICALLY_CONSOLIDATED"
    manifest["copy_only"] = False
    manifest["originals_preserved"] = True
    manifest["legacy_archive"] = archive.relative_to(ROOT).as_posix()
    manifest["consolidated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    catalog_path = BIBLE / "index" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["status"] = "CANONICAL_MANIFEST"
    catalog["physical_migration"] = "PHYSICALLY_CONSOLIDATED"
    catalog["sources"] = rewrite(catalog.get("sources", {}), replacements)
    catalog["audio_roots"] = rewrite(catalog.get("audio_roots", []), replacements)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record = {"version": 1, "status": "APPLIED", "archive": archive.relative_to(ROOT).as_posix(), "moves": moves}
    (BIBLE / "index" / "physical_consolidation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"archive": str(archive), "moves": len(moves), "records": len(manifest.get("records", []))}


def refresh_manifest() -> dict:
    """Refresh canonical fingerprints after approved local catalog edits."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    refreshed = 0
    for item in manifest.get("records", []):
        canonical = ROOT / str(item.get("canonical", ""))
        if not canonical.is_file():
            continue
        item["canonical_size"] = canonical.stat().st_size
        item["canonical_sha256"] = digest(canonical)
        refreshed += 1
    manifest["fingerprint_note"] = "canonical_size/canonical_sha256 reflect the current verified Bible copy; source_sha256 remains historical staging evidence"
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"refreshed": refreshed}


def record_legacy_archive() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    archive = ROOT / "data" / "archive" / "bible_legacy_sources_20261115"
    names = list(SOURCE_ROOTS)
    missing = [name for name in names if not (archive / name).is_dir()]
    if missing:
        raise RuntimeError(f"legacy archive incomplete: {missing}")
    manifest["legacy_archive"] = archive.relative_to(ROOT).as_posix()
    manifest["legacy_roots_archived"] = names
    manifest["legacy_roots_present"] = []
    manifest["status"] = "STAGED_WITH_LEGACY_ARCHIVE"
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"archive": archive.relative_to(ROOT).as_posix(), "archived": names}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-manifest", action="store_true")
    parser.add_argument("--record-legacy-archive", action="store_true")
    args = parser.parse_args()
    if args.refresh_manifest:
        print(json.dumps(refresh_manifest(), ensure_ascii=False, indent=2))
        if not args.apply:
            return
    if args.record_legacy_archive:
        print(json.dumps(record_legacy_archive(), ensure_ascii=False, indent=2))
        if not args.apply:
            return
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = verify_manifest(manifest)
    if errors:
        raise SystemExit("VERIFY FAILED\n" + "\n".join(errors[:20]))
    pending_legacy = sum(1 for source in SOURCE_ROOTS.values() if source.is_dir())
    pending_mirrors = sum(1 for source, target in path_map() if source.is_dir() and not target.is_dir())
    print(json.dumps({"verify": "PASS", "records": len(manifest.get("records", [])), "planned_moves": pending_mirrors + pending_legacy}, ensure_ascii=False, indent=2))
    if args.apply:
        print(json.dumps(apply(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
