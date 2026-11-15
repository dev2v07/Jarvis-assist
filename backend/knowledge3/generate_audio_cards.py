"""Bounded Fish Audio generation for read-only Mixing and DAW cards.

Usage: ``python generate_audio_cards.py --module mixing --limit 3``.
Each module keeps its own catalog and audio directory; existing files are
never overwritten.
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

INDEX_PATH = INDEX


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", choices=("mixing", "daw"), required=True)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    catalog_path = ROOT / "data" / "knowledge3" / args.module / "catalog.json"
    audio_root = ROOT / "data" / "knowledge3" / args.module / "audio"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = payload.get("cards", [])
    manager = VoiceModelManager(ROOT / "backend")
    created = 0
    for row in rows:
        target = audio_root / f"{row['id']}.wav"
        if target.is_file() and target.stat().st_size > 44:
            row["audio_status"] = "AUDIO_READY"
            row["audio_path"] = str(target.relative_to(ROOT)).replace("\\", "/")
            continue
        if created >= max(1, int(args.limit)):
            continue
        text = f"{row.get('title', '')}. {row.get('summary', '')}"
        temp: Path | None = None
        try:
            audio = manager.synthesize_fish(text, profile="jarvis")
            with tempfile.NamedTemporaryFile(prefix=f"jarvis_{args.module}_", suffix=".wav", delete=False) as handle:
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
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    module_index = index.setdefault(args.module, {})
    ready = sum(row.get("audio_status") == "AUDIO_READY" for row in rows)
        module_index["audio_path"] = f"data/Bible/.internal/audio/library/knowledge3/{args.module}"
    module_index["audio_ready"] = ready
    module_index["audio_pending"] = max(0, len(rows) - ready)
    module_index["audio_status"] = "AUDIO_READY" if ready == len(rows) and rows else "AUDIO_PARTIAL_READY"
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"module": args.module, "created": created, "total": len(rows)}, ensure_ascii=False))
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
