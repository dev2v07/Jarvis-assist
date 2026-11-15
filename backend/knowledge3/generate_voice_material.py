"""Resumable, small-batch Fish Audio generator for Voice Mentor cards.

Only new Voice Mentor files are written. Existing WAV files and the
conversation/offline libraries are never touched.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
from bible_paths import audio, material
sys.path.insert(0, str(ROOT / "backend"))
from voice_engine.voice_models import VoiceModelManager  # noqa: E402

LESSONS = material("voice", "lessons.json")
AUDIO_ROOT = audio("voice", "audio")


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
        row["audio_status"] = "AUDIO_PENDING"
        text = str(row.get("text", "")).strip()
        if not text:
            row["audio_status"] = "ERROR"
            row["audio_error"] = "empty text"
            continue
        temp: Path | None = None
        try:
            audio = manager.synthesize_fish(text, profile="jarvis")
            with tempfile.NamedTemporaryFile(prefix="jarvis_voice_", suffix=".wav", delete=False) as handle:
                temp = Path(handle.name)
                handle.write(audio)
            info = sf.info(str(temp))
            if info.duration <= 0 or info.channels < 1 or info.samplerate < 8000:
                raise RuntimeError("invalid audio metadata")
            target.parent.mkdir(parents=True, exist_ok=True)
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
    print(json.dumps({"created": created, "total": len(rows)}, ensure_ascii=False))
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
