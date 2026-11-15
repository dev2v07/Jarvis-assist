"""Read-only Personal Music Intelligence over the local music catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.bible_paths import resolve


def _norm(value: Any) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", str(value or "").lower().replace("ё", "е")).split())


def _album_key(value: Any) -> str:
    """Compare releases while ignoring edition-only suffixes."""
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", text)
    text = re.sub(r"\b(?:deluxe|special|japanese|edition|reissue|remaster(?:ed)?|promo|anniversary|expanded|version)\b", " ", text)
    text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


class MusicIntelligenceService:
    """Search local collection metadata without touching original audio files."""

    def __init__(self, backend_dir: Path) -> None:
        self.catalog_path = resolve(backend_dir, "data/knowledge3/music_catalog.json")
        self.reference_path = resolve(backend_dir, "data/knowledge3/music/reference_catalog.json")
        self._mtime_ns = 0
        self._catalog: dict[str, Any] = {}
        self._reload()

    def _reload(self) -> None:
        try:
            self._catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            self._mtime_ns = self.catalog_path.stat().st_mtime_ns
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            self._catalog = {"summary": {}, "artists": [], "albums": [], "tracks": []}
            self._mtime_ns = 0

    def _refresh(self) -> None:
        try:
            if self.catalog_path.stat().st_mtime_ns != self._mtime_ns:
                self._reload()
        except OSError:
            pass

    def summary(self) -> dict[str, Any]:
        self._refresh()
        result = dict(self._catalog.get("summary", {}))
        result.update({
            "source": self._catalog.get("source", "LOCAL_COLLECTION"),
            "read_only": bool(self._catalog.get("read_only", True)),
            "root": self._catalog.get("root", ""),
            "external_discography": self._catalog.get("external_discography", {"status": "NOT_INDEXED", "items": []}),
        })
        reference = self._read_reference()
        result["external_discography"] = {
            "status": reference.get("status", "SOURCE_LINKED"),
            "artists": len(reference.get("artists", [])),
            "albums": sum(len(row.get("albums", [])) for row in reference.get("artists", [])),
            "path": str(self.reference_path),
        }
        return result

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        self._refresh()
        needle = _norm(query)
        if not needle:
            return []
        results: list[dict[str, Any]] = []
        for row in self._catalog.get("artists", []):
            haystack = _norm(" ".join([str(row.get("name", "")), *[str(x) for x in row.get("albums", [])]]))
            if needle in haystack or all(word in haystack for word in needle.split()):
                results.append({"kind": "artist", "name": row.get("name"), "tracks": row.get("tracks", 0), "albums": row.get("albums", []), "score": 1.0})
        for row in self._catalog.get("albums", []):
            haystack = _norm(" ".join(str(value) for value in row.values()))
            if needle in haystack or all(word in haystack for word in needle.split()):
                results.append({"kind": "album", "artist": row.get("artist"), "album": row.get("album"), "tracks": row.get("tracks", 0), "score": 0.9})
        for row in self._catalog.get("tracks", []):
            haystack = _norm(" ".join(str(value) for value in row.values() if isinstance(value, (str, int, float))))
            if needle in haystack or all(word in haystack for word in needle.split()):
                results.append({"kind": "track", "artist": row.get("artist"), "album": row.get("album"), "title": row.get("title"), "path": row.get("path"), "score": 0.8})
        results.sort(key=lambda item: item["score"], reverse=True)
        for artist in self._read_reference().get("artists", []):
            haystack = _norm(" ".join([artist.get("name", ""), *[a.get("title", "") for a in artist.get("albums", [])]]))
            if needle in haystack or all(word in haystack for word in needle.split()):
                results.append({"kind": "external_artist", "name": artist.get("name"), "albums": artist.get("albums", []), "sources": artist.get("sources", []), "score": 0.75, "read_only": True})
        return results[: max(1, min(int(limit), 100))]

    def artist_report(self, artist_name: str) -> dict[str, Any]:
        """Return a read-only local/reference report for one artist."""
        self._refresh()
        needle = _norm(artist_name)
        local = next((row for row in self._catalog.get("artists", []) if _norm(row.get("name")) == needle), None)
        reference = next((row for row in self._read_reference().get("artists", []) if _norm(row.get("name")) == needle), None)
        if local is None and reference is None:
            raise LookupError(f"Исполнитель не найден в локальном или reference-каталоге: {artist_name}")
        local_albums = list(local.get("albums", [])) if local else []
        reference_albums = list(reference.get("albums", [])) if reference else []
        reference_titles = [str(row.get("title", "")) for row in reference_albums]
        local_names = {_album_key(name) for name in local_albums}
        matched = [row for row in reference_albums if _album_key(row.get("title")) in local_names]
        missing = [row for row in reference_albums if _album_key(row.get("title")) not in local_names]
        return {
            "name": (local or reference).get("name"),
            "read_only": True,
            "local_collection": {
                "present": local is not None,
                "tracks": local.get("tracks", 0) if local else 0,
                "albums": local_albums,
            },
            "full_discography": {
                "available": reference is not None,
                "albums": reference_titles,
                "sources": reference.get("sources", []) if reference else [],
            },
            "matched_releases": matched,
            "missing_releases": missing,
            "comparison_method": "normalized_album_title_edition_aware",
        }

    def compare_artists(self, artist_names: list[str]) -> dict[str, Any]:
        reports = []
        for name in artist_names[:5]:
            try:
                reports.append(self.artist_report(name))
            except LookupError:
                reports.append({"name": name, "not_found": True})
        return {
            "read_only": True,
            "artists": reports,
            "comparison": [
                {"name": report.get("name"), "local_tracks": report.get("local_collection", {}).get("tracks", 0), "local_albums": len(report.get("local_collection", {}).get("albums", [])), "missing_releases": len(report.get("missing_releases", []))}
                for report in reports if not report.get("not_found")
            ],
        }

    def recommend_similar(self, artist_name: str, limit: int = 10) -> dict[str, Any]:
        """Recommend local artists using only collection metadata.

        No genre is invented: when genre tags are absent, similarity is based
        on shared normalized album-title tokens and is labelled accordingly.
        """
        self._refresh()
        needle = _norm(artist_name)
        artists = self._catalog.get("artists", [])
        source = next((row for row in artists if _norm(row.get("name")) == needle), None)
        if source is None:
            raise LookupError(f"Исполнитель не найден в локальной коллекции: {artist_name}")
        source_tokens = {token for album in source.get("albums", []) for token in _norm(album).split() if len(token) > 2}
        candidates = []
        for row in artists:
            if row is source:
                continue
            tokens = {token for album in row.get("albums", []) for token in _norm(album).split() if len(token) > 2}
            overlap = len(source_tokens & tokens)
            union = len(source_tokens | tokens) or 1
            score = overlap / union
            candidates.append({"name": row.get("name"), "score": round(score, 3), "tracks": row.get("tracks", 0), "albums": row.get("albums", [])})
        candidates.sort(key=lambda item: (item["score"], item["tracks"]), reverse=True)
        return {"read_only": True, "source_artist": source.get("name"), "method": "shared_album_title_tokens", "results": candidates[: max(1, min(int(limit), 50))], "limitation": "В локальном каталоге недостаточно жанровых тегов для строгого жанрового сравнения."}

    def metadata_analysis(self) -> dict[str, Any]:
        """Report coverage of technical tags discovered during the read-only scan."""
        self._refresh()
        tracks = self._catalog.get("tracks", [])
        formats: dict[str, int] = {}
        genres: dict[str, int] = {}
        duration_known = 0
        quality_known = 0
        for row in tracks:
            fmt = str(row.get("format") or "unknown").lower()
            formats[fmt] = formats.get(fmt, 0) + 1
            genre = str(row.get("genre") or "").strip()
            if genre:
                genres[genre] = genres.get(genre, 0) + 1
            if float(row.get("duration_seconds") or 0) > 0:
                duration_known += 1
            if float(row.get("sample_rate") or 0) > 0 or float(row.get("bitrate") or 0) > 0:
                quality_known += 1
        return {"read_only": True, "tracks": len(tracks), "formats": formats, "genres": genres, "known_duration": duration_known, "known_quality": quality_known, "limitations": ["Пустые метаданные не заполняются догадками."]}

    def _read_reference(self) -> dict[str, Any]:
        try:
            value = json.loads(self.reference_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"artists": []}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"artists": []}

