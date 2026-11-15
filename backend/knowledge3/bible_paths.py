"""Write locations for Knowledge 3 generators after the Bible cutover."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATERIALS = ROOT / "data" / "Bible" / ".internal" / "sources" / "knowledge3"
AUDIO = ROOT / "data" / "Bible" / ".internal" / "audio" / "library" / "knowledge3"
INDEX = MATERIALS / "index.json"


def material(*parts: str) -> Path:
    return MATERIALS.joinpath(*parts)


def audio(*parts: str) -> Path:
    return AUDIO.joinpath(*parts)
