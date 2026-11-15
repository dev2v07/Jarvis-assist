"""Generate the ten cached Fish Audio replies for the exact ``что нового`` intent.

The generator is resumable and never overwrites an existing WAV.  It writes
only to the dedicated runtime cache; the manually curated Bible source is not
changed by this operation.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.voice_runtime import VoiceRuntime  # noqa: E402
from voice_engine.voice_models import VoiceModelManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target_dir = ROOT / "backend" / "voice_engine" / "sound" / "cache"
    target_dir.mkdir(parents=True, exist_ok=True)
    manager = VoiceModelManager(ROOT / "backend")
    generated = 0

    for filename, text in VoiceRuntime.NEWS_WAVS:
        target = target_dir / filename
        if target.exists():
            print(f"EXISTS {filename}", flush=True)
            continue
        if args.limit and generated >= args.limit:
            break
        print(f"GENERATE {filename}: {text}", flush=True)
        if args.dry_run:
            continue
        temp: Path | None = None
        try:
            audio = manager.synthesize_fish(text, profile="jarvis")
            with tempfile.NamedTemporaryFile(prefix="jarvis_news_", suffix=".wav", delete=False) as handle:
                temp = Path(handle.name)
                handle.write(audio)
            info = sf.info(str(temp))
            if info.duration <= 0 or info.channels < 1 or info.samplerate < 8000:
                raise RuntimeError("Fish Audio returned invalid WAV metadata")
            if target.exists():
                raise FileExistsError(f"refusing to overwrite {target}")
            target.write_bytes(temp.read_bytes())
            generated += 1
            print(f"READY {filename}: {info.duration:.2f}s {info.samplerate}Hz", flush=True)
        except Exception as error:
            print(f"BLOCKED {filename}: Fish Audio {type(error).__name__}", flush=True)
            return 2
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    print(f"DONE generated={generated} directory={target_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
