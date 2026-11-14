"""Fast local intent matcher for pre-generated Jarvis voice responses."""

from __future__ import annotations

import json
import random
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalResponseMatch:
    intent_id: str
    text: str
    audio_path: Path
    score: float


class LocalResponseService:
    """Match safe, pre-generated conversational intents without an LLM call."""

    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.library_dir = self.backend_dir.parent / "data" / "voice_responses"
        self.questions_path = self.library_dir / "questions.json"
        self.state_path = self.library_dir / "selection_state.json"
        self._lock = threading.RLock()
        self._data: dict = {"intents": []}
        self._state: dict[str, list[str]] = {}
        self._questions_mtime_ns = 0
        self._reload()

    def _reload(self) -> None:
        try:
            self._data = json.loads(self.questions_path.read_text(encoding="utf-8"))
            self._questions_mtime_ns = self.questions_path.stat().st_mtime_ns
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {"intents": []}
        try:
            self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._state = {}

    def _refresh_if_changed(self) -> None:
        try:
            if self.questions_path.stat().st_mtime_ns != self._questions_mtime_ns:
                self._reload()
        except OSError:
            pass

    @staticmethod
    def normalize(text: str) -> str:
        return " ".join(str(text or "").lower().replace("ё", "е").split()).strip(" ,.!?;:")

    def _score(self, normalized: str, intent: dict) -> float:
        best = 0.0
        phrases = [intent.get("primary_question", ""), *intent.get("trigger_phrases", [])]
        for phrase in phrases:
            candidate = self.normalize(phrase)
            if not candidate:
                continue
            if normalized == candidate:
                best = max(best, 1.0)
            elif candidate in normalized or normalized in candidate:
                best = max(best, 0.9)
            else:
                left = set(candidate.split())
                right = set(normalized.split())
                if left:
                    best = max(best, len(left & right) / len(left) * 0.82)
        keywords = {self.normalize(item) for item in intent.get("keywords", []) if item}
        if keywords:
            best = max(best, len(keywords & set(normalized.split())) / len(keywords) * 0.78)
        return best

    def match(self, text: str) -> LocalResponseMatch | None:
        normalized = self.normalize(text)
        if not normalized:
            return None
        with self._lock:
            self._refresh_if_changed()
            best_intent: dict | None = None
            best_score = 0.0
            for intent in self._data.get("intents", []):
                # Dynamic intents must go to Ollama/tools. Only Class A is an
                # immediate answer; Class B keeps its command acknowledgement.
                if intent.get("class") != "instant":
                    continue
                score = self._score(normalized, intent)
                if score > best_score:
                    best_intent, best_score = intent, score
            if best_intent is None or best_score < 0.72:
                return None
            previous = self._state.get(best_intent["id"], [])
            ready = [item for item in best_intent.get("responses", []) if item.get("status") == "ready"]
            ready = [item for item in ready if (self.library_dir / item.get("wav", "")).is_file()]
            if not ready:
                return None
            eligible = [item for item in ready if item.get("id") not in previous[-2:]] or ready
            selected = random.choice(eligible)
            selected_id = selected.get("id", "")
            self._state[best_intent["id"]] = [*previous, selected_id][-8:]
            try:
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                self.state_path.write_text(
                    json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except OSError:
                pass
            return LocalResponseMatch(
                intent_id=best_intent["id"],
                text=str(selected.get("text", "")),
                audio_path=self.library_dir / selected["wav"],
                score=best_score,
            )

    def summary(self) -> dict:
        with self._lock:
            self._refresh_if_changed()
        intents = self._data.get("intents", [])
        responses = [item for intent in intents for item in intent.get("responses", [])]
        return {
            "intents": len(intents),
            "responses": len(responses),
            "ready": sum(item.get("status") == "ready" for item in responses),
            "instant_intents": sum(item.get("class") == "instant" for item in intents),
        }
