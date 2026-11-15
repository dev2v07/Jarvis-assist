"""Small resumable Fish Audio generator for Knowledge 3.0 audio lessons.

The script is intentionally opt-in and bounded by --limit. It only writes
new files under data/knowledge3/audio/lesson_audio and never touches existing
voice_responses, offline_knowledge or user audio.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
from bible_paths import INDEX, audio, material
sys.path.insert(0, str(ROOT / "backend"))
from voice_engine.voice_models import VoiceModelManager  # noqa: E402

LESSONS = material("audio", "lessons.json")
AUDIO_ROOT = audio("audio", "lesson_audio")
INDEX_PATH = INDEX


def sync_index(rows: list[dict]) -> None:
    """Keep the shared index truthful after every resumable batch."""
    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return
    audio = index.setdefault("audio", {})
    ready = sum(row.get("audio_status") == "AUDIO_READY" for row in rows)
    audio["lessons_path"] = "data/Bible/.internal/sources/knowledge3/audio/lessons.json"
    audio["lessons"] = len(rows)
    audio["audio_ready"] = ready
    audio["audio_pending"] = max(0, len(rows) - ready)
    audio["status"] = "AUDIO_READY" if ready == len(rows) and rows else "AUDIO_PARTIAL_READY"
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    rows = json.loads(LESSONS.read_text(encoding="utf-8"))
    manager = VoiceModelManager(ROOT / "backend")
    created = 0
    for row in rows:
        target = AUDIO_ROOT / f"{row['id']}.wav"
        if target.is_file() and target.stat().st_size > 44:
            row["audio_status"] = "AUDIO_READY"
            row["audio_path"] = str(target.relative_to(ROOT)).replace("\\", "/")
            continue
        if created >= max(1, int(args.limit)):
            continue
        text = str(row.get("text", "")).strip()
        if not text:
            row["audio_status"] = "ERROR"
            row["audio_error"] = "empty text"
            continue
        temp: Path | None = None
        try:
            audio = manager.synthesize_fish(text, profile="jarvis")
            with tempfile.NamedTemporaryFile(prefix="jarvis_knowledge_", suffix=".wav", delete=False) as handle:
                temp = Path(handle.name)
                handle.write(audio)
            info = sf.info(str(temp))
            if info.duration <= 0 or info.channels < 1 or info.samplerate < 8000:
                raise RuntimeError("invalid audio metadata")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(str(target))
            target.write_bytes(temp.read_bytes())
            row["audio_status"] = "AUDIO_READY"
            row["audio_path"] = str(target.relative_to(ROOT)).replace("\\", "/")
            row["audio_metadata"] = {"duration": round(info.duration, 3), "samplerate": info.samplerate, "channels": info.channels}
            row.pop("audio_error", None)
            created += 1
            print(f"READY {row['id']} {target}", flush=True)
        except Exception as error:
            row["audio_status"] = "ERROR"
            row["audio_error"] = str(error)[:500]
            print(f"ERROR {row['id']}: {error}", flush=True)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    LESSONS.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_index(rows)
    print(json.dumps({"created": created, "total": len(rows)}, ensure_ascii=False))
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
