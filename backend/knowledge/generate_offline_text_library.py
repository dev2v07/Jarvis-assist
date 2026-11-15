"""Resumeable local draft authoring for the offline knowledge catalog.

The script uses the locally installed Ollama model only to prepare drafts. It
does not invent source URLs, does not generate audio, and marks every new
material ``verified=false`` so drafts cannot leak into voice runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "Bible" / ".internal" / "sources" / "offline_knowledge" / "catalog.json"


def extract_json(value: str) -> dict:
    value = re.sub(r"<think>.*?</think>", "", value or "", flags=re.S | re.I).strip()
    start = value.find("{")
    if start < 0:
        raise ValueError("Ollama did not return a JSON object")
    decoder = json.JSONDecoder()
    result, _ = decoder.raw_decode(value[start:])
    if not isinstance(result, dict):
        raise ValueError("Ollama JSON response is not an object")
    return result


def ask_ollama(model: str, topic: dict) -> dict:
    prompt = f"""Ты готовишь черновик русскоязычной офлайн-энциклопедии Jarvis.
Тема: {topic['title']}
Категория: {topic['category']}

Верни только JSON без markdown и без комментариев:
{{"text":"краткое точное объяснение", "answers":["вариант 1", "вариант 2", "вариант 3", "вариант 4", "вариант 5", "вариант 6", "вариант 7", "вариант 8", "вариант 9", "вариант 10"], "sources":["https://..."], "source_queries":["что проверить по теме"]}}

Требования: русский язык, 10 действительно разных вариантов, факты без выдуманных дат и характеристик, 2-4 предложения в каждом варианте, без служебных меток и обращения к пользователю. Источник указывай только если уверен в точной ссылке на официальный сайт, музей, университет или документацию; иначе оставь sources пустым и добавь поисковый запрос в source_queries. Источник предложен моделью и пока не считается проверенным."""
    response = requests.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "think": False,
            "options": {"temperature": 0.25, "num_predict": 1800},
        },
        timeout=600,
    )
    response.raise_for_status()
    body = response.json()
    return extract_json(body.get("message", {}).get("content", ""))


def save(data: dict) -> None:
    tmp = CATALOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for _ in range(5):
        try:
            tmp.replace(CATALOG)
            return
        except PermissionError:
            time.sleep(0.25)
    CATALOG.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    completed = 0
    for topic in data.get("topics", []):
        if topic.get("answers") or topic.get("verified") is False:
            continue
        if args.limit and completed >= args.limit:
            break
        try:
            draft = ask_ollama(args.model, topic)
            answers = [str(item).strip() for item in draft.get("answers", []) if str(item).strip()]
            if len(answers) < 10 or not str(draft.get("text", "")).strip():
                raise ValueError(f"invalid draft shape: answers={len(answers)}")
            sources = [str(item).strip() for item in draft.get("sources", []) if str(item).strip().startswith(("https://", "http://"))]
            source_queries = [str(item).strip() for item in draft.get("source_queries", []) if str(item).strip()]
            topic.update(
                text=str(draft["text"]).strip(),
                answers=answers[:10],
                variants_count=min(len(answers), 10),
                sources=sources,
                source_queries=source_queries or [f"официальный источник {topic['title']}"],
                source_status="MODEL_SUGGESTED",
                verified=False,
                review_status="DRAFT",
                status="TEXT_READY",
                audio_status="AUDIO_PENDING",
            )
            completed += 1
            print(f"DRAFT {completed}: {topic['id']}", flush=True)
        except Exception as error:
            topic["status"] = "ERROR"
            topic["review_status"] = "DRAFT_ERROR"
            topic["error"] = str(error)[:500]
            print(f"ERROR {topic['id']}: {error}", flush=True)
        save(data)
    save(data)
    print(f"DONE drafts={completed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
