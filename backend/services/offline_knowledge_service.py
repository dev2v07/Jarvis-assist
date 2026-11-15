"""Read-only local knowledge catalog used before the dynamic LLM route.

The catalog is deliberately separate from the Fish Audio response manifest. A
topic is eligible for an offline answer only when it has a reviewed answer
file/text entry; a catalog record without an answer is informational and is
allowed to fall through to Ollama.
"""

from __future__ import annotations

import json
import random
import re
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OfflineKnowledgeMatch:
    topic_id: str
    category: str
    title: str
    answer: str
    score: float
    audio_path: Path | None = None
    audio_variant: int | None = None


class OfflineKnowledgeService:
    """Small, fast catalog matcher with a safe LLM fallback contract."""

    # The bulk offline import stamped every topic VERIFIED. Only a later,
    # explicit content review may authorize a direct factual answer.
    READY_STATUSES = {"VERIFIED", "TESTED"}

    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.project_root = self.backend_dir.parent
        self._physical_map = self._load_physical_map()
        self.catalog_path = self._canonical_path("data/offline_knowledge/catalog.json")
        self._catalog: dict = {"topics": []}
        self._mtime_ns = 0
        self._selection: dict[str, int] = {}
        self._lock = threading.RLock()
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

    @staticmethod
    def normalize(text: str) -> str:
        text = str(text or "").lower().replace("ё", "е")
        return " ".join(re.sub(r"[^\w\s-]", " ", text).split()).strip()

    def _reload(self) -> None:
        try:
            self._catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            self._mtime_ns = self.catalog_path.stat().st_mtime_ns
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            self._catalog = {"topics": []}
            self._mtime_ns = 0

    def _refresh_if_changed(self) -> None:
        try:
            if self.catalog_path.stat().st_mtime_ns != self._mtime_ns:
                self._reload()
        except OSError:
            pass

    def match(self, text: str) -> OfflineKnowledgeMatch | None:
        """Return only a reviewed answer; empty catalog records never match."""
        self._refresh_if_changed()
        normalized = self.normalize(text)
        if not normalized:
            return None
        best: tuple[dict | None, float] = (None, 0.0)
        words = set(normalized.split())
        for topic in self._catalog.get("topics", []):
            if topic.get("alias_of"):
                continue
            # Reviewed child answers are owned by KnowledgeSearchService.
            # Serving old `answers` here would pair revised text with legacy
            # WAV files that have not been checked against that text.
            if topic.get("response_variations"):
                continue
            if str(topic.get("status", "")).upper() not in self.READY_STATUSES:
                continue
            review = topic.get("quality_review") or {}
            if not isinstance(review, dict) or str(review.get("status", "")).upper() not in self.READY_STATUSES:
                continue
            # Legacy bulk metadata marks all 405 topics VERIFIED, but 402 of
            # them have no source at all. Keep them searchable for research;
            # do not serve them as reviewed factual answers.
            if not topic.get("sources"):
                continue
            answers = [str(item).strip() for item in topic.get("answers", []) if str(item).strip()]
            if not answers:
                continue
            candidates = [topic.get("title", ""), *topic.get("prompts", [])]
            for candidate in candidates:
                phrase = self.normalize(candidate)
                if not phrase:
                    continue
                phrase_words = set(phrase.split())
                score = 1.0 if normalized == phrase else len(words & phrase_words) / max(len(phrase_words), 1) * 0.82
                if phrase in normalized or normalized in phrase:
                    score = max(score, 0.9)
                if score > best[1]:
                    best = (topic, score)
        if best[0] is None or best[1] < 0.78:
            return None
        topic = best[0]
        answers = [str(item).strip() for item in topic.get("answers", []) if str(item).strip()]
        # A topic is eligible for instant playback only when its catalog status
        # and the selected concrete WAV both say it is ready. The physical
        # offline_knowledge/audio tree remains separate from voice_responses.
        ready_audio = []
        for item in topic.get("audio", []):
            if str(item.get("status", "")).lower() != "ready":
                continue
            relative = Path(str(item.get("path", "")))
            candidate = relative if relative.is_absolute() else self._canonical_path(str(relative).replace("\\", "/"))
            if candidate.is_file() and candidate.stat().st_size > 44:
                ready_audio.append((item, candidate))
        selected_audio = None
        if ready_audio:
            previous = self._selection.get(str(topic.get("id", "")), -1)
            choices = [pair for pair in ready_audio if int(pair[0].get("variant", -1)) != previous] or ready_audio
            selected_audio = random.choice(choices)
            self._selection[str(topic.get("id", ""))] = int(selected_audio[0].get("variant", 0))
        selected_variant = int(selected_audio[0].get("variant", 0)) if selected_audio else None
        selected_answer = answers[selected_variant - 1] if selected_variant and selected_variant <= len(answers) else answers[0]
        return OfflineKnowledgeMatch(
            topic_id=str(topic.get("id", "")),
            category=str(topic.get("category", "")),
            title=str(topic.get("title", "")),
            answer=selected_answer,
            score=best[1],
            audio_path=selected_audio[1] if selected_audio else None,
            audio_variant=selected_variant,
        )

    def summary(self) -> dict:
        self._refresh_if_changed()
        topics = list(self._catalog.get("topics", []))
        return {
            "topics": len(topics),
            "reviewed_topics": sum(bool(topic.get("answers")) for topic in topics),
            "pending_topics": sum(not bool(topic.get("answers")) for topic in topics),
            "categories": sorted({str(topic.get("category", "")) for topic in topics if topic.get("category")}),
            "source": self._catalog.get("source", "local"),
        }
