"""Bounded Python sandbox MVP for Coding Developer examples."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from services.bible_paths import resolve


class CodingSandboxService:
    def __init__(self, backend_dir: Path) -> None:
        self.root = resolve(backend_dir, "data/knowledge3/coding_projects")

    def run_python(self, project: str, code: str, timeout: int = 8, filename: str = "main.py") -> dict:
        safe_project = "".join(char for char in str(project) if char.isalnum() or char in "-_ ").strip()[:64]
        if not safe_project:
            raise ValueError("project is required")
        if len(code) > 50000:
            raise ValueError("code is too large")
        timeout = max(1, min(int(timeout), 15))
        project_dir = self.root / safe_project
        project_dir.mkdir(parents=True, exist_ok=True)
        if Path(filename).name != filename or Path(filename).suffix.lower() != ".py":
            raise ValueError("filename должен быть именем .py-файла")
        script = project_dir / filename
        script.write_text(str(code), encoding="utf-8")
        script_abs = script.resolve()
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
        try:
            completed = subprocess.run(
                [sys.executable, str(script_abs)], cwd=str(project_dir), env=env,
                capture_output=True, text=True, timeout=timeout, shell=False,
            )
            return {"ok": completed.returncode == 0, "project": safe_project, "returncode": completed.returncode, "stdout": completed.stdout[-10000:], "stderr": completed.stderr[-10000:], "path": str(script_abs)}
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "project": safe_project, "returncode": None, "stdout": str(exc.stdout or "")[-10000:], "stderr": "timeout", "path": str(script_abs)}

    def run_javascript(self, project: str, code: str, timeout: int = 8, filename: str = "main.js") -> dict:
        """Run a bounded Node script without a shell or package installation."""
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js не найден в PATH")
        safe_project = "".join(char for char in str(project) if char.isalnum() or char in "-_ ").strip()[:64]
        if not safe_project:
            raise ValueError("project is required")
        if len(code) > 50000:
            raise ValueError("code is too large")
        timeout = max(1, min(int(timeout), 15))
        project_dir = self.root / safe_project
        project_dir.mkdir(parents=True, exist_ok=True)
        if Path(filename).name != filename or Path(filename).suffix.lower() != ".js":
            raise ValueError("filename должен быть именем .js-файла")
        script = project_dir / filename
        script.write_text(str(code), encoding="utf-8")
        try:
            completed = subprocess.run(
                [node, str(script.resolve())], cwd=str(project_dir),
                env={"PATH": os.environ.get("PATH", ""), "NODE_NO_WARNINGS": "1"},
                capture_output=True, text=True, timeout=timeout, shell=False,
            )
            return {"ok": completed.returncode == 0, "project": safe_project, "returncode": completed.returncode, "stdout": completed.stdout[-10000:], "stderr": completed.stderr[-10000:], "path": str(script.resolve()), "runtime": "node"}
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "project": safe_project, "returncode": None, "stdout": str(exc.stdout or "")[-10000:], "stderr": "timeout", "path": str(script.resolve()), "runtime": "node"}

    def create_javascript_project(self, project: str, files: dict[str, str], run_tests: bool = True) -> dict:
        """Create a Node project using only local files; never runs npm install."""
        safe_project = "".join(char for char in str(project) if char.isalnum() or char in "-_ ").strip()[:64]
        if not safe_project:
            raise ValueError("project is required")
        if not isinstance(files, dict) or not files:
            raise ValueError("files are required")
        project_dir = (self.root / safe_project).resolve()
        if project_dir.exists():
            raise FileExistsError(f"project already exists: {project_dir}")
        clean: dict[Path, str] = {}
        for name, content in files.items():
            relative = Path(str(name))
            if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in {".js", ".json", ".md", ".txt"}:
                raise ValueError(f"unsupported or unsafe project file: {name}")
            if len(str(content)) > 100000:
                raise ValueError(f"file is too large: {name}")
            clean[relative] = str(content)
        project_dir.mkdir(parents=True, exist_ok=False)
        for relative, content in clean.items():
            target = (project_dir / relative).resolve()
            if project_dir not in target.parents:
                raise ValueError(f"file escapes project: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        readme = project_dir / "README.md"
        if not readme.exists():
            readme.write_text(f"# {safe_project}\n\nСоздано Jarvis Coding Developer без установки внешних пакетов.\n", encoding="utf-8")
        result = {"ok": True, "project": safe_project, "path": str(project_dir), "files": [str(p) for p in clean], "test": None, "runtime": "node"}
        if run_tests and (project_dir / "test.js").is_file():
            result["test"] = self.run_javascript(safe_project, (project_dir / "test.js").read_text(encoding="utf-8"), timeout=15, filename="test.js")
            result["ok"] = bool(result["test"].get("ok"))
        return result

    def create_python_project(self, project: str, files: dict[str, str], run_tests: bool = True) -> dict:
        """Create a new bounded project without overwriting an existing project."""
        safe_project = "".join(char for char in str(project) if char.isalnum() or char in "-_ ").strip()[:64]
        if not safe_project:
            raise ValueError("project is required")
        if not isinstance(files, dict) or not files:
            raise ValueError("files are required")
        project_dir = (self.root / safe_project).resolve()
        if project_dir.exists():
            raise FileExistsError(f"project already exists: {project_dir}")
        clean: dict[Path, str] = {}
        for name, content in files.items():
            relative = Path(str(name))
            if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in {".py", ".md", ".txt", ".json"}:
                raise ValueError(f"unsupported or unsafe project file: {name}")
            if len(str(content)) > 100000:
                raise ValueError(f"file is too large: {name}")
            clean[relative] = str(content)
        project_dir.mkdir(parents=True, exist_ok=False)
        for relative, content in clean.items():
            target = (project_dir / relative).resolve()
            if project_dir not in target.parents:
                raise ValueError(f"file escapes project: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        readme = project_dir / "README.md"
        if not readme.exists():
            readme.write_text(f"# {safe_project}\n\nСоздано Jarvis Coding Developer в изолированной папке.\n", encoding="utf-8")
        result = {"ok": True, "project": safe_project, "path": str(project_dir), "files": [str(p) for p in clean], "test": None}
        if run_tests and (project_dir / "test_main.py").is_file():
            result["test"] = self.run_python(safe_project, (project_dir / "test_main.py").read_text(encoding="utf-8"), timeout=15, filename="test_main.py")
            result["ok"] = bool(result["test"].get("ok"))
        return result
