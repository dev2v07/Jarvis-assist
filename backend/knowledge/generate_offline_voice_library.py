"""Resumable Fish Audio generator for reviewed offline knowledge topics.

Unlike the conversational generator, this script is intentionally inert for
the extracted catalog: it skips topics without reviewed answer variants. It
can be started later with --limit/--all after texts and sources are approved.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from voice_engine.voice_models import VoiceModelManager  # noqa: E402

CATALOG = ROOT / "data" / "Bible" / ".internal" / "sources" / "offline_knowledge" / "catalog.json"
AUDIO_ROOT = ROOT / "data" / "Bible" / ".internal" / "audio" / "library" / "offline_knowledge" / "audio"


def save(data: dict) -> None:
    path = CATALOG
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for _ in range(5):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.25)
    path.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--category", default="")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    manager = VoiceModelManager(ROOT / "backend")
    generated = 0
    for topic in data.get("topics", []):
        if args.category and topic.get("category") != args.category:
            continue
        answers = [str(item).strip() for item in topic.get("answers", []) if str(item).strip()]
        if not answers or topic.get("status") not in {"TEXT_READY", "AUDIO_PENDING", "ERROR"}:
            continue
        audio_items = topic.setdefault("audio", [])
        for index, text in enumerate(answers, 1):
            if args.limit and generated >= args.limit:
                save(data)
                return 0
            target = AUDIO_ROOT / str(topic["id"]) / f"variant_{index:02d}.wav"
            existing = next((item for item in audio_items if item.get("variant") == index), None)
            if existing and existing.get("status") == "ready" and target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            topic["audio_status"] = "AUDIO_PENDING"
            topic["status"] = "AUDIO_PENDING"
            save(data)
            temp: Path | None = None
            try:
                audio = manager.synthesize_fish(text, profile="jarvis")
                with tempfile.NamedTemporaryFile(prefix="jarvis_offline_", suffix=".wav", delete=False) as handle:
                    temp = Path(handle.name)
                    handle.write(audio)
                info = sf.info(str(temp))
                if info.duration <= 0 or info.channels < 1 or info.samplerate < 8000:
                    raise RuntimeError("invalid audio metadata")
                target.write_bytes(temp.read_bytes())
                temp.unlink(missing_ok=True)
                if existing is None:
                    existing = {"variant": index}
                    audio_items.append(existing)
                existing.update(path=str(target.relative_to(ROOT)).replace("\\", "/"), status="ready", duration=round(info.duration, 3), samplerate=info.samplerate, channels=info.channels)
                generated += 1
                print(f"READY {topic['id']} variant={index}", flush=True)
            except Exception as error:
                if temp is not None:
                    temp.unlink(missing_ok=True)
                if existing is None:
                    existing = {"variant": index}
                    audio_items.append(existing)
                existing.update(status="error", error=str(error)[:500])
                topic["status"] = "ERROR"
                topic["audio_status"] = "ERROR"
                print(f"ERROR {topic['id']} variant={index}: {error}", flush=True)
            save(data)
    save(data)
    print(f"DONE new={generated}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
