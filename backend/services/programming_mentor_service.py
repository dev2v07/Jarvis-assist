"""Small persistent Programming Mentor MVP."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.bible_paths import resolve, runtime_path


class ProgrammingMentorService:
    def __init__(self, backend_dir: Path) -> None:
        root = resolve(backend_dir, "data/knowledge3/programming/lessons.json").parent
        self.root = root
        self.lessons_path = resolve(backend_dir, "data/knowledge3/programming/lessons.json")
        self.progress_path = runtime_path(Path(backend_dir), "programming_progress.json")
        self.legacy_progress_path = Path(backend_dir).parent / "data" / "knowledge3" / "programming" / "progress.json"

    def _read(self, path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return fallback

    def lessons(self, language: str = "") -> list[dict[str, Any]]:
        rows = self._read(self.lessons_path, [])
        language = str(language or "").strip().lower()
        return [row for row in rows if not language or str(row.get("language", "")).lower() == language]

    def get(self, lesson_id: str) -> dict[str, Any] | None:
        return next((row for row in self.lessons() if row.get("id") == lesson_id), None)

    def progress(self) -> dict[str, Any]:
        path = self.progress_path if self.progress_path.is_file() else self.legacy_progress_path
        return self._read(path, {"languages": {}, "lessons": {}})

    def save_progress(self, lesson_id: str, completed: bool, score: int = 0, note: str = "") -> dict[str, Any]:
        lesson = self.get(lesson_id)
        if not lesson:
            raise KeyError(lesson_id)
        data = self.progress()
        data.setdefault("lessons", {})[lesson_id] = {
            "completed": bool(completed),
            "score": max(0, min(100, int(score))),
            "note": str(note)[:1000],
        }
        data.setdefault("languages", {}).setdefault(lesson["language"], {"completed": 0})
        data["languages"][lesson["language"]]["completed"] = sum(
            1 for item_id, item in data["lessons"].items()
            if item.get("completed") and self.get(item_id) and self.get(item_id).get("language") == lesson["language"]
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.progress_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def evaluate(self, lesson_id: str, code: str, stdout: str, stderr: str) -> dict[str, Any]:
        """Apply small deterministic checks to the starter Python exercises."""
        lesson = self.get(lesson_id)
        if not lesson:
            raise KeyError(lesson_id)
        source = str(code or "")
        output = str(stdout or "").strip()
        errors = str(stderr or "").strip()
        checks = lesson.get("check", {}).get("criteria", [])
        passed: list[str] = []
        failed: list[str] = []
        rules: list[tuple[str, bool]] = []
        if lesson_id == "python-001-variables-and-types":
            rules = [(checks[0] if len(checks) > 0 else "две переменные", len([line for line in source.splitlines() if "=" in line and not line.lstrip().startswith("#")]) >= 2),
                     (checks[1] if len(checks) > 1 else "строка и число", bool(repr(source).count("'") + repr(source).count('"')) and any(ch.isdigit() for ch in source)),
                     (checks[2] if len(checks) > 2 else "вывод", "print" in source)]
        elif lesson_id == "python-002-conditionals":
            rules = [(checks[0] if len(checks) > 0 else "ветвление", "if" in source and ("elif" in source or "else" in source)),
                     (checks[1] if len(checks) > 1 else "границы", any(op in source for op in ("<", ">", "<=", ">=", "=="))),
                     (checks[2] if len(checks) > 2 else "вывод", "print" in source)]
        elif lesson_id == "python-003-functions":
            rules = [(checks[0] if len(checks) > 0 else "параметры", "def " in source and source.count(",") >= 1),
                     (checks[1] if len(checks) > 1 else "return", "return " in source),
                     (checks[2] if len(checks) > 2 else "вывод", "print" in source)]
        else:
            language = str(lesson.get("language", "")).lower()
            rules = self._static_rules(language, lesson_id, source, checks)
        for criterion, ok in rules:
            (passed if ok else failed).append(criterion)
        if errors:
            failed.append("код завершился с ошибкой")
        score = round(len(passed) / max(len(rules), 1) * 100)
        return {"lesson_id": lesson_id, "passed": not failed, "score": score, "passed_checks": passed, "failed_checks": failed, "stdout": output[:4000], "stderr": errors[:4000]}

    @staticmethod
    def _static_rules(language: str, lesson_id: str, source: str, checks: list[str]) -> list[tuple[str, bool]]:
        """Safe syntax/topic checks for non-Python lessons; never executes submitted code."""
        lower = source.lower()
        has = lambda *parts: all(part.lower() in lower for part in parts)
        if language == "html":
            if lesson_id == "html-002-form":
                return [("form и labels", has("<form", "<label")), ("email required", has("type=", "email", "required")), ("кнопка отправки", has("<button"))]
            if lesson_id == "html-003-accessibility":
                return [("landmarks", has("<nav", "<main")), ("heading", "<h1" in lower or "<h2" in lower), ("link or button", "<a " in lower or "<button" in lower)]
            return [("html structure", has("<html", "<body")), ("heading", "<h1" in lower or "<h2" in lower), ("link", "<a " in lower)]
        if language == "php":
            return [("function", "function" in lower), ("parameters", "$" in source), ("return or query", "return" in lower or "select" in lower)]
        if language == "wordpress":
            return [("WordPress hook", "add_shortcode" in lower or "register_rest_route" in lower), ("safe output", "esc_" in lower or "wp_json_encode" in lower or "sanitize" in lower), ("callback", "function" in lower or "=>" in source)]
        if language in {"react", "react native"}:
            native = language == "react native"
            return [("component", "function" in lower or "const" in lower), ("render", "return" in lower), ("ui primitives", ("view" in lower and "text" in lower) if native else ("title" in lower and "status" in lower))]
        if language == "flutter":
            return [("widget", "statelesswidget" in lower or "statefulwidget" in lower), ("build", "build(" in lower), ("state update or content", "setstate" in lower or "text(" in lower)]
        if language == "git":
            return [("git commands", "git " in lower), ("safe branch workflow", "branch" in lower or "checkout" in lower), ("no forced publication", "push" not in lower or "without push" in lower)]
        if language == "sql":
            if lesson_id == "sql-003-transaction":
                return [("transaction start", "begin" in lower or "start transaction" in lower), ("data change", "update" in lower or "insert" in lower or "delete" in lower), ("commit or rollback", "commit" in lower or "rollback" in lower)]
            return [("select", "select" in lower), ("source table", "from" in lower), ("join or ordering", "join" in lower or "order by" in lower)]
        if language == "fastapi":
            return [("FastAPI import", "fastapi" in lower), ("route", "@app." in lower or "@router." in lower), ("response or error", "return" in lower or "httpexception" in lower)]
        return [(criterion or "topic", bool(source.strip())) for criterion in (checks[:3] or ["non-empty answer"])]
