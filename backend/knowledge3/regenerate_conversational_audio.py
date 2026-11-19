"""Resumable Fish Audio regeneration for the six conversational groups.

Generation always writes into a staging directory first. The working WAV
files are only replaced by an explicit ``--install`` run after validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "data" / "Bible" / ".internal" / "sources" / "voice_responses" / "questions.json"
AUDIO = ROOT / "data" / "Bible" / ".internal" / "audio" / "responses"
STAGING = ROOT / "data" / "Bible" / ".internal" / "audio" / "staging_conversational_20261118"
MANIFEST = STAGING / "staging_manifest.json"

GROUPS = {
    "greetings_001": "greetings",
    "greetings_how_are_you": "greetings",
    "greetings_002": "greetings",
    "mood_002": "mood",
    "mood_010": "mood",
    "farewell_004": "farewell",
}


def load_questions() -> dict:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def save_questions(payload: dict) -> None:
    QUESTIONS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "items": {}}


def write_manifest(payload: dict) -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_wav(path: Path) -> tuple[bool, str, float]:
    try:
        import soundfile as sf

        info = sf.info(str(path))
    except Exception as exc:  # noqa: BLE001 - report any decoder failure
        return False, f"unreadable: {type(exc).__name__}", 0.0
    if info.samplerate != 44100:
        return False, f"samplerate {info.samplerate}", info.duration
    if info.channels != 1:
        return False, f"channels {info.channels}", info.duration
    if info.duration < 0.3:
        return False, f"too short {info.duration:.2f}s", info.duration
    if path.stat().st_size <= 44:
        return False, "empty file", info.duration
    return True, "", info.duration


def target_paths(intent_id: str, response_id: str) -> tuple[Path, Path]:
    folder = GROUPS[intent_id]
    name = f"{intent_id}_{response_id}.wav"
    relative = Path(folder) / name
    return STAGING / relative, AUDIO / relative


def generate(limit: int | None = None) -> dict:
    from voice_engine.voice_models import VoiceModelManager

    payload = load_questions()
    intents = {item["id"]: item for item in payload["intents"]}
    manager = VoiceModelManager(ROOT / "backend")
    manifest = read_manifest()
    items = manifest.setdefault("items", {})
    attempted = 0
    generated = 0
    failed = 0
    skipped = 0
    for intent_id in GROUPS:
        intent = intents.get(intent_id)
        if intent is None:
            continue
        for response in intent.get("responses", []):
            key = f"{intent_id}:{response['id']}"
            stage, final = target_paths(intent_id, response["id"])
            if stage.is_file():
                ok, reason, duration = validate_wav(stage)
                if ok:
                    skipped += 1
                    continue
            if limit is not None and attempted >= limit:
                write_manifest(manifest)
                return {"attempted": attempted, "generated": generated, "failed": failed, "skipped": skipped, "limit_reached": True}
            text = str(response.get("text", "")).strip()
            if not text:
                items[key] = {"status": "skipped", "reason": "empty text"}
                continue
            attempted += 1
            try:
                data = manager.synthesize_fish(text)
                stage.parent.mkdir(parents=True, exist_ok=True)
                stage.write_bytes(data)
                ok, reason, duration = validate_wav(stage)
                if not ok:
                    stage.unlink(missing_ok=True)
                    raise RuntimeError(reason)
                items[key] = {
                    "status": "staged",
                    "intent": intent_id,
                    "response_id": response["id"],
                    "text_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
                    "staged_path": str(stage.relative_to(ROOT)).replace("\\", "/"),
                    "final_path": str(final.relative_to(ROOT)).replace("\\", "/"),
                    "bytes": stage.stat().st_size,
                    "duration": round(duration, 3),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                generated += 1
                print(f"OK {key} {duration:.2f}s", flush=True)
            except Exception as exc:  # noqa: BLE001 - record and continue
                failed += 1
                items[key] = {
                    "status": "failed",
                    "intent": intent_id,
                    "response_id": response["id"],
                    "error": str(exc)[:500],
                    "at": datetime.now(timezone.utc).isoformat(),
                }
                print(f"FAIL {key}: {exc}", flush=True)
            write_manifest(manifest)
            time.sleep(0.15)
    write_manifest(manifest)
    return {"attempted": attempted, "generated": generated, "failed": failed, "skipped": skipped}


def install() -> dict:
    payload = load_questions()
    intents = {item["id"]: item for item in payload["intents"]}
    manifest = read_manifest()
    items = manifest.get("items", {})
    installed = 0
    missing = []
    for intent_id in GROUPS:
        intent = intents.get(intent_id)
        if intent is None:
            continue
        for response in intent.get("responses", []):
            key = f"{intent_id}:{response['id']}"
            entry = items.get(key, {})
            stage, final = target_paths(intent_id, response["id"])
            if entry.get("status") != "staged" or not stage.is_file():
                missing.append(key)
                continue
            ok, reason, _ = validate_wav(stage)
            if not ok:
                missing.append(f"{key}:{reason}")
                continue
            final.parent.mkdir(parents=True, exist_ok=True)
            temporary = final.with_suffix(".tmp")
            shutil.copyfile(stage, temporary)
            os.replace(temporary, final)
            response["wav"] = f"{GROUPS[intent_id]}/{final.name}"
            response["generation_status"] = "AUDIO_READY"
            response["status"] = "ready"
            response.pop("text_only", None)
            response["audio_regenerated_at"] = "2026-11-18"
            entry["status"] = "installed"
            entry["installed_at"] = datetime.now(timezone.utc).isoformat()
            installed += 1
    save_questions(payload)
    write_manifest(manifest)
    return {"installed": installed, "missing": missing}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        print(json.dumps(install(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(generate(args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
