"""Fast local intent matcher for pre-generated Jarvis voice responses."""

from __future__ import annotations

import json
import random
import threading
from dataclasses import dataclass
from pathlib import Path

from services.bible_paths import runtime_path


@dataclass(frozen=True)
class LocalResponseMatch:
    intent_id: str
    intent_class: str
    text: str
    audio_path: Path
    score: float


class LocalResponseService:
    """Match safe, pre-generated conversational intents without an LLM call."""

    _selection_lock = threading.RLock()

    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.project_root = self.backend_dir.parent
        self.legacy_library_dir = self.project_root / "data" / "voice_responses"
        self.library_dir = self.project_root / "data" / "Bible" / "materials" / "voice_responses"
        self._physical_map = self._load_physical_map()
        self.questions_path = self._canonical_path("data/voice_responses/questions.json")
        self.state_path = runtime_path(self.backend_dir, "selection_state.json")
        self.legacy_state_path = self.legacy_library_dir / "selection_state.json"
        self._lock = threading.RLock()
        self._data: dict = {"intents": []}
        self._state: dict[str, list[str]] = {}
        self._questions_mtime_ns = 0
        self._reload()

    def _load_physical_map(self) -> dict[str, Path]:
        manifest_path = self.project_root / "data" / "Bible" / "index" / "physical_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return {
            str(item.get("source")): self.project_root / str(item.get("canonical"))
            for item in manifest.get("records", [])
            if item.get("source") and item.get("canonical")
        }

    def _canonical_path(self, source_path: str) -> Path:
        return self._physical_map.get(source_path, self.project_root / source_path)

    def _audio_path(self, wav: str) -> Path:
        return self._canonical_path(f"data/voice_responses/{wav}")

    def _reload(self) -> None:
        try:
            self._data = json.loads(self.questions_path.read_text(encoding="utf-8"))
            self._questions_mtime_ns = self.questions_path.stat().st_mtime_ns
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {"intents": []}
        try:
            state_path = self.state_path if self.state_path.is_file() else self.legacy_state_path
            self._state = json.loads(state_path.read_text(encoding="utf-8"))
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
            # A lone generic keyword such as "сколько" must not hijack a
            # factual question like "сколько памяти у Intel 80386". Apply
            # keyword recall only for a one-word utterance or when an intent
            # phrase already has meaningful overlap with the question.
            if normalized in keywords or best >= 0.45:
                best = max(best, len(keywords & set(normalized.split())) / len(keywords) * 0.78)
        return best

    def match(self, text: str, allowed_classes: set[str] | None = None) -> LocalResponseMatch | None:
        normalized = self.normalize(text)
        if not normalized:
            return None
        with self._selection_lock, self._lock:
            self._refresh_if_changed()
            # Main chat and VoiceRuntime each hold a service instance. Refresh
            # the shared selection file under one process-wide lock so the
            # second instance cannot rotate from stale in-memory history.
            try:
                state_path = self.state_path if self.state_path.is_file() else self.legacy_state_path
                self._state = json.loads(state_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                self._state = {}
            best_intent: dict | None = None
            best_score = 0.0
            for intent in self._data.get("intents", []):
                # Dynamic intents must go to Ollama/tools. Only Class A is an
                # immediate answer; Class B keeps its command acknowledgement.
                if intent.get("class") not in (allowed_classes or {"instant"}):
                    continue
                score = self._score(normalized, intent)
                if score > best_score:
                    best_intent, best_score = intent, score
            if best_intent is None or best_score < 0.72:
                return None
            previous = self._state.get(best_intent["id"], [])
            ready = [
                item for item in best_intent.get("responses", [])
                if item.get("status") == "ready"
                and item.get("generation_status", "AUDIO_READY") == "AUDIO_READY"
                and item.get("enabled", True) is not False
            ]
            ready = [item for item in ready if self._audio_path(str(item.get("wav", ""))).is_file()]
            if not ready:
                return None
            # Prefer a full-cycle rotation.  The old two-item window still
            # allowed a response to return on the third request, which made a
            # ten-variant group sound repetitive.  Keep every other ready
            # response out of the candidate set until the cycle is exhausted;
            # the fallback is only relevant when persisted history is stale or
            # contains ids that no longer exist.
            recent_window = max(1, min(len(ready) - 1, len(ready)))
            recent_ids = set(previous[-recent_window:])
            eligible = [item for item in ready if item.get("id") not in recent_ids] or ready
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
                intent_class=str(best_intent.get("class", "instant")),
                text=str(selected.get("text", "")),
                audio_path=self._audio_path(str(selected["wav"])),
                score=best_score,
            )

    def summary(self) -> dict:
        with self._lock:
            self._refresh_if_changed()
        intents = self._data.get("intents", [])
        responses = [item for intent in intents for item in intent.get("responses", [])]
        audit = {}
        try:
            audit = json.loads(self._canonical_path("data/voice_responses/variation_audit.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return {
            "intents": len(intents),
            "responses": len(responses),
            "ready": sum(item.get("status") == "ready" for item in responses),
            "pending": sum(item.get("status") in {"pending", "generating"} for item in responses),
            "errors": sum(item.get("status") == "error" for item in responses),
            "instant_intents": sum(item.get("class") == "instant" for item in intents),
            "exact_duplicate_items": audit.get("exact_duplicate_items"),
            "near_duplicate_pairs_same_intent": audit.get("near_duplicate_pairs_same_intent"),
        }
