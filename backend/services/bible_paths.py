"""Canonical path resolution for the physically cut-over Bible."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def _manifest_maps(manifest_path: str) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}, ()
    if not manifest.get("records"):
        return {}, ()
    direct: dict[str, str] = {}
    prefixes: list[tuple[str, str]] = []
    for item in manifest.get("records", []):
        source = str(item.get("source", "")).replace("\\", "/").rstrip("/")
        canonical = str(item.get("canonical", "")).replace("\\", "/").rstrip("/")
        if not source or not canonical:
            continue
        direct[source] = canonical
        source_parts = source.split("/")
        canonical_parts = canonical.split("/")
        if len(source_parts) >= 2:
            source_root = "/".join(source_parts[:2])
            root_name = source_parts[1]
            try:
                root_index = canonical_parts.index(root_name)
            except ValueError:
                root_index = -1
            if root_index >= 1:
                canonical_root = "/".join(canonical_parts[: root_index + 1])
                direct.setdefault(source_root, canonical_root)
                source_parent = source.rsplit("/", 1)[0]
                canonical_parent = canonical.rsplit("/", 1)[0]
                direct.setdefault(source_parent, canonical_parent)
        prefixes.append((source + "/", canonical + "/"))
    prefixes.sort(key=lambda pair: len(pair[0]), reverse=True)
    return direct, tuple(prefixes)


def resolve(backend_dir: Path, source_path: str) -> Path:
    project_root = Path(backend_dir).parent
    manifest_path = project_root / "data" / "Bible" / "index" / "physical_manifest.json"
    direct, prefixes = _manifest_maps(str(manifest_path))
    normalized = source_path.replace("\\", "/").rstrip("/")
    if normalized in direct:
        return project_root / direct[normalized]
    for source_prefix, canonical_prefix in prefixes:
        if normalized.startswith(source_prefix):
            suffix = normalized[len(source_prefix):]
            return project_root / (canonical_prefix + suffix)
    # Empty directories do not produce manifest records. Resolve their
    # source-root aliases using the active Bible layout instead of falling
    # back to an archived/deleted legacy path.
    for legacy_root in ("knowledge3", "offline_knowledge", "voice_responses"):
        alias = f"data/{legacy_root}"
        if normalized == alias or normalized.startswith(alias + "/"):
            relative = normalized[len(alias):].lstrip("/")
            candidates = (
                project_root / "data" / "Bible" / ".internal" / "sources" / legacy_root,
                project_root / "data" / "Bible" / "sources" / legacy_root,
                project_root / "data" / "Bible" / "materials" / legacy_root,
            )
            for candidate_root in candidates:
                candidate = candidate_root / relative
                if candidate.exists() or candidate_root.is_dir():
                    return candidate
    return project_root / source_path


def runtime_path(backend_dir: Path, *parts: str) -> Path:
    """Return the canonical Bible-owned path for mutable library runtime state."""
    return Path(backend_dir).parent / "data" / "Bible" / "index" / "runtime" / Path(*parts)
