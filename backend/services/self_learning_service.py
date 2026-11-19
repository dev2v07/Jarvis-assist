"""SELF_LEARNING mode backed by the canonical Bible source tree.

This service deliberately owns no second search/index implementation.  It
stores structured, provenance-aware drafts in the Bible and asks the existing
catalog builder to refresh the shared human-facing index.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.llm_service import LocalLLMService


def _norm(value: Any) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", str(value or "").casefold().replace("ё", "е")).split())


class SelfLearningService:
    mode = "SELF_LEARNING"

    def __init__(self, project_root: Path, llm: LocalLLMService | None = None) -> None:
        self.project_root = Path(project_root)
        self.source_path = self.project_root / "data" / "Bible" / ".internal" / "sources" / "self_learning" / "catalog.json"
        self.llm = llm or LocalLLMService()

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.source_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict[str, Any]) -> None:
        self.source_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.source_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.source_path)

    async def _draft(self, message: str, attachments: list[dict[str, Any]]) -> dict[str, Any]:
        attachment_names = [str(item.get("name") or "") for item in attachments if isinstance(item, dict)]
        prompt = (
            "Преобразуй пользовательский материал в структурированную карточку знаний. "
            "Верни только JSON-объект с полями title, category, summary, content, facts, "
            "steps, sources, uncertainties. Не выдумывай источники; авторские утверждения "
            "помечай как user_provided. Это черновик для проверки, не подтверждай факты сам.\n\n"
            f"Материал пользователя:\n{message}\n\nВложения: {', '.join(attachment_names) or 'нет'}"
        )
        raw = await self.llm.chat(
            [{"role": "user", "content": prompt}],
            "Ты редактор Knowledge Library. Соблюдай JSON и сохраняй происхождение каждого утверждения.",
        )
        try:
            parsed = json.loads(str(raw).strip())
            if isinstance(parsed, dict) and parsed.get("content"):
                return parsed
        except json.JSONDecodeError:
            pass
        # Never persist a raw user task as if it were a knowledge card. The
        # caller reports this as an uncompleted learning turn instead.
        raise RuntimeError("structured_draft_unavailable")

    @staticmethod
    def _entry_id(draft: dict[str, Any]) -> str:
        identity = _norm("|".join([draft.get("title", ""), draft.get("content", "")]))
        return "self_learning:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _sources(draft: dict[str, Any]) -> list[Any]:
        sources = draft.get("sources")
        if not isinstance(sources, list) or not sources:
            return [{"type": "user_provided", "label": "Сообщение пользователя"}]
        return sources

    async def process(self, message: str, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        draft = await self._draft(str(message or ""), attachments or [])
        payload = self._read()
        entries = [item for item in payload.get("entries", []) if isinstance(item, dict)]
        entry_id = self._entry_id(draft)
        duplicate = next((item for item in entries if item.get("id") == entry_id), None)
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "id": entry_id,
            "title": str(draft.get("title") or "Материал пользователя")[:200],
            "category": str(draft.get("category") or "user_provided")[:100],
            "summary": str(draft.get("summary") or "")[:3000],
            "content": str(draft.get("content") or "")[:20000],
            "facts": draft.get("facts") if isinstance(draft.get("facts"), list) else [],
            "steps": draft.get("steps") if isinstance(draft.get("steps"), list) else [],
            "sources": self._sources(draft),
            "uncertainties": draft.get("uncertainties") if isinstance(draft.get("uncertainties"), list) else [],
            "provenance": "user_provided",
            "status": "NEEDS_REVIEW",
            "updated_at": now,
        }
        if duplicate:
            duplicate.update(entry)
            created = 0
            updated = 1
        else:
            entries.append(entry)
            created = 1
            updated = 0
        payload = {"version": 1, "source": "SELF_LEARNING", "entries": entries, "updated_at": now}
        self._write(payload)

        indexed = False
        index_error = ""
        try:
            from knowledge.build_bible_catalog import main as rebuild_bible_catalog
            rebuild_bible_catalog()
            indexed = True
        except Exception as exc:  # pragma: no cover - defensive runtime path
            index_error = type(exc).__name__

        return {
            "created": created,
            "updated": updated,
            "duplicates": 1 if duplicate else 0,
            "entry_id": entry_id,
            "path": str(self.source_path),
            "indexed": indexed,
            "index_error": index_error,
            "status": entry["status"],
            "sources": entry["sources"],
        }

    @staticmethod
    def format_report(result: dict[str, Any]) -> str:
        index_state = "подтверждена" if result.get("indexed") else "не подтверждена"
        return (
            "SELF-LEARNING: материал обработан как черновик для Knowledge Library.\n"
            f"Создано новых записей: {result.get('created', 0)}; "
            f"дополнено: {result.get('updated', 0)}; "
            f"дубликатов: {result.get('duplicates', 0)}.\n"
            f"Источники: {json.dumps(result.get('sources', []), ensure_ascii=False)}.\n"
            f"Сохранено: {result.get('path')}. Статус проверки: NEEDS_REVIEW.\n"
            f"Индексация общей Bible: {index_state}."
        )
