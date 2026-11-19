"""Quarantine WAV files that have no live reference anywhere in the library.

The input CSV is only a candidate list. Every candidate is re-checked against
questions.json, offline/knowledge3 catalogs, the human catalog and code-level
WAV references. Files are moved to a quarantine directory (never deleted) and
an SHA256 manifest is written for restoration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "docs" / "knowledge" / "quality" / "conversational_wav_orphans_2026-11-18.csv"
QUARANTINE = ROOT / "data" / "Bible" / ".internal" / "audio" / "quarantine_20261118"
MANIFEST = QUARANTINE / "quarantine_manifest.csv"
AUDIO_RESPONSES = ROOT / "data" / "Bible" / ".internal" / "audio" / "responses"

WAV_RE = re.compile(r"([A-Za-zА-Яа-я0-9_\- ]+\.wav)", re.IGNORECASE)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def collect_refs() -> tuple[set[str], set[str], set[str]]:
    refs: set[str] = set()

    questions = load_json(ROOT / "data/Bible/.internal/sources/voice_responses/questions.json") or {}
    for intent in questions.get("intents", []):
        for response in intent.get("responses", []):
            wav = response.get("wav")
            if wav:
                refs.add(f"data/Bible/.internal/audio/responses/{wav}".replace("\\", "/"))

    offline = load_json(ROOT / "data/Bible/.internal/sources/offline_knowledge/catalog.json") or {}
    for topic in offline.get("topics", []):
        for item in topic.get("audio", []) or []:
            if item.get("path"):
                refs.add(str(item["path"]).replace("\\", "/"))
        for variant in topic.get("response_variations", []) or []:
            if variant.get("audio_path"):
                refs.add(str(variant["audio_path"]).replace("\\", "/"))

    for path in (ROOT / "data/Bible/.internal/sources/knowledge3").rglob("*.json"):
        payload = load_json(path)
        stack = [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if item.get("audio_path"):
                    refs.add(str(item["audio_path"]).replace("\\", "/"))
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)

    catalog = load_json(ROOT / "data/Bible/index/library_catalog.json") or {}
    for record in catalog.get("records", []):
        for link in record.get("audio_links", []) or []:
            if link.get("path"):
                refs.add(str(link["path"]).replace("\\", "/"))
        if record.get("audio_path"):
            refs.add(str(record["audio_path"]).replace("\\", "/"))

    # physical_manifest is a fingerprint of the consolidated tree, not a live
    # link; it is used only for integrity checks and does not protect a file.
    manifest_paths: set[str] = set()
    manifest = load_json(ROOT / "data/Bible/index/physical_manifest.json") or {}
    for record in manifest.get("records", []):
        if record.get("canonical"):
            manifest_paths.add(str(record["canonical"]).replace("\\", "/"))

    code_names: set[str] = set()
    for path in (ROOT / "backend").rglob("*.py"):
        if "jarvis_env" in path.parts or "device_env" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in WAV_RE.finditer(text):
            code_names.add(Path(match.group(1).strip()).name.lower())
    return refs, code_names, manifest_paths


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    refs, code_names, manifest_paths = collect_refs()
    rows = list(csv.DictReader(CANDIDATES.open(encoding="utf-8")))
    confirmed = []
    protected = []
    missing = []
    for row in rows:
        relative = row["path"].replace("\\", "/")
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        normalized = relative.replace("\\", "/")
        if normalized in refs:
            protected.append((normalized, "live_catalog_reference"))
            continue
        if path.name.lower() in code_names:
            protected.append((normalized, "code_reference"))
            continue
        confirmed.append({
            "path": normalized,
            "size": path.stat().st_size,
            "sha256": sha256(path),
            "previously_referenced": row.get("previously_referenced", ""),
        })
    print(json.dumps({
        "candidates": len(rows),
        "confirmed": len(confirmed),
        "protected": len(protected),
        "missing": len(missing),
    }, ensure_ascii=False, indent=2))
    for item in protected[:10]:
        print("PROTECTED", item)
    if not args.apply:
        for item in confirmed[:10]:
            print("CONFIRMED", item["path"])
        return
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    moved = []
    for item in confirmed:
        source = ROOT / item["path"]
        target = QUARANTINE / item["path"].removeprefix("data/Bible/.internal/audio/responses/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(target.stem + "_dup" + target.suffix)
        shutil.move(str(source), str(target))
        item["quarantine_path"] = str(target.relative_to(ROOT)).replace("\\", "/")
        item["moved_at"] = datetime.now(timezone.utc).isoformat()
        moved.append(item)
    with MANIFEST.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "size", "sha256", "previously_referenced", "quarantine_path", "moved_at"])
        writer.writeheader()
        writer.writerows(moved)
    print(json.dumps({"moved": len(moved), "quarantine": str(QUARANTINE)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
