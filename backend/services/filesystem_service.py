"""Local, safe folder/file search for Jarvis voice commands."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path


class AmbiguousPathError(RuntimeError):
    def __init__(self, query: str, candidates: list[Path]):
        self.query = query
        self.candidates = candidates
        super().__init__(f"Несколько совпадений для: {query}")


class FileSystemService:
    EXCLUDED = {"$Recycle.Bin", "System Volume Information", "Windows", "node_modules", ".git", "__pycache__"}
    ALIASES = {
        "документы": "Documents", "мои документы": "Documents", "загрузки": "Downloads",
        "рабочий стол": "Desktop", "музыка": "Music", "видео": "Videos",
        "изображения": "Pictures", "проекты": "C:\\projects", "мой компьютер": "ThisPC",
    }

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.db_path = self.project_dir.parent / "data" / "filesystem_index.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS filesystem_index (
                name TEXT NOT NULL, path TEXT PRIMARY KEY, drive TEXT, object_type TEXT,
                last_seen REAL NOT NULL, last_opened REAL
            )""")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=3)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def roots(self) -> list[Path]:
        user = Path.home()
        roots = [user / name for name in ("Documents", "Downloads", "Desktop", "Music", "Videos", "Pictures")]
        roots += [self.project_dir.parent, Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu"]
        return [root for root in roots if root.is_dir()]

    def index_path(self, path: Path) -> None:
        path = path.resolve()
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO filesystem_index(name,path,drive,object_type,last_seen,last_opened) VALUES(?,?,?,?,?,COALESCE((SELECT last_opened FROM filesystem_index WHERE path=?),NULL))",
                (path.name, str(path), path.drive, "folder" if path.is_dir() else "file", time.time(), str(path)),
            )

    def scan(self, roots: list[Path] | None = None, max_entries: int = 30000) -> int:
        count = 0
        rows = []
        for root in roots or self.roots():
            if not root.is_dir():
                continue
            for current, dirs, files in os.walk(root, topdown=True):
                dirs[:] = [item for item in dirs if item not in self.EXCLUDED and not item.startswith(".")]
                for name in dirs:
                    path = Path(current) / name
                    rows.append((name, str(path), path.drive, "folder", time.time()))
                    count += 1
                    if len(rows) >= 500:
                        with self._connect() as db:
                            db.executemany(
                                "INSERT OR REPLACE INTO filesystem_index(name,path,drive,object_type,last_seen) VALUES(?,?,?,?,?)",
                                rows,
                            )
                        rows.clear()
                    if count >= max_entries:
                        break
                if count >= max_entries:
                    break
            if count >= max_entries:
                break
        if rows:
            with self._connect() as db:
                db.executemany(
                    "INSERT OR REPLACE INTO filesystem_index(name,path,drive,object_type,last_seen) VALUES(?,?,?,?,?)",
                    rows,
                )
        return count

    def _search_db(self, query: str, folders_only: bool = True) -> list[Path]:
        query = " ".join(query.lower().split())
        with self._connect() as db:
            rows = db.execute(
                "SELECT path FROM filesystem_index WHERE lower(name) LIKE ? AND (?=0 OR object_type='folder') ORDER BY length(path)",
                (f"%{query}%", int(folders_only)),
            ).fetchall()
        return [Path(row[0]) for row in rows if Path(row[0]).exists()]

    def find_folder(self, query: str) -> list[Path]:
        query = " ".join(query.lower().replace("папку", "").replace("каталог", "").split()).strip()
        alias = self.ALIASES.get(query)
        if alias == "ThisPC":
            return [Path("\\")]  # Explorer handles this special shell location.
        if alias:
            known = Path.home() / alias if ":\\" not in alias else Path(alias)
            if known.is_dir():
                self.index_path(known)
                return [known]
        matches = self._search_db(query)
        if not matches:
            self.scan(max_entries=12000)
            matches = self._search_db(query)
        return matches[:10]

    def open_folder(self, query: str) -> Path:
        matches = self.find_folder(query)
        if not matches:
            raise FileNotFoundError(f"Папка не найдена: {query}")
        if len(matches) > 1:
            raise AmbiguousPathError(query, matches[:5])
        path = matches[0]
        if str(path) == "\\":
            subprocess.Popen(["explorer.exe", "shell:MyComputerFolder"])
        else:
            os.startfile(str(path))
            with self._connect() as db:
                db.execute("UPDATE filesystem_index SET last_opened=? WHERE path=?", (time.time(), str(path)))
        return path
