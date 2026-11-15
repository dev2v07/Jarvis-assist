"""Small deterministic conversation layer shared by text and voice paths."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class ConversationResolver:
    """Resolve bounded context-sensitive social turns without an LLM call."""

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value or "").lower().replace("ё", "е").split()).strip(" ,.!?;:")

    @classmethod
    def _history_text(cls, history: Iterable[Mapping[str, Any]] | None) -> list[str]:
        return [
            cls._normalize(str(item.get("content", "")))
            for item in (history or [])
            if isinstance(item, Mapping) and item.get("content")
        ]

    @classmethod
    def resolve(
        cls,
        query: str,
        history: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        normalized = cls._normalize(query)
        if not normalized:
            return None
        previous = cls._history_text(history)

        if (
            "ты хороший" in normalized
            or "хороший ли ты" in normalized
            or "ты добрый" in normalized
        ):
            return {
                "source": "conversational_local",
                "id": "jarvis_good_assistant",
                "title": "Характер Jarvis",
                "answer": "Стараюсь быть хорошим помощником, сэр: отвечать честно, полезно и по делу.",
                "score": 1.0,
                "audio_path": None,
                "audio_variant": None,
                "sources": ["backend/services/conversation_resolver.py"],
                "context_used": False,
            }

        has_sleep_context = any(
            "хочешь спать" in item or "хочу спать" in item
            for item in previous[-6:]
        )

        if "а я" in normalized and "хочу спать" in normalized:
            return {
                "source": "conversational_context",
                "id": "sleep_user_tired",
                "title": "Поддержка пользователя, который хочет спать",
                "answer": "Тогда лучше отдохните. Спокойной ночи — продолжим разговор, когда будете готовы.",
                "score": 1.0,
                "audio_path": None,
                "audio_variant": None,
                "sources": ["backend/services/conversation_resolver.py"],
                "context_used": True,
            }

        if "точно не хочешь спать" in normalized and has_sleep_context:
            return {
                "source": "conversational_context",
                "id": "sleep_followup_confirmed",
                "title": "Контекстный ответ о готовности Jarvis",
                "answer": "Точно. Я не сплю и готов продолжать разговор или помочь с задачей.",
                "score": 1.0,
                "audio_path": None,
                "audio_variant": None,
                "sources": ["backend/services/conversation_resolver.py"],
                "context_used": True,
            }

        if (
            has_sleep_context
            and (
                "почему ты не спишь" in normalized
                or "почему не спишь" in normalized
                or "почему ты не хочешь спать" in normalized
            )
        ):
            return {
                "source": "conversational_context",
                "id": "sleep_followup_explanation",
                "title": "Объяснение готовности Jarvis",
                "answer": "Потому что я не сплю, сэр. Я всегда готов продолжить разговор и помочь с задачей.",
                "score": 1.0,
                "audio_path": None,
                "audio_variant": None,
                "sources": ["backend/services/conversation_resolver.py"],
                "context_used": True,
            }

        if "хочешь спать" in normalized and "точно" not in normalized:
            return {
                "source": "conversational_context",
                "id": "sleep_jarvis_ready",
                "title": "Jarvis не спит",
                "answer": "Я не сплю и готов к работе.",
                "score": 1.0,
                "audio_path": None,
                "audio_variant": None,
                "sources": ["backend/services/conversation_resolver.py"],
                "context_used": bool(previous),
            }

        return None
