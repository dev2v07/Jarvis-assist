"""Generate the seven short Fish Audio model-wait acknowledgements.

The command is deliberately small and resumable. It never overwrites an
existing WAV and never changes the response library JSON files.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from voice_engine.model_acknowledgements import (  # noqa: E402
    MODEL_ACKNOWLEDGEMENTS,
    model_acknowledgement_dir,
)
from voice_engine.voice_models import VoiceModelManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="maximum number of missing WAV files")
    parser.add_argument("--dry-run", action="store_true", help="only list missing files")
    args = parser.parse_args()

    target_dir = model_acknowledgement_dir(ROOT)
    target_dir.mkdir(parents=True, exist_ok=True)
    manager = VoiceModelManager(ROOT / "backend")
    completed = 0

    for text, filename in MODEL_ACKNOWLEDGEMENTS:
        target = target_dir / filename
        if target.exists():
            print(f"EXISTS {filename}", flush=True)
            continue
        if args.limit and completed >= args.limit:
            break
        print(f"GENERATE {filename}: {text}", flush=True)
        if args.dry_run:
            continue
        temp: Path | None = None
        try:
            audio = manager.synthesize_fish(text, profile="jarvis")
            with tempfile.NamedTemporaryFile(prefix="jarvis_model_ack_", suffix=".wav", delete=False) as handle:
                temp = Path(handle.name)
                handle.write(audio)
            info = sf.info(str(temp))
            if info.duration <= 0 or info.channels < 1 or info.samplerate < 8000:
                raise RuntimeError("Fish Audio returned invalid WAV metadata")
            if target.exists():
                raise FileExistsError(f"refusing to overwrite {target}")
            target.write_bytes(temp.read_bytes())
            completed += 1
            print(f"READY {filename}: {info.duration:.2f}s {info.samplerate}Hz", flush=True)
        except Exception as error:
            # Do not print provider URLs, credentials or a long traceback.
            # A failed provider must leave the target absent so generation can
            # be resumed safely when Fish Audio is available again.
            print(f"BLOCKED {filename}: Fish Audio {type(error).__name__}", flush=True)
            return 2
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    print(f"DONE generated={completed} directory={target_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
