import os
import json
import shutil
import time
import threading
from pathlib import Path


class ProjectManager:

    def __init__(self, workspace_root: str):

        self.workspace_root = Path(workspace_root)
        self.projects_dir = self.workspace_root / "projects"

        self.lock = threading.Lock()

        self.current_project = "temp"

        self.projects_dir.mkdir(parents=True, exist_ok=True)

        temp_path = self.projects_dir / "temp"

        if temp_path.exists():
            print("[ProjectManager] clearing temp")
            shutil.rmtree(temp_path)

        self.create_project("temp")


    # ------------------------------------------------
    # PROJECT MANAGEMENT
    # ------------------------------------------------

    def create_project(self, name: str):

        safe = self._sanitize(name)

        path = self.projects_dir / safe

        if path.exists():
            return False, "project exists"

        path.mkdir()

        (path / "cad").mkdir()
        (path / "browser").mkdir()

        metadata = {
            "name": safe,
            "created": time.time()
        }

        with open(path / "project.json", "w") as f:
            json.dump(metadata, f)

        print(f"[ProjectManager] created {safe}")

        return True, safe


    def switch_project(self, name: str):

        safe = self._sanitize(name)

        path = self.projects_dir / safe

        if not path.exists():
            return False, "not found"

        self.current_project = safe

        return True, safe


    def list_projects(self):

        return [
            p.name
            for p in self.projects_dir.iterdir()
            if p.is_dir()
        ]


    # ------------------------------------------------
    # PATHS
    # ------------------------------------------------

    def project_path(self):

        return self.projects_dir / self.current_project


    def cad_path(self):

        return self.project_path() / "cad"


    def browser_path(self):

        return self.project_path() / "browser"


    # ------------------------------------------------
    # CHAT LOG
    # ------------------------------------------------

    def log_chat(self, sender: str, text: str):

        log_file = self.project_path() / "chat_history.jsonl"

        entry = {
            "time": time.time(),
            "sender": sender,
            "text": text
        }

        with self.lock:

            with open(log_file, "a", encoding="utf8") as f:
                f.write(json.dumps(entry) + "\n")


    # ------------------------------------------------
    # CAD
    # ------------------------------------------------

    def save_cad(self, source_path: str, prompt: str):

        if not os.path.exists(source_path):
            return None

        ts = int(time.time())

        safe = self._sanitize(prompt)[:30].replace(" ", "_")

        filename = f"{ts}_{safe}.stl"

        dest = self.cad_path() / filename

        shutil.copy2(source_path, dest)

        return str(dest)


    # ------------------------------------------------
    # BROWSER
    # ------------------------------------------------

    def save_browser_file(self, source_path):

        if not os.path.exists(source_path):
            return None

        name = os.path.basename(source_path)

        dest = self.browser_path() / name

        shutil.copy2(source_path, dest)

        return str(dest)


    # ------------------------------------------------
    # CONTEXT
    # ------------------------------------------------

    def get_project_context(
        self,
        max_file_size=8000,
        max_files=20
    ):

        path = self.project_path()

        lines = []

        files = []

        for root, dirs, fs in os.walk(path):

            for f in fs:

                rel = os.path.relpath(
                    os.path.join(root, f),
                    path
                )

                files.append(rel)

        files = files[:max_files]

        lines.append(f"Project: {self.current_project}")
        lines.append("")

        for rel in files:

            ext = Path(rel).suffix

            if ext not in {
                ".py",
                ".js",
                ".json",
                ".txt",
                ".md",
                ".html",
                ".css"
            }:
                continue

            full = path / rel

            try:

                if full.stat().st_size > max_file_size:
                    continue

                text = full.read_text(errors="ignore")

                lines.append(f"--- {rel} ---")
                lines.append(text)
                lines.append("")

            except:
                pass

        return "\n".join(lines)


    # ------------------------------------------------
    # CHAT HISTORY
    # ------------------------------------------------

    def get_recent_chat(self, limit=10):

        log = self.project_path() / "chat_history.jsonl"

        if not log.exists():
            return []

        lines = log.read_text().splitlines()

        result = []

        for line in lines[-limit:]:

            try:
                result.append(json.loads(line))
            except:
                pass

        return result


    # ------------------------------------------------
    # UTILS
    # ------------------------------------------------

    def _sanitize(self, name):

        return "".join(
            c for c in name
            if c.isalnum() or c in " -_"
        ).strip()