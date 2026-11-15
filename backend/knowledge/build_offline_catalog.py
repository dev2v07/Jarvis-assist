"""Extract the attached offline-knowledge specification into a safe catalog.

This creates topic metadata only. It intentionally does not invent answers or
generate audio; reviewed answers can be added later without touching the
existing Fish Audio manifest.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CATEGORY_RE = re.compile(r"^##\s+КАТЕГОРИЯ\s+(.+?)\s*$", re.IGNORECASE)
NUMBERED_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
SECTIONS = {
    "## 1. Сказки": "Истории и сказки",
    "## 2. Научная фантастика": "Научная фантастика",
    "## 3. Детективы и мистические истории": "Детективы и мистика",
    "## 4. Образовательные аудиолекции": "Аудиолекции",
}


def parse(source: Path) -> list[dict]:
    topics: list[dict] = []
    category = "Без категории"
    subsection = ""
    collect = False
    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        category_match = CATEGORY_RE.match(line)
        if category_match:
            category = category_match.group(1).strip()
            subsection = ""
            collect = True
            continue
        if line in SECTIONS:
            subsection = SECTIONS[line]
            collect = True
            continue
        if line.startswith("## ") and not category_match:
            # Ignore procedural numbered lists and generation requirements.
            collect = False
            subsection = ""
            continue
        numbered = NUMBERED_RE.match(line)
        if collect and numbered and len(numbered.group(2)) >= 8:
            title = numbered.group(2).strip().rstrip(".")
            safe_id = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:70]
            if not safe_id:
                safe_id = f"topic_{len(topics)+1:04d}"
            topics.append({
                "id": f"offline_{len(topics)+1:04d}_{safe_id}",
                "category": subsection or category,
                "title": title,
                "prompts": [title],
                "text": "",
                "sources": [],
                "answers": [],
                "variants_count": 0,
                "audio_status": "AUDIO_PENDING",
                "class": "offline_knowledge",
                "status": "AUDIO_PENDING",
            })
    return topics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/Bible/.internal/sources/offline_knowledge/catalog.json"))
    args = parser.parse_args()
    topics = parse(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({
            "version": 2,
            "source": "attached offline knowledge specification",
            "topics": topics,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"topics={len(topics)} output={args.output}")


if __name__ == "__main__":
    main()
