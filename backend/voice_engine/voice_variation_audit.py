"""Audit and enrich the existing local conversational voice library.

The tool is intentionally non-destructive: it never rewrites text, removes a
WAV, or changes an existing audio mapping.  It adds metadata needed for
context-aware selection and writes a machine-readable audit report.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "data" / "Bible" / "materials" / "voice_responses"
QUESTIONS = LIBRARY / "questions.json"
REPORT_JSON = LIBRARY / "variation_audit.json"
REPORT_MD = ROOT / "docs" / "VOICE_RESPONSE_VARIATIONS_REPORT.md"


def normalize(text: str) -> str:
    return " ".join(str(text or "").lower().replace("ё", "е").split())


def load() -> dict:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def audit(data: dict, enrich: bool = False) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_rows: list[dict] = []
    exact: dict[str, list[dict]] = defaultdict(list)
    near_pairs: list[dict] = []
    categories: dict[str, dict] = {}

    for intent in data.get("intents", []):
        intent_id = str(intent.get("id", ""))
        semantic_group = intent_id.rsplit("_", 1)[0] or intent_id
        category = str(intent.get("category", ""))
        category_stats = categories.setdefault(
            semantic_group,
            {"intents": 0, "responses": 0, "ready": 0, "pending": 0, "errors": 0},
        )
        category_stats["intents"] += 1
        for response in intent.get("responses", []):
            response_id = f"{intent_id}:{response.get('id', '')}"
            text = str(response.get("text", "")).strip()
            normalized = normalize(text)
            wav = str(response.get("wav", "")).replace("\\", "/")
            wav_path = LIBRARY / wav
            status = str(response.get("status", "pending"))
            category_stats["responses"] += 1
            if status == "ready":
                category_stats["ready"] += 1
            elif status in {"pending", "generating"}:
                category_stats["pending"] += 1
            else:
                category_stats["errors"] += 1
            row = {
                "response_id": response_id,
                "intent_id": intent_id,
                "category": category,
                "semantic_group": semantic_group,
                "text": text,
                "normalized_text": normalized,
                "wav": wav,
                "wav_exists": wav_path.is_file(),
                "status": status,
            }
            all_rows.append(row)
            exact[normalized].append(row)
            if enrich:
                response.update(
                    {
                        "response_id": response_id,
                        "semantic_group": semantic_group,
                        "context_tags": [semantic_group, str(intent.get("class", "instant")), category],
                        "enabled": bool(response.get("enabled", status == "ready")),
                        "generation_status": "AUDIO_READY" if status == "ready" and wav_path.is_file() else ("ERROR" if status == "error" else "AUDIO_PENDING"),
                        "created_at": response.get("created_at") or now,
                    }
                )

    exact_groups = [group for group in exact.values() if group and group[0]["normalized_text"] and len(group) > 1]
    for left_index, left in enumerate(all_rows):
        for right in all_rows[left_index + 1 :]:
            if left["response_id"] == right["response_id"]:
                continue
            # A semantic group contains many related intents (for example all
            # greetings).  Its texts may legitimately share a response style;
            # the quality gate must compare variants inside one intent, where
            # the user actually hears the rotation.
            if left["intent_id"] != right["intent_id"]:
                continue
            if not left["normalized_text"] or not right["normalized_text"] or left["normalized_text"] == right["normalized_text"]:
                continue
            similarity = SequenceMatcher(None, left["normalized_text"], right["normalized_text"]).ratio()
            if similarity >= 0.85:
                near_pairs.append({"left": left["response_id"], "right": right["response_id"], "similarity": round(similarity, 3)})

    report = {
        "version": 1,
        "generated_at": now,
        "source": "data/voice_responses/questions.json",
        "non_destructive": True,
        "intents": len(data.get("intents", [])),
        "responses": len(all_rows),
        "ready_audio": sum(row["status"] == "ready" and row["wav_exists"] for row in all_rows),
        "missing_audio": sum(not row["wav_exists"] for row in all_rows),
        "exact_duplicate_groups": len(exact_groups),
        "exact_duplicate_items": sum(len(group) - 1 for group in exact_groups),
        "near_duplicate_pairs_same_intent": len(near_pairs),
        "categories": categories,
        "duplicate_examples": [
            {"text": group[0]["text"], "responses": [row["response_id"] for row in group[:20]]}
            for group in exact_groups[:30]
        ],
        "near_duplicate_examples": near_pairs[:100],
    }
    return report


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def save_markdown(report: dict) -> None:
    lines = [
        "# Voice Response Variations — audit",
        "",
        f"Проверено намерений: **{report['intents']}**, вариантов: **{report['responses']}**.",
        "",
        f"Готовых WAV по существующим связям: **{report['ready_audio']}**; отсутствующих: **{report['missing_audio']}**.",
        f"Точных повторяющихся текстовых групп: **{report['exact_duplicate_groups']}**, повторных записей: **{report['exact_duplicate_items']}**.",
        f"Почти одинаковых пар внутри одного intent: **{report['near_duplicate_pairs_same_intent']}**.",
        "",
        "## Интерпретация",
        "",
        "Повтор текста между разными intent не объявляется исправленным только из-за другого имени WAV. Такие записи попадают в очередь на новую семантическую формулировку. Старые WAV и их текстовые связи не удаляются.",
        "",
        "## Статистика по группам",
        "",
        "| Группа | Intent | Варианты | Готово | Ожидают | Ошибки |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, value in sorted(report["categories"].items()):
        lines.append(f"| `{key}` | {value['intents']} | {value['responses']} | {value['ready']} | {value['pending']} | {value['errors']} |")
    lines.extend(["", "## Ограничения", "", "- Аудио считается готовым только если статус `ready` и WAV существует.", "- Содержимое существующих WAV не менялось.", "- Для новых вариантов генерация выполняется отдельным пакетным Fish Audio pipeline."])
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enrich", action="store_true", help="add metadata without changing text/audio")
    args = parser.parse_args()
    data = load()
    report = audit(data, enrich=args.enrich)
    if args.enrich:
        temporary = QUESTIONS.with_suffix(QUESTIONS.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(QUESTIONS)
    save_json(REPORT_JSON, report)
    save_markdown(report)
    print(json.dumps({key: report[key] for key in ("intents", "responses", "ready_audio", "missing_audio", "exact_duplicate_groups", "exact_duplicate_items", "near_duplicate_pairs_same_intent")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
