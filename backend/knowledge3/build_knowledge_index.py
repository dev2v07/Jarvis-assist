"""Build the Phase 1 local knowledge index without modifying source media.

The command only reads the module registry, audited environment and the local
music collection. It writes derived JSON under data/knowledge3. External
discographies are intentionally kept separate and are not invented here.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from bible_paths import MATERIALS, material
DEFAULT_MUSIC_ROOT = Path(r"E:\Музыка")
OUT_ROOT = MATERIALS

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"}


def read_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def first_tag(tags, *names: str) -> str:
    if not tags:
        return ""
    for name in names:
        value = tags.get(name)
        if value:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else ""
            return str(value).strip()
    return ""


def media_metadata(path: Path) -> dict:
    metadata = {}
    try:
        from mutagen import File as MutagenFile  # type: ignore

        media = MutagenFile(str(path), easy=True)
        if media is not None:
            metadata = {
                "artist": first_tag(media, "artist", "albumartist"),
                "album": first_tag(media, "album"),
                "title": first_tag(media, "title"),
                "year": first_tag(media, "date", "originaldate", "year"),
                "genre": first_tag(media, "genre"),
                "duration_seconds": round(float(getattr(media.info, "length", 0) or 0), 3),
                "sample_rate": int(getattr(media.info, "sample_rate", 0) or 0),
                "channels": int(getattr(media.info, "channels", 0) or 0),
                "bitrate": int(getattr(media.info, "bitrate", 0) or 0),
            }
    except Exception:
        metadata = {}
    if metadata.get("duration_seconds", 0) or metadata.get("sample_rate", 0):
        return metadata
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return metadata
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "format=duration:format_tags=artist,album,title,date,genre:stream=sample_rate,channels,bit_rate",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=True,
        )
        payload = json.loads(completed.stdout or "{}")
        tags = (payload.get("format") or {}).get("tags") or {}
        streams = payload.get("streams") or []
        stream = next((item for item in streams if item.get("codec_type", "audio") == "audio"), streams[0] if streams else {})
        metadata = {
            "artist": first_tag(tags, "artist", "ARTIST", "album_artist", "ALBUM_ARTIST"),
            "album": first_tag(tags, "album", "ALBUM"),
            "title": first_tag(tags, "title", "TITLE"),
            "year": first_tag(tags, "date", "DATE", "year", "YEAR"),
            "genre": first_tag(tags, "genre", "GENRE"),
            "duration_seconds": round(float((payload.get("format") or {}).get("duration", 0) or 0), 3),
            "sample_rate": int(stream.get("sample_rate", 0) or 0),
            "channels": int(stream.get("channels", 0) or 0),
            "bitrate": int(stream.get("bit_rate", 0) or 0),
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        pass
    return metadata


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_music_catalog(root: Path, include_hash: bool) -> dict:
    tracks: list[dict] = []
    artists: dict[str, dict] = {}
    albums: dict[tuple[str, str], dict] = {}
    if not root.exists():
        return {"root": str(root), "exists": False, "read_only": True, "tracks": [], "artists": [], "albums": []}

    audio_files = [path for path in sorted(root.rglob("*")) if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        metadata_rows = pool.map(media_metadata, audio_files)
        scanned = zip(audio_files, metadata_rows)
        for path, meta in scanned:
            rel = path.relative_to(root)
            parts = rel.parts
            fallback_artist = parts[0] if len(parts) > 1 else "Unknown Artist"
            fallback_album = parts[1] if len(parts) > 2 else "Unknown Album"
            artist = meta.get("artist") or fallback_artist
            album = meta.get("album") or fallback_album
            title = meta.get("title") or path.stem
            item = {
                "path": str(path),
                "relative_path": str(rel),
                "artist": artist,
                "album": album,
                "title": title,
                "format": path.suffix.lower().lstrip("."),
                "size_bytes": path.stat().st_size,
                "year": meta.get("year", ""),
                "genre": meta.get("genre", ""),
                "duration_seconds": meta.get("duration_seconds", 0),
                "sample_rate": meta.get("sample_rate", 0),
                "channels": meta.get("channels", 0),
                "bitrate": meta.get("bitrate", 0),
                "source": "LOCAL_COLLECTION",
            }
            if include_hash:
                item["sha256"] = digest(path)
            tracks.append(item)
            artists.setdefault(artist, {"name": artist, "tracks": 0, "albums": set()})
            artists[artist]["tracks"] += 1
            artists[artist]["albums"].add(album)
            albums.setdefault((artist, album), {"artist": artist, "album": album, "tracks": 0})
            albums[(artist, album)]["tracks"] += 1

    artist_rows = [{**value, "albums": sorted(value["albums"])} for value in artists.values()]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "exists": True,
        "read_only": True,
        "source": "LOCAL_COLLECTION",
        "summary": {"tracks": len(tracks), "artists": len(artist_rows), "albums": len(albums)},
        "artists": sorted(artist_rows, key=lambda row: row["name"].lower()),
        "albums": sorted(albums.values(), key=lambda row: (row["artist"].lower(), row["album"].lower())),
        "tracks": tracks,
        "external_discography": {"status": "NOT_INDEXED", "source": "FULL_DISCOGRAPHY", "items": []},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--music-root", type=Path, default=DEFAULT_MUSIC_ROOT)
    parser.add_argument("--hash", action="store_true", dest="include_hash")
    args = parser.parse_args()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    registry = read_json(OUT_ROOT / "module_registry.json", {"modules": []})
    audit = read_json(OUT_ROOT / "environment_audit.json", {})
    music = build_music_catalog(args.music_root, args.include_hash)
    index = read_json(OUT_ROOT / "index.json", {})
    index.update({
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "modules": registry.get("modules", []),
        "sources": {
            "module_registry": "data/Bible/.internal/sources/knowledge3/module_registry.json",
            "environment_audit": "data/Bible/.internal/sources/knowledge3/environment_audit.json",
            "offline_knowledge": "data/Bible/.internal/sources/offline_knowledge/catalog.json",
        },
        "offline_knowledge": {
            "path": "data/Bible/.internal/sources/offline_knowledge/catalog.json",
            "topics": len(read_json(ROOT / "data/Bible/.internal/sources/offline_knowledge/catalog.json", {}).get("topics", [])),
            "status": "VERIFIED_BY_USER",
        },
        "environment": {
            "audit_generated_at": audit.get("generated_at"),
            "installed_programs": len(audit.get("installed_programs", [])),
        },
        "music": {**index.get("music", {}), "path": "data/Bible/.internal/sources/knowledge3/music_catalog.json", "summary": music.get("summary", {})},
    })
    (OUT_ROOT / "music_catalog.json").write_text(json.dumps(music, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_ROOT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"index": index["music"], "music": music.get("summary", {})}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
