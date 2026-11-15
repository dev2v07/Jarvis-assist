"""Read-only Phase 0 audit for Knowledge & Creative Intelligence 3.0."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from bible_paths import MATERIALS
OUT = MATERIALS


def registry_uninstall() -> list[dict]:
    if sys.platform != "win32":
        return []
    import winreg

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    found: dict[str, dict] = {}
    for hive, root in locations:
        try:
            with winreg.OpenKey(hive, root) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            values = {}
                            for value_index in range(winreg.QueryInfoKey(subkey)[1]):
                                name, value, _ = winreg.EnumValue(subkey, value_index)
                                values[name] = value
                            display = str(values.get("DisplayName", "")).strip()
                            if display:
                                found[display.lower()] = {
                                    "name": display,
                                    "version": str(values.get("DisplayVersion", "")),
                                    "publisher": str(values.get("Publisher", "")),
                                    "install_location": str(values.get("InstallLocation", "")),
                                    "uninstall": str(values.get("UninstallString", "")),
                                }
                    except OSError:
                        continue
        except OSError:
            continue
    return sorted(found.values(), key=lambda item: item["name"].lower())


def scan_paths() -> dict:
    candidates = {
        "music_collection": [Path("E:/Музыка")],
        "vst2": [Path("C:/Program Files/VstPlugins"), Path("C:/Program Files/Steinberg/VstPlugins"), Path("C:/Program Files (x86)/VstPlugins")],
        "vst3": [Path("C:/Program Files/Common Files/VST3"), Path("C:/Program Files/Common Files/Steinberg/VST3")],
        "audio_apps": [Path("C:/Program Files/Steinberg"), Path("C:/Program Files/REAPER (x64)")],
    }
    result: dict[str, dict] = {}
    for group, paths in candidates.items():
        entries = []
        for path in paths:
            if not path.exists():
                entries.append({"path": str(path), "exists": False})
                continue
            files = 0
            extensions: dict[str, int] = {}
            try:
                for item in path.rglob("*"):
                    if item.is_file():
                        files += 1
                        ext = item.suffix.lower() or "[no extension]"
                        extensions[ext] = extensions.get(ext, 0) + 1
            except OSError:
                pass
            entries.append({"path": str(path), "exists": True, "files": files, "extensions": extensions})
        result[group] = {"paths": entries}
    music = Path("E:/Музыка")
    if music.exists():
        audio_ext = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma"}
        tracks = 0
        artists: set[str] = set()
        albums: set[str] = set()
        try:
            for item in music.rglob("*"):
                if item.is_file() and item.suffix.lower() in audio_ext:
                    tracks += 1
                    parts = item.relative_to(music).parts
                    if len(parts) > 1:
                        artists.add(parts[0])
                    if len(parts) > 2:
                        albums.add(parts[1])
        except OSError:
            pass
        result["music_collection"].update({"tracks": tracks, "artists_by_folder": len(artists), "albums_by_folder": len(albums), "read_only": True})
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "installed_programs": registry_uninstall(),
        "paths": scan_paths(),
        "notes": [
            "This is an inventory only; no files, projects, plugins or audio were changed.",
            "Plugin documentation and versions require a second, product-specific audit.",
        ],
    }
    (OUT / "environment_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"programs": len(payload["installed_programs"]), "groups": list(payload["paths"]), "output": str(OUT / "environment_audit.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
