"""Read-only integrity verifier for all Jarvis local WAV libraries."""

from __future__ import annotations

import json
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from bible_paths import material


def referenced_paths() -> list[tuple[str, Path]]:
    records: list[tuple[str, Path]] = []
    targets = (
        material("programming", "lessons.json"),
        material("audio", "lessons.json"),
        material("voice", "lessons.json"),
        material("guitar", "catalog.json"),
        material("literature", "catalog.json"),
        material("psychology", "cards.json"),
        material("mixing", "catalog.json"),
        material("daw", "catalog.json"),
    )
    for path in targets:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload if isinstance(payload, list) else next((payload.get(key, []) for key in ("lessons", "models", "works", "cards") if isinstance(payload.get(key), list)), [])
        for row in rows:
            audio_path = str(row.get("audio_path") or "")
            if audio_path:
                resolved = Path(audio_path)
                if not resolved.is_absolute():
                    resolved = ROOT / resolved
                records.append((str(row.get("id", path.name)), resolved))
    offline = ROOT / "data/Bible/.internal/sources/offline_knowledge/catalog.json"
    try:
        payload = json.loads(offline.read_text(encoding="utf-8"))
        for topic in payload.get("topics", []):
            for item in topic.get("audio", []):
                resolved = Path(str(item.get("path", "")))
                if not resolved.is_absolute():
                    resolved = ROOT / resolved
                records.append((f"{topic.get('id')}:{item.get('variant')}", resolved))
    except (OSError, json.JSONDecodeError):
        pass
    for root_name in ("data/Bible/.internal/audio/responses",):
        for path in (ROOT / root_name).rglob("*.wav"):
            records.append((f"voice_responses:{path.name}", path))
    return records


def verify() -> dict:
    errors: list[dict] = []
    checked: set[str] = set()
    stats = {"files_checked": 0, "frames": 0, "samplerates": {}, "channels": {}}
    for record_id, path in referenced_paths():
        key = str(path.resolve()).lower()
        if key in checked:
            continue
        checked.add(key)
        stats["files_checked"] += 1
        try:
            if not path.is_file() or path.stat().st_size <= 44:
                raise ValueError("missing_or_empty")
            with wave.open(str(path), "rb") as source:
                frames = source.getnframes()
                rate = source.getframerate()
                channels = source.getnchannels()
                if frames <= 0 or rate <= 0 or channels <= 0:
                    raise ValueError("invalid_audio_metadata")
            stats["frames"] += frames
            stats["samplerates"][str(rate)] = stats["samplerates"].get(str(rate), 0) + 1
            stats["channels"][str(channels)] = stats["channels"].get(str(channels), 0) + 1
        except (OSError, ValueError, wave.Error) as exc:
            errors.append({"id": record_id, "path": str(path), "error": str(exc)})
    return {"ok": not errors, "errors": errors, "stats": stats, "read_only": True}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
