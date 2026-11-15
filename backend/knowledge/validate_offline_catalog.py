"""Validate offline knowledge metadata without touching audio or WAV manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


STATUSES = {"TEXT_READY", "AUDIO_PENDING", "AUDIO_READY", "VERIFIED", "ERROR"}


def validate(path: Path) -> tuple[list[str], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    topics = data.get("topics", [])
    ids: set[str] = set()
    ready = 0
    for index, topic in enumerate(topics, 1):
        topic_id = str(topic.get("id", ""))
        if not topic_id or topic_id in ids:
            errors.append(f"topic {index}: missing or duplicate id")
        ids.add(topic_id)
        for field in ("title", "category", "text", "sources", "answers", "variants_count", "status", "audio_status"):
            if field not in topic:
                errors.append(f"{topic_id or index}: missing {field}")
        status = str(topic.get("status", ""))
        if status not in STATUSES:
            errors.append(f"{topic_id or index}: invalid status {status}")
        answers = [str(item).strip() for item in topic.get("answers", []) if str(item).strip()]
        if int(topic.get("variants_count", 0) or 0) != len(answers):
            errors.append(f"{topic_id or index}: variants_count does not match answers")
        if status in {"AUDIO_READY", "VERIFIED"} and not answers:
            errors.append(f"{topic_id or index}: audio-ready topic has no answer text")
        if status in {"TEXT_READY", "AUDIO_READY", "VERIFIED"}:
            ready += 1
    return errors, {"topics": len(topics), "ready_text_topics": ready, "errors": len(errors)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("data/Bible/.internal/sources/offline_knowledge/catalog.json"))
    args = parser.parse_args()
    errors, summary = validate(args.path)
    print(json.dumps(summary, ensure_ascii=False))
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
