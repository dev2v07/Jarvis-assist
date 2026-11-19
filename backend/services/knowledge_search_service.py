"""Fast read-only search over the shared local knowledge sources."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from services.local_response_service import LocalResponseService
from services.conversation_resolver import ConversationResolver
from services.bible_paths import runtime_path


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", str(value or "").lower().replace("ё", "е")).split())


QUERY_FILLER = {"что", "такое", "как", "почему", "зачем", "ли", "и", "в", "на", "о", "об", "от", "для", "это", "мне"}


def focus_query(query: str) -> str:
    words = [word for word in query.split() if word not in QUERY_FILLER]
    return " ".join(words) if words else query


def token_score(query: str, haystack: str) -> float:
    """Small language-tolerant lexical score for cross-module questions."""
    if not query or not haystack:
        return 0.0
    if query in haystack:
        return 1.0
    query_tokens = focus_query(query).split()
    hay_tokens = set(haystack.split())
    matched = 0
    for token in query_tokens:
        if token in hay_tokens:
            matched += 1
            continue
        stem = token[:4] if len(token) >= 4 else token
        if stem and any(candidate.startswith(stem) or stem.startswith(candidate[:4]) for candidate in hay_tokens if len(candidate) >= 4):
            matched += 1
    return matched / max(1, len(query_tokens))


def matches_query(query: str, haystack: str) -> bool:
    score = token_score(query, haystack)
    return score >= (0.5 if len(focus_query(query).split()) <= 2 else 0.33)


class KnowledgeSearchService:
    def __init__(self, backend_dir: Path, local_responses: LocalResponseService | None = None) -> None:
        root = Path(backend_dir).parent
        self.project_root = root
        self.bible_manifest_path = root / "data" / "Bible" / "index" / "catalog.json"
        manifest = self._read(self.bible_manifest_path, {})
        manifest_sources = manifest.get("sources", {}) if isinstance(manifest, dict) else {}
        physical_manifest = self._read(root / "data" / "Bible" / "index" / "physical_manifest.json", {})
        self._physical_map = {
            str(item.get("source")): root / str(item.get("canonical"))
            for item in physical_manifest.get("records", [])
            if item.get("source") and item.get("canonical")
        } if isinstance(physical_manifest, dict) and physical_manifest.get("records") else {}

        def source_path(key: str, fallback: str) -> Path:
            relative = str(manifest_sources.get(key) or fallback)
            if relative in self._physical_map:
                return self._physical_map[relative]
            candidate = Path(relative)
            return candidate if candidate.is_absolute() else root / candidate

        self.conversational_path = source_path("voice_questions", "data/voice_responses/questions.json")
        self.offline_path = source_path("offline_catalog", "data/offline_knowledge/catalog.json")
        self.music_path = source_path("knowledge3_music", "data/knowledge3/music_catalog.json")
        self.music_reference_path = source_path("knowledge3_music_reference", "data/knowledge3/music/reference_catalog.json")
        self.programming_path = source_path("knowledge3_programming", "data/knowledge3/programming/lessons.json")
        self.voice_path = source_path("knowledge3_voice", "data/knowledge3/voice/lessons.json")
        self.guitar_path = source_path("knowledge3_guitar", "data/knowledge3/guitar/catalog.json")
        self.psychology_path = source_path("knowledge3_psychology", "data/knowledge3/psychology/cards.json")
        self.literature_path = source_path("knowledge3_literature", "data/knowledge3/literature/catalog.json")
        self.audio_path = source_path("knowledge3_audio", "data/knowledge3/audio/plugin_registry.json")
        self.audio_lessons_path = source_path("knowledge3_audio_lessons", "data/knowledge3/audio/lessons.json")
        self.mixing_path = source_path("knowledge3_mixing", "data/knowledge3/mixing/catalog.json")
        self.daw_path = source_path("knowledge3_daw", "data/knowledge3/daw/catalog.json")
        self.self_learning_path = source_path(
            "self_learning", "data/Bible/.internal/sources/self_learning/catalog.json"
        )
        self.variant_state_path = runtime_path(Path(backend_dir), "variant_selection_state.json")
        self.legacy_variant_state_path = root / "data" / "knowledge3" / "variant_selection_state.json"
        # Keep the last three choices blocked. This prevents immediate and
        # short-cycle repeats while still allowing a topic with four variants
        # to answer again once its rotation has been exhausted.
        self.variant_history_limit = 3
        self._local_responses = local_responses or LocalResponseService(Path(backend_dir))
        self._conversation_resolver = ConversationResolver()

    @staticmethod
    def _read(path: Path, fallback: dict | list) -> dict | list:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _offline_content_status(row: dict) -> str:
        if not row.get("sources"):
            return "RESEARCH_REQUIRED"
        review = row.get("quality_review") or {}
        if isinstance(review, dict) and str(review.get("status", "")).upper() in {"VERIFIED", "TESTED"}:
            return str(review["status"]).upper()
        return "SOURCE_REVIEW"

    def catalog(self) -> dict:
        """Build one read-only record map from the existing physical owners.

        Records contain locations and links, never a second persisted copy of
        knowledge text or audio. Legacy IDs remain available for migration.
        """
        records: list[dict] = []
        collisions: list[str] = []
        seen: set[str] = set()
        specs = (
            (self.offline_path, "topics", "offline", "topic", "title"),
            (self.conversational_path, "intents", "voice", "intent", "primary_question"),
            (self.programming_path, None, "knowledge3", "programming", "title"),
            (self.voice_path, None, "knowledge3", "voice_production", "title"),
            (self.guitar_path, "models", "knowledge3", "guitar", "model"),
            (self.psychology_path, "cards", "knowledge3", "psychology", "title"),
            (self.literature_path, "works", "knowledge3", "literature", "title"),
            (self.audio_lessons_path, None, "knowledge3", "audio_lesson", "title"),
            (self.audio_path, "products", "knowledge3", "plugin", "name"),
            (self.mixing_path, "cards", "knowledge3", "mixing", "title"),
            (self.daw_path, "cards", "knowledge3", "daw", "title"),
            (self.music_reference_path, "artists", "knowledge3", "music_reference", "name"),
            (self.self_learning_path, "entries", "self_learning", "self_learning", "title"),
        )
        project_root = self.project_root
        for path, key, namespace, kind, title_key in specs:
            payload = self._read(path, [] if key is None else {})
            rows = payload if key is None else payload.get(key, []) if isinstance(payload, dict) else []
            for index, row in enumerate(rows if isinstance(rows, list) else []):
                if not isinstance(row, dict):
                    continue
                legacy_id = str(row.get("id") or row.get("name") or f"row-{index:04d}")
                canonical_id = f"{namespace}:{kind}:{normalize(legacy_id).replace(' ', '-')}"
                if canonical_id in seen:
                    collisions.append(canonical_id)
                    canonical_id = f"{canonical_id}:source-{index}"
                seen.add(canonical_id)
                raw_sources = row.get("sources", [])
                source_ids = [str(value.get("url") if isinstance(value, dict) else value)
                              for value in raw_sources if value]
                variants = row.get("response_variations", [])
                if namespace == "offline":
                    variants = row.get("response_variations") or row.get("answers", [])
                    audio_links = [{"variant_id": f"{canonical_id}:v{int(a.get('variant', n + 1)):02d}",
                                    "path": a.get("path"), "status": a.get("status")}
                                   for n, a in enumerate(row.get("audio", [])) if isinstance(a, dict)]
                    effective_status = self._offline_content_status(row)
                elif namespace == "voice":
                    variants = row.get("responses", [])
                    audio_links = [{"variant_id": f"{canonical_id}:{v.get('id', n)}",
                                    "path": f"data/Bible/.internal/audio/responses/{v['wav']}" if v.get("wav") else None,
                                    "status": v.get("generation_status") or v.get("status")}
                                   for n, v in enumerate(variants) if isinstance(v, dict)]
                    effective_status = "AUDIT_REQUIRED"
                else:
                    audio_links = ([{"variant_id": canonical_id, "path": row.get("audio_path"),
                                     "status": row.get("audio_status")}]
                                   if row.get("audio_path") else [])
                    audio_links.extend({"variant_id": str(v.get("variant_id")), "path": v.get("audio_path"),
                                        "status": v.get("audio_status")}
                                       for v in variants if isinstance(v, dict) and v.get("audio_path"))
                    effective_status = str(row.get("status") or "AUDIT_REQUIRED")
                    if not source_ids and effective_status == "VERIFIED":
                        effective_status = "RESEARCH_REQUIRED"
                if row.get("alias_of"):
                    effective_status = "OUTDATED"
                records.append({
                    "canonical_id": canonical_id,
                    "legacy_id": legacy_id,
                    "alias_of": row.get("alias_of"),
                    "kind": kind,
                    "title": str(row.get(title_key) or legacy_id),
                    "category": str(row.get("category") or kind),
                    "subcategory": row.get("subcategory"),
                    "source_location": str(path.relative_to(project_root)).replace("\\", "/"),
                    "source_index": index,
                    "source_ids": source_ids,
                    "recorded_status": row.get("status"),
                    "content_status": effective_status,
                    "audio_links": audio_links,
                    "variant_count": len(variants) if isinstance(variants, list) else 0,
                    "updated_at": row.get("updated_at") or row.get("verified_at"),
                    "version": row.get("version", 1),
                    "derived_id": not bool(row.get("id") or row.get("name")),
                })
        music = self._read(self.music_path, {})
        for index, track in enumerate(music.get("tracks", []) if isinstance(music, dict) else []):
            relative = str(track.get("relative_path") or track.get("path") or index)
            stable_part = hashlib.sha256(relative.casefold().encode("utf-8")).hexdigest()[:20]
            canonical_id = f"knowledge3:local_track:{stable_part}"
            if canonical_id in seen:
                collisions.append(canonical_id)
                canonical_id = f"{canonical_id}:source-{index}"
            seen.add(canonical_id)
            records.append({
                "canonical_id": canonical_id, "legacy_id": relative, "kind": "local_track",
                "title": str(track.get("title") or relative), "category": "local_music",
                "subcategory": track.get("artist"), "source_location": str(self.music_path.relative_to(project_root)).replace("\\", "/"),
                "source_index": index, "source_ids": ["LOCAL_COLLECTION"],
                "recorded_status": track.get("status"), "content_status": "DISCOVERED",
                "audio_links": [], "variant_count": 0, "updated_at": music.get("generated_at"),
                "version": music.get("version", 1), "derived_id": True,
            })
        for collection, kind in (("artists", "local_artist"), ("albums", "local_album")):
            for index, item in enumerate(music.get(collection, []) if isinstance(music, dict) else []):
                identity = (str(item.get("name") or "") if kind == "local_artist"
                            else f"{item.get('artist', '')}\x1f{item.get('album', '')}")
                stable_part = hashlib.sha256(identity.casefold().encode("utf-8")).hexdigest()[:20]
                canonical_id = f"knowledge3:{kind}:{stable_part}"
                if canonical_id in seen:
                    collisions.append(canonical_id)
                    exact_part = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
                    canonical_id = f"{canonical_id}:{exact_part}"
                    if canonical_id in seen:
                        canonical_id = f"{canonical_id}:source-{index}"
                seen.add(canonical_id)
                records.append({
                    "canonical_id": canonical_id, "legacy_id": identity, "kind": kind,
                    "title": str(item.get("name") or item.get("album") or identity),
                    "category": "local_music", "subcategory": item.get("artist"),
                    "source_location": str(self.music_path.relative_to(project_root)).replace("\\", "/"),
                    "source_index": index, "source_ids": ["LOCAL_COLLECTION"],
                    "recorded_status": item.get("status"), "content_status": "DISCOVERED",
                    "audio_links": [], "variant_count": 0, "updated_at": music.get("generated_at"),
                    "version": music.get("version", 1), "derived_id": True,
                })
        return {"records": records, "count": len(records), "collisions": collisions}

    def get(self, canonical_id: str) -> dict | None:
        """Resolve a canonical record to its owning source row on demand."""
        record = next((item for item in self.catalog()["records"] if item["canonical_id"] == canonical_id), None)
        if record is None:
            return None
        path = self.project_root / record["source_location"]
        payload = self._read(path, {})
        if record["kind"] in {"local_track", "local_artist", "local_album"}:
            key = {"local_track": "tracks", "local_artist": "artists", "local_album": "albums"}[record["kind"]]
            rows = payload.get(key, []) if isinstance(payload, dict) else []
        elif isinstance(payload, list):
            rows = payload
        else:
            key = {"topic": "topics", "intent": "intents", "guitar": "models",
                   "psychology": "cards", "literature": "works", "plugin": "products",
                   "mixing": "cards", "daw": "cards", "music_reference": "artists",
                   "self_learning": "entries"}.get(record["kind"])
            rows = payload.get(key, []) if key and isinstance(payload, dict) else []
        index = record["source_index"]
        return {"record": record, "content": rows[index]} if 0 <= index < len(rows) else None

    def _variant_state(self) -> dict:
        state_path = self.variant_state_path if self.variant_state_path.is_file() else self.legacy_variant_state_path
        state = self._read(state_path, {})
        if not isinstance(state, dict):
            state = {}
        state.setdefault("version", 1)
        state.setdefault("recent_variant_ids", [])
        state.setdefault("usage", {})
        return state

    def _recent_variant_ids(self) -> set[str]:
        state = self._variant_state()
        return {str(value) for value in state.get("recent_variant_ids", []) if value}

    def _mark_variant_used(self, variant_id: str | None) -> None:
        """Persist a small local history; never touches any knowledge catalog."""
        if not variant_id:
            return
        state = self._variant_state()
        value = str(variant_id)
        recent = [item for item in state.get("recent_variant_ids", []) if str(item) != value]
        recent.append(value)
        state["recent_variant_ids"] = recent[-self.variant_history_limit :]
        usage = state.setdefault("usage", {})
        usage[value] = int(usage.get(value, 0)) + 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.variant_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.variant_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def search(self, query: str, limit: int = 20) -> list[dict]:
        needle = normalize(query)
        if not needle:
            return []
        results: list[dict] = []
        conversational = self._read(self.conversational_path, {})
        self._append_conversational(results, needle, conversational)
        offline = self._read(self.offline_path, {})
        offline_topics = offline.get("topics", []) if isinstance(offline, dict) else []
        # Reviewed children are searched by their own question and answer.
        # Legacy answers and WAV links remain in the parent for research, but
        # are never silently paired with a new verified child text.
        offline_rows = [{**topic, "status": self._offline_content_status(topic)}
                        for topic in offline_topics if isinstance(topic, dict) and not topic.get("alias_of")]
        reviewed_topics = [row for row in offline_rows if row["status"] in {"VERIFIED", "TESTED"}]
        research_topics = [row for row in offline_rows if row["status"] not in {"VERIFIED", "TESTED"}]
        self._append_cards(results, needle, reviewed_topics, "offline_knowledge",
                           ("title", "text", "prompts", "variant_kind"), 0.95)
        self._append_cards(results, needle, research_topics, "offline_knowledge",
                           ("title", "text", "prompts", "variant_kind"), 0.45)
        lessons = self._read(self.programming_path, [])
        for lesson in lessons if isinstance(lessons, list) else []:
            haystack = normalize(" ".join([str(lesson.get("title", "")), str(lesson.get("summary", "")), str(lesson.get("language", ""))]))
            if matches_query(needle, haystack):
                results.append({"kind": "programming_lesson", "id": lesson.get("id"), "title": lesson.get("title"), "answer": lesson.get("explanation") or lesson.get("summary"), "sources": lesson.get("sources", []), "status": lesson.get("status"), "audio_status": lesson.get("audio_status"), "audio_path": lesson.get("audio_path"), "has_audio": lesson.get("audio_status") == "AUDIO_READY", "score": round(0.95 * token_score(needle, haystack), 3)})
        music = self._read(self.music_path, {})
        for row in music.get("artists", []) + music.get("albums", []) if isinstance(music, dict) else []:
            haystack = normalize(" ".join(str(value) for value in row.values() if isinstance(value, (str, int))))
            if matches_query(needle, haystack):
                results.append({"kind": "local_music", "title": row.get("name") or row.get("album"), "artist": row.get("artist"), "answer": f"Локальная коллекция: {row.get('name') or row.get('album')}", "sources": ["data/Bible/.internal/sources/knowledge3/music_catalog.json"], "score": round(0.7 * token_score(needle, haystack), 3)})
        reference = self._read(self.music_reference_path, {})
        for artist in self._expand_variants(reference.get("artists", []) if isinstance(reference, dict) else []):
            haystack = normalize(self._searchable_text(artist, ("name", "albums", "text", "summary")))
            if matches_query(needle, haystack):
                album_titles = ", ".join(str(album.get("title", "")) for album in artist.get("albums", []) if album.get("title"))
                results.append({"kind": "external_music_reference", "id": artist.get("id") or artist.get("variant_id") or artist.get("name"), "parent_id": artist.get("parent_id"), "variant_kind": artist.get("variant_kind"), "title": artist.get("name"), "answer": KnowledgeSearchService._answer_text(artist) or f"Reference-дискография {artist.get('name')}: {album_titles}", "albums": artist.get("albums", []), "sources": artist.get("sources", []), "status": artist.get("status") or "AUDIT_REQUIRED", "score": round(0.75 * token_score(needle, haystack), 3), "read_only": True})
        self._append_cards(results, needle, self._read(self.voice_path, []), "voice_production", ("title", "summary", "text", "category"), 0.88)
        self._append_cards(results, needle, self._read(self.guitar_path, {}).get("models", []), "guitar", ("brand", "series", "model", "summary", "use_cases", "text", "variant_kind"), 0.84)
        psychology = self._read(self.psychology_path, {})
        self._append_cards(results, needle, psychology.get("cards", []) if isinstance(psychology, dict) else [], "psychology", ("topic", "title", "text", "exercise"), 0.86)
        literature = self._read(self.literature_path, {})
        self._append_cards(results, needle, literature.get("works", []) if isinstance(literature, dict) else [], "literature", ("author", "title", "summary", "topics", "text", "variant_kind"), 0.82)
        audio = self._read(self.audio_path, {})
        self._append_cards(results, needle, audio.get("products", []) if isinstance(audio, dict) else [], "music_production", ("name", "publisher", "category", "function", "version"), 0.80)
        self._append_cards(results, needle, self._read(self.audio_lessons_path, []), "music_production_lesson", ("title", "summary", "text", "topics", "category"), 0.86)
        mixing = self._read(self.mixing_path, {})
        self._append_cards(results, needle, mixing.get("cards", []) if isinstance(mixing, dict) else [], "mixing", ("title", "summary", "topics", "text", "variant_kind"), 0.88)
        daw = self._read(self.daw_path, {})
        self._append_cards(results, needle, daw.get("cards", []) if isinstance(daw, dict) else [], "daw", ("title", "summary", "topics"), 0.87)
        self_learning = self._read(self.self_learning_path, {})
        self._append_cards(
            results, needle,
            self_learning.get("entries", []) if isinstance(self_learning, dict) else [],
            "self_learning", ("title", "summary", "content", "facts", "steps"), 0.72,
        )
        results.sort(key=lambda item: item.get("score", 0), reverse=True)
        # For multi-topic requests, keep the strongest result from each module
        # visible before filling the remaining slots by score.
        diversified: list[dict] = []
        seen_kinds: set[str] = set()
        for item in results:
            kind = str(item.get("kind", ""))
            if kind not in seen_kinds:
                diversified.append(item)
                seen_kinds.add(kind)
        diversified.extend(item for item in results if item not in diversified)
        return diversified[: max(1, min(int(limit), 100))]

    def _append_conversational(self, results: list[dict], query: str, payload: dict | list) -> None:
        """Expose the existing conversational library as the first search source.

        This is a non-mutating lookup: unlike runtime selection it does not
        advance response rotation or write selection state.
        """
        intents = payload.get("intents", []) if isinstance(payload, dict) else []
        best: tuple[dict, float] | None = None
        for intent in intents:
            if intent.get("class") != "instant":
                continue
            phrases = [intent.get("primary_question", ""), *intent.get("trigger_phrases", [])]
            score = 0.0
            for phrase in phrases:
                candidate = normalize(phrase)
                if not candidate:
                    continue
                if query == candidate:
                    score = max(score, 1.0)
                elif candidate in query or query in candidate:
                    score = max(score, 0.92)
                else:
                    score = max(score, 0.82 * len(set(query.split()) & set(candidate.split())) / max(1, len(set(candidate.split()))))
            if score >= 0.72 and (best is None or score > best[1]):
                best = (intent, score)
        if best is None:
            return
        intent, score = best
        recent = self._recent_variant_ids()
        ready_candidates = [item for item in intent.get("responses", [])
                            if item.get("status") == "ready" and item.get("wav")
                            and item.get("generation_status", "AUDIO_READY") == "AUDIO_READY"
                            and item.get("enabled", True) is not False
                            and self._physical_reference(f"data/Bible/.internal/audio/responses/{item['wav']}")
                            and Path(self._physical_reference(f"data/Bible/.internal/audio/responses/{item['wav']}")).is_file()]
        ready = next((item for item in ready_candidates if str(item.get("id", "")) not in recent), None)
        if ready is None:
            ready = ready_candidates[0] if ready_candidates else None
        results.append({
            "kind": "conversational",
            "id": intent.get("id"),
            "title": intent.get("primary_question") or intent.get("category"),
            "category": intent.get("category"),
            "status": "AUDIO_READY" if ready else "TEXT_READY",
            "has_audio": bool(ready),
            "audio_path": self._physical_reference(f"data/Bible/.internal/audio/responses/{ready['wav']}") if ready else None,
            "audio_variant": ready.get("id") if ready else None,
            "sources": [str(self.conversational_path.relative_to(self.project_root)).replace("\\", "/")],
            "score": round(score, 3),
        })

    @staticmethod
    def _expand_variants(rows: list[dict]) -> list[dict]:
        """Expose substantive response variants as searchable children of one item."""
        expanded: list[dict] = []
        for row in rows if isinstance(rows, list) else []:
            variants = row.get("response_variations", []) if isinstance(row, dict) else []
            if not isinstance(variants, list) or not variants:
                expanded.append(row)
                continue
            for variant in variants:
                if not isinstance(variant, dict) or not variant.get("text"):
                    continue
                child = dict(row)
                child.update(variant)
                child["id"] = variant.get("variant_id") or f"{row.get('id')}-variant"
                child["parent_id"] = variant.get("parent_id") or row.get("id")
                child["text"] = variant.get("text")
                child["answer"] = variant["text"]
                # A child must be scored by its own answer, not by the full
                # parent research blob; otherwise every variant gets the same
                # score and the first one wins regardless of the question.
                child.pop("detailed_material", None)
                child.pop("response_variations", None)
                child["sources"] = variant.get("sources") or variant.get("source_ids") or row.get("sources", [])
                child["audio_status"] = variant.get("audio_status", "AUDIO_PENDING")
                child["audio_path"] = variant.get("audio_path") if variant.get("audio_status") == "AUDIO_READY" else None
                expanded.append(child)
        return expanded

    @staticmethod
    def _searchable_text(row: dict, fields: tuple[str, ...]) -> str:
        """Include structured research fields without creating a second index."""
        parts = [str(row.get(field, "")) for field in fields]
        detailed = row.get("detailed_material")
        if detailed:
            parts.append(json.dumps(detailed, ensure_ascii=False, sort_keys=True))
        return " ".join(parts)

    @staticmethod
    def _answer_text(row: dict) -> str:
        base = row.get("answer") or row.get("text") or row.get("explanation") or row.get("summary") or row.get("function") or row.get("description") or ""
        detailed = row.get("detailed_material")
        if detailed:
            base = f"{base}\n\nИсследовательский материал:\n{json.dumps(detailed, ensure_ascii=False, sort_keys=True)}"
        return str(base)

    def _physical_reference(self, value: str | None) -> str | None:
        if not value:
            return value
        normalized = str(value).replace("\\", "/")
        direct = self._physical_map.get(normalized)
        if direct:
            return str(direct)
        return value

    def _append_cards(self, results: list[dict], query: str, rows: list[dict], kind: str, fields: tuple[str, ...], base_score: float) -> None:
        for row in KnowledgeSearchService._expand_variants(rows):
            haystack = normalize(KnowledgeSearchService._searchable_text(row, fields))
            exact_pattern = any(normalize(pattern) == query for pattern in row.get("query_patterns", []))
            if query and (exact_pattern or matches_query(query, haystack)):
                topic_score = token_score(query, haystack)
                if row.get("parent_id"):
                    variant_search = normalize(" ".join([str(row.get("text", "")), " ".join(row.get("query_patterns", []))]))
                    answer_score = token_score(query, variant_search)
                    score = base_score * (0.65 * topic_score + 0.35 * answer_score)
                    if exact_pattern:
                        # A reviewed author-supplied question is a stronger
                        # intent signal than incidental words in another
                        # child of the same topic.
                        score = max(score, base_score + 0.20)
                else:
                    score = base_score * topic_score
                # A broad one-concept query must not receive an unrelated
                # reviewed child's answer merely because that concept is
                # mentioned incidentally in one of its examples/questions.
                # Exact authored questions still bypass this conservative cap.
                focus = focus_query(query)
                if row.get("parent_id") and not exact_pattern and len(focus.split()) == 1:
                    title_anchor = normalize(" ".join(str(row.get(key, "")) for key in
                                                      ("title", "topic", "model", "name", "brand", "series")))
                    if token_score(focus, title_anchor) < 1.0:
                        score = min(score, 0.65)
                results.append({"kind": kind, "id": row.get("id") or row.get("name"), "parent_id": row.get("parent_id"), "variant_kind": row.get("variant_kind"), "exact_query_pattern": exact_pattern, "title": row.get("title") or row.get("model") or row.get("name"), "answer": KnowledgeSearchService._answer_text(row), "status": row.get("status") or row.get("audio_status") or "SOURCE_LINKED", "has_audio": row.get("audio_status") == "AUDIO_READY", "audio_path": self._physical_reference(row.get("audio_path")), "audio_variant": row.get("audio_variant"), "sources": row.get("sources", []), "score": round(score, 3)})

    def context_bundle(self, query: str, limit: int = 6) -> dict:
        """Collect bounded local evidence for a complex question before LLM use."""
        results = self.search(query, max(12, min(int(limit) * 3, 30)))
        selected: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for item in results:
            key = (str(item.get("kind", "")), str(item.get("id") or item.get("title", "")))
            if key in seen or not item.get("answer"):
                continue
            # The context is injected into an LLM as reviewed evidence. Do
            # not launder legacy source-less or SOURCE_REVIEW cards through it.
            if not item.get("sources") or item.get("status") not in {"VERIFIED", "TESTED"}:
                continue
            if float(item.get("score", 0)) < 0.55:
                continue
            seen.add(key)
            selected.append({
                "module": item.get("kind"),
                "title": item.get("title"),
                "answer": str(item.get("answer", ""))[:2500],
                "sources": item.get("sources", []),
                "score": item.get("score", 0),
            })
            if len(selected) >= max(1, min(int(limit), 10)):
                break
        modules = list(dict.fromkeys(str(item["module"]) for item in selected))
        return {
            "query": query,
            "sources": selected,
            "modules": modules,
            "multi_source": len(modules) >= 2,
            "requires_generation": not any(item.get("kind") == "conversational" and item.get("has_audio") for item in results),
        }

    def answer(self, query: str, history: list[dict] | None = None) -> dict | None:
        """Resolve a runtime answer in source order without invoking an LLM."""
        contextual = self._conversation_resolver.resolve(query, history)
        if contextual:
            return contextual
        conversational = self._conversational_answer(query)
        if conversational:
            return conversational
        # Prefer a strong, topic-specific indexed result over a weak lexical
        # collision from another course (for example, "состав" matching a
        # programming lesson while the query is about Trivium).
        indexed_kinds = {
            "guitar", "literature", "psychology", "mixing", "daw",
            "voice_production", "music_production", "music_production_lesson",
            "external_music_reference", "programming_lesson", "offline_knowledge",
        }
        indexed_results = [row for row in self.search(query, 100)
                           if row.get("kind") in indexed_kinds and row.get("answer")
                           and row.get("sources") and row.get("status") in {"VERIFIED", "TESTED"}
                           and float(row.get("score", 0)) >= 0.72]
        indexed_results.sort(key=lambda row: float(row.get("score", 0)), reverse=True)
        recent = self._recent_variant_ids()
        if indexed_results:
            strongest = indexed_results[0]
            same_topic = [row for row in indexed_results
                          if (row.get("parent_id") or row.get("id")) == (strongest.get("parent_id") or strongest.get("id"))
                          and (not strongest.get("exact_query_pattern") or row.get("exact_query_pattern"))
                          and float(row.get("score", 0)) >= float(strongest.get("score", 0)) - 0.10]
            fresh = next((row for row in same_topic if str(row.get("id")) not in recent), None)
            indexed_results = [fresh or strongest]
        for indexed in indexed_results:
            if indexed.get("kind") not in indexed_kinds or not indexed.get("answer"):
                continue
            if float(indexed.get("score", 0)) < 0.72:
                continue
            if indexed.get("parent_id"):
                self._mark_variant_used(indexed.get("id"))
            return {
                "source": indexed.get("kind"),
                "id": indexed.get("id"),
                "parent_id": indexed.get("parent_id"),
                "variant_kind": indexed.get("variant_kind"),
                "title": indexed.get("title"),
                "answer": indexed.get("answer"),
                "score": indexed.get("score", 0),
                "audio_path": indexed.get("audio_path"),
                "audio_variant": indexed.get("audio_variant"),
                "sources": indexed.get("sources", []),
            }
        return None

    def _conversational_answer(self, query: str) -> dict | None:
        """Resolve instant speech through the existing, rotation-aware matcher."""
        normalized = normalize(query)
        match = self._local_responses.match(query, {"instant"})
        if match is None:
            return None
        return {
            "source": "conversational",
            "id": match.intent_id,
            "title": match.intent_id,
            "answer": match.text,
            "score": match.score,
            "audio_path": str(match.audio_path) if match.audio_path else None,
            "audio_variant": None,
            "sources": [str(self.conversational_path.relative_to(self.project_root)).replace("\\", "/")],
        }

    @staticmethod
    def _best_match(query: str, rows: list[dict], fields: tuple[str, ...], excluded_ids: set[str] | None = None) -> dict | None:
        if not query or not isinstance(rows, list):
            return None
        qwords = set(query.split())
        best = None
        best_score = 0.0
        for row in KnowledgeSearchService._expand_variants(rows):
            if excluded_ids and str(row.get("id", "")) in excluded_ids:
                continue
            haystack = normalize(KnowledgeSearchService._searchable_text(row, fields))
            if not haystack:
                continue
            words = set(haystack.split())
            overlap = len(qwords & words) / max(1, len(qwords))
            score = max(token_score(query, haystack), 1.0 if query in haystack else overlap)
            if score > best_score and score >= 0.65:
                best = dict(row)
                best["_score"] = round(score, 3)
                best_score = score
        return best
