"""Read-only WAV/reference audit for the existing Unified Knowledge Library.

Writes a review plan only. It never edits source catalogs or audio files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SOURCES = ("knowledge3", "offline_knowledge", "voice_responses")


def read_json(relative: str, fallback: dict | list) -> dict | list:
    try:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def relative_path(value: str, owner: str | None = None) -> str:
    path = Path(str(value or "").replace("\\", "/"))
    if path.is_absolute():
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)
    result = path.as_posix().lstrip("./")
    return result if result.startswith("data/") else f"data/{owner}/{result}" if owner else result


def text_key(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def references() -> dict[str, list[dict]]:
    refs: dict[str, list[dict]] = defaultdict(list)
    voice = read_json("data/voice_responses/questions.json", {})
    for intent in voice.get("intents", []) if isinstance(voice, dict) else []:
        for response in intent.get("responses", []):
            if response.get("wav"):
                path = relative_path(response["wav"], "voice_responses")
                refs[path].append({"source": "data/voice_responses/questions.json",
                                   "material_id": intent.get("id"), "variant_id": response.get("id"),
                                   "intent_class": intent.get("class"), "category": intent.get("category"),
                                   "status": response.get("status"), "text": response.get("text", "")})
    offline = read_json("data/offline_knowledge/catalog.json", {})
    for topic in offline.get("topics", []) if isinstance(offline, dict) else []:
        answers = topic.get("answers", [])
        for audio in topic.get("audio", []):
            if not audio.get("path"):
                continue
            number = int(audio.get("variant", 0) or 0)
            script = answers[number - 1] if 0 < number <= len(answers) else ""
            refs[relative_path(audio["path"], "offline_knowledge")].append({
                "source": "data/offline_knowledge/catalog.json", "material_id": topic.get("id"),
                "variant_id": number, "category": topic.get("category"),
                "status": audio.get("status"), "text": script,
            })
    specs = (
        ("voice/lessons.json", None), ("programming/lessons.json", None),
        ("audio/lessons.json", None), ("guitar/catalog.json", "models"),
        ("literature/catalog.json", "works"), ("psychology/cards.json", "cards"),
        ("mixing/catalog.json", "cards"), ("daw/catalog.json", "cards"),
    )
    for suffix, key in specs:
        source = f"data/knowledge3/{suffix}"
        payload = read_json(source, [] if key is None else {})
        rows = payload if key is None else payload.get(key, []) if isinstance(payload, dict) else []
        for row in rows if isinstance(rows, list) else []:
            if row.get("audio_path"):
                refs[relative_path(row["audio_path"], "knowledge3")].append({
                    "source": source, "material_id": row.get("id"), "variant_id": None,
                    "category": row.get("category"), "status": row.get("audio_status"),
                    "text": row.get("text") or row.get("answer") or row.get("summary") or "",
                    "link_type": "legacy_parent_audio",
                })
            for variant in row.get("response_variations", []):
                if variant.get("audio_path"):
                    refs[relative_path(variant["audio_path"], "knowledge3")].append({
                        "source": source, "material_id": row.get("id"),
                        "variant_id": variant.get("variant_id"), "category": row.get("category"),
                        "status": variant.get("audio_status"), "text": variant.get("text", ""),
                        "link_type": "variant_audio",
                    })
    return refs


def build_plan() -> dict:
    refs = references()
    records: list[dict] = []
    for root_name in SOURCES:
        for path in sorted((DATA / root_name).rglob("*.wav")):
            relative = path.relative_to(ROOT).as_posix()
            problems: list[str] = []
            try:
                with wave.open(str(path), "rb") as reader:
                    duration = round(reader.getnframes() / reader.getframerate(), 3)
                    sample_rate = reader.getframerate()
                    channels = reader.getnchannels()
                    sample_width = reader.getsampwidth()
            except (OSError, wave.Error, ZeroDivisionError) as exc:
                duration = 0.0
                sample_rate = channels = sample_width = 0
                problems.append(f"invalid_wav:{exc}")
            links = refs.get(relative, [])
            if not links:
                problems.append("no_catalog_reference")
            records.append({"wav_path": relative, "root": root_name,
                            "bytes": path.stat().st_size, "sha256": digest(path),
                            "duration_seconds": duration, "sample_rate": sample_rate,
                            "channels": channels, "sample_width_bytes": sample_width,
                            "references": links, "problems": problems})
    by_hash: dict[str, list[dict]] = defaultdict(list)
    by_text: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_hash[record["sha256"]].append(record)
        if record["root"] == "voice_responses" and record["references"]:
            key = text_key(record["references"][0].get("text", ""))
            if key:
                by_text[key].append(record)
    for items in by_hash.values():
        if len(items) > 1:
            for record in items:
                record["problems"].append("byte_identical_wav")
    for items in by_text.values():
        if len(items) <= 1:
            continue
        # A deterministic primary helps plan the review; it is not an audio
        # quality judgment. Every proposed archive still needs listening.
        for index, record in enumerate(sorted(items, key=lambda x: x["wav_path"])):
            record["text_duplicate_group_size"] = len(items)
            record["proposed_action"] = "KEEP_CANDIDATE_NEEDS_LISTEN" if index == 0 else "ARCHIVE_CANDIDATE_NEEDS_LISTEN"
    for record in records:
        if "proposed_action" not in record:
            record["proposed_action"] = "REVIEW_UNIQUE_OR_UNLINKED"
        if any(link.get("intent_class") == "dynamic" for link in record["references"]):
            record["problems"].append("dynamic_wav_not_used_by_LocalResponseService")
    existing = {record["wav_path"] for record in records}
    missing_links = [{"wav_path": path, "references": links} for path, links in refs.items() if path not in existing]
    counts = Counter(record["root"] for record in records)
    actions = Counter(record["proposed_action"] for record in records)
    return {"version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "read_only_review_plan_no_deletion", "roots": dict(counts),
            "summary": {"wav_files": len(records), "linked_files": sum(bool(record["references"]) for record in records),
                        "unlinked_files": sum(not record["references"] for record in records),
                        "missing_link_targets": len(missing_links),
                        "byte_duplicate_groups": sum(len(items) > 1 for items in by_hash.values()),
                        "voice_text_duplicate_groups": sum(len(items) > 1 for items in by_text.values()),
                        "actions": dict(actions)},
            "missing_link_targets": missing_links, "files": records,
            "review_rule": "No deletion until every candidate has a link audit, listening check, reversible backup, replacement mapping, and runtime playback test."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "UNIFIED_KNOWLEDGE_WAV_REVIEW_PLAN.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT.resolve()):
        parser.error("output must stay inside the Jarvis project")
    if output.exists() and not args.overwrite:
        parser.error("output exists; use --overwrite for a fresh read-only snapshot")
    plan = build_plan()
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **plan["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
