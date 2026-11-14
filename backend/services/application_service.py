"""Discover and launch installed Windows applications without shell commands."""

from __future__ import annotations

import json
import os
import subprocess
import winreg
from pathlib import Path


APP_ALIASES = {
    "whatsapp": ("whatsapp", "вацап", "ватсап"), "claude": ("claude", "клод"),
    "codex": ("codex", "кодекс"), "figma": ("figma", "фигма"),
    "cubase": ("cubase", "кубейс", "кубейс тринадцать"), "chrome": ("chrome", "хром", "гугл хром"),
    "telegram": ("telegram", "телеграм"), "discord": ("discord", "дискорд"),
    "vscode": ("visual studio code", "vs code", "код", "висуал студио код"),
    "android_studio": ("android studio", "андроид студио"), "github_desktop": ("github desktop", "гитхаб"),
    "spotify": ("spotify", "спотифай"), "yandex_music": ("яндекс музыка", "яндекс", "yandex music"), "steam": ("steam", "стим"), "obs": ("obs", "обс"),
    "filezilla": ("filezilla", "файлзилла"), "notepad++": ("notepad++", "ноутпад"),
    "word": ("microsoft word", "word", "ворд"), "excel": ("microsoft excel", "excel", "эксель"),
    "photoshop": ("photoshop", "фотошоп"), "premiere": ("premiere pro", "премьер"),
    "reaper": ("reaper", "рипер"), "audacity": ("audacity", "аудасити"),
}


class ApplicationService:
    def __init__(self, project_dir: Path):
        self.path = Path(project_dir).parent / "data" / "applications.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.apps: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        try:
            self.apps = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.apps = {}

    def _add(self, key: str, name: str, target: str, launch_type: str) -> None:
        if key not in self.apps or not self.apps[key].get("available"):
            self.apps[key] = {"name": name, "target": target, "launch_type": launch_type, "aliases": APP_ALIASES.get(key, (key,)), "available": True}

    def discover(self) -> dict:
        # Shortcuts are safer than guessing arbitrary executables and cover
        # normal desktop/Start-menu installations.
        shortcut_roots = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path.home() / "Desktop",
        ]
        for root in shortcut_roots:
            if not root.is_dir():
                continue
            for shortcut in root.rglob("*.lnk"):
                stem = shortcut.stem.lower()
                for key, aliases in APP_ALIASES.items():
                    if any(alias.lower() in stem for alias in aliases):
                        self._add(key, shortcut.stem, str(shortcut), "shortcut")
        known = {
            "chrome": [os.environ.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe", os.environ.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe"],
            "telegram": [os.environ.get("APPDATA", "") + r"\Telegram Desktop\Telegram.exe", os.environ.get("LOCALAPPDATA", "") + r"\Telegram Desktop\Telegram.exe"],
            "yandex_music": [str(Path.home() / "AppData/Local/Programs/YandexMusic/Яндекс Музыка.exe")],
            "steam": [os.environ.get("PROGRAMFILES(X86)", "") + r"\Steam\steam.exe"],
        }
        for key, paths in known.items():
            for raw in paths:
                if raw and Path(raw).is_file():
                    self._add(key, key.title(), raw, "executable")
                    break
        for key, item in self.apps.items():
            item["available"] = Path(item["target"]).exists() if item["launch_type"] == "executable" else True
        self.path.write_text(json.dumps(self.apps, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.apps

    def find(self, query: str) -> tuple[str, dict] | None:
        query = query.lower()
        self.load()
        for key, aliases in APP_ALIASES.items():
            if any(alias in query for alias in aliases) and key in self.apps and self.apps[key].get("available"):
                return key, self.apps[key]
        return None

    def launch(self, query: str) -> dict:
        match = self.find(query)
        if not match:
            self.discover()
            match = self.find(query)
        if not match:
            raise FileNotFoundError(f"Приложение не найдено: {query}")
        key, item = match
        if item["launch_type"] == "shortcut":
            os.startfile(item["target"])
        else:
            subprocess.Popen([item["target"]])
        return {"key": key, **item}
