"""Local Voice Production Mentor cards with safe source metadata."""

from __future__ import annotations

import json
import re
from uuid import uuid4
from pathlib import Path

from services.bible_paths import resolve, runtime_path


class VoiceProductionService:
    def __init__(self, backend_dir: Path) -> None:
        self.path = resolve(backend_dir, "data/knowledge3/voice/lessons.json")
        self.sessions_path = runtime_path(Path(backend_dir), "voice_production_sessions.json")
        self.legacy_sessions_path = Path(backend_dir).parent / "data" / "knowledge3" / "voice" / "sessions.json"

    def lessons(self, category: str = "") -> list[dict]:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            rows = []
        category = str(category or "").strip().lower()
        return [row for row in rows if not category or str(row.get("category", "")).lower() == category]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        needle = " ".join(re.sub(r"[^\w\s-]", " ", str(query or "").lower()).split())
        if not needle:
            return []
        result = []
        for row in self.lessons():
            haystack = " ".join(str(row.get(key, "")) for key in ("title", "summary", "text", "category")).lower()
            if needle in haystack or all(word in haystack for word in needle.split()):
                result.append(row)
        return result[: max(1, min(int(limit), 100))]

    def workflow(self, guitars: str = "", scope: str = "", issue: str = "", session_id: str = "", command: str = "") -> dict:
        """Return a deterministic, safe vocal troubleshooting session plan.

        The plan is deliberately read-only: it guides the user through the
        same questions and listening checks a mentor would ask, but it never
        opens Cubase or changes a project without a separately confirmed DAW
        action.
        """
        guitars = str(guitars or "").strip()
        scope = str(scope or "").strip()
        issue = str(issue or "").strip()
        session_id = str(session_id or "").strip() or uuid4().hex[:12]
        sessions = self._read_sessions()
        state = sessions.get(session_id, {"step": 0, "history": []})
        questions = []
        if not guitars:
            questions.append("Какие именно гитары или источники используются?")
        if not scope:
            questions.append("Проблема в отдельной дорожке или на общей шине?")
        if not issue:
            questions.append("Что слышно: резкость, мутность, шум, нехватка атаки или дисбаланс?")
        steps = [
            {"id": "identify_source", "title": "Уточнить источник", "action": "collect_answers", "complete": bool(guitars)},
            {"id": "identify_scope", "title": "Уточнить область проблемы", "action": "collect_answers", "complete": bool(scope)},
            {"id": "identify_issue", "title": "Зафиксировать симптом", "action": "collect_answers", "complete": bool(issue)},
            {"id": "open_cubase", "title": "Предложить открыть Cubase", "action": "confirmation_first", "complete": False},
            {"id": "open_eq", "title": "Предложить открыть Pro-Q 3", "action": "confirmation_first", "complete": False},
            {"id": "find_band", "title": "Найти проблемную область", "action": "read_only_listening", "complete": False},
            {"id": "audition_filter", "title": "Прослушать узкую полосу", "action": "read_only_listening", "complete": False},
            {"id": "apply_filter", "title": "Настроить фильтр после подтверждения", "action": "confirmation_first", "complete": False},
            {"id": "compare_source", "title": "Сравнить с исходником", "action": "read_only_listening", "complete": False},
            {"id": "next_stage", "title": "Перейти к следующему этапу", "action": "guided_follow_up", "complete": False},
        ]
        normalized_command = str(command or "").strip().lower()
        if normalized_command in {"продолжай", "дальше", "следующий", "next"}:
            state["step"] = min(int(state.get("step", 0)) + 1, len(steps) - 1)
        elif normalized_command in {"назад", "верни предыдущую настройку", "предыдущий", "back"}:
            state["step"] = max(int(state.get("step", 0)) - 1, 0)
        elif normalized_command in {"повтори", "повтори последний шаг", "repeat"}:
            state["step"] = max(int(state.get("step", 0)), 0)
        elif normalized_command in {"объясни подробнее", "подробнее", "explain"}:
            state["detail_requested"] = True
        if state.get("history", [])[-1:] != [state["step"]]:
            state.setdefault("history", []).append(state["step"])
            state["history"] = state["history"][-20:]
        sessions[session_id] = state
        self._write_sessions(sessions)
        current_step = steps[state["step"]]
        return {
            "session_id": session_id,
            "read_only": True,
            "requires_confirmation_for_daw": True,
            "inputs": {"guitars": guitars, "scope": scope, "issue": issue},
            "questions": questions,
            "steps": steps,
            "current_step": current_step,
            "current_step_index": state["step"],
            "command": normalized_command,
            "detail_requested": bool(state.get("detail_requested", False)),
            "recommended_lessons": [row["id"] for row in self.lessons()[:3]],
            "status": "needs_user_details" if questions else "ready_for_guided_session",
        }

    def _read_sessions(self) -> dict:
        try:
            path = self.sessions_path if self.sessions_path.is_file() else self.legacy_sessions_path
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

    def _write_sessions(self, sessions: dict) -> None:
        self.sessions_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions_path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
