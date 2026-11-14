"""Resumable Fish Audio generator for the local Jarvis response library.

Examples:
  python backend/voice_engine/generate_voice_library.py --limit 24
  python backend/voice_engine/generate_voice_library.py --all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from voice_engine.voice_models import VoiceModelManager  # noqa: E402

LIBRARY = ROOT / "data" / "voice_responses"
QUESTIONS = LIBRARY / "questions.json"
MANIFEST = LIBRARY / "manifest.json"


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def update_manifest(data: dict) -> None:
    responses = [item for intent in data["intents"] for item in intent["responses"]]
    save_json(MANIFEST, {
        "version": data.get("version", 1),
        "generated_at": data.get("generated_at"),
        "intents": len(data["intents"]),
        "responses": len(responses),
        "ready": sum(item.get("status") == "ready" for item in responses),
        "pending": sum(item.get("status") == "pending" for item in responses),
        "errors": sum(item.get("status") == "error" for item in responses),
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="maximum new files in this run")
    parser.add_argument("--all", action="store_true", help="process all pending responses")
    parser.add_argument("--intent", help="only one intent id")
    args = parser.parse_args()
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    manager = VoiceModelManager(ROOT / "backend")
    completed = 0
    for intent in data.get("intents", []):
        if args.intent and intent["id"] != args.intent:
            continue
        for response in intent.get("responses", []):
            if response.get("status") == "ready":
                continue
            if args.limit and completed >= args.limit:
                update_manifest(data)
                return 0
            text = response["text"]
            target = LIBRARY / response["wav"]
            target.parent.mkdir(parents=True, exist_ok=True)
            response["status"] = "generating"
            response["error"] = ""
            save_json(QUESTIONS, data)
            try:
                audio = manager.synthesize_fish(text, profile="jarvis")
                with tempfile.NamedTemporaryFile(prefix="jarvis_voice_", suffix=".wav", delete=False) as handle:
                    temp = Path(handle.name)
                    handle.write(audio)
                info = sf.info(str(temp))
                if info.duration <= 0 or info.channels < 1 or info.samplerate < 8000:
                    raise RuntimeError("invalid audio metadata")
                target.write_bytes(temp.read_bytes())
                temp.unlink(missing_ok=True)
                response.update(status="ready", duration=round(info.duration, 3), samplerate=info.samplerate, channels=info.channels)
                completed += 1
                print(f"READY {completed}: {intent['id']} / {response['id']} / {info.duration:.2f}s", flush=True)
            except Exception as error:
                try:
                    temp.unlink(missing_ok=True)
                except UnboundLocalError:
                    pass
                response.update(status="error", error=str(error)[:500])
                print(f"ERROR {intent['id']} / {response['id']}: {error}", flush=True)
            save_json(QUESTIONS, data)
            update_manifest(data)
            time.sleep(0.15)
    update_manifest(data)
    print(f"DONE new={completed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
