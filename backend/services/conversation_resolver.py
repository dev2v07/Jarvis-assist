"""Small deterministic conversation layer shared by text and voice paths.

Besides the original sleep-context replies, this layer now tracks the
question Jarvis asked last ("pending dialogue") and resolves the user's
answer to it.  The pending question is derived from the conversation
history, so no second dialogue store is introduced.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class ConversationResolver:
    """Resolve bounded context-sensitive social turns without an LLM call."""

    # The last assistant line is classified by these ordered patterns.
    # Longer / more specific patterns must come before shorter ones.
    _PENDING_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("good_morning_slept", ("выспались", "выспался", "выспалась")),
        ("task_detail", ("что уже известно", "что нужно сделать в первую очередь")),
        ("plans", (
            "какие планы", "какие у вас планы", "чем сегодня займемся", "чем займемся",
            "с чего начнем", "начнем с чего", "начать с чего",
            "что будем делать",
        )),
        ("whats_new", ("что нового", "какие новости", "что интересного", "что слышно")),
        ("how_are_you", (
            "как ваши дела", "как вы сегодня", "как ваше настроение",
            "как прошел ваш день", "как прошли ваши дела",
            "как вы себя чувствуете", "а у вас как", "как настроение", "как поживаете",
            "как дела",
        )),
    )

    _NEGATIVE = (
        "не выспал", "плохо спал", "не очень", "плохо", "устал", "устала",
        "тяжело", "грустно", "нет",
    )
    _POSITIVE = (
        "выспал", "хорошо", "отлично", "нормально", "неплохо", "супер",
        "замечательно", "да", "ага", "конечно",
    )
    _UNKNOWN = ("не знаю", "пока не знаю", "не решил", "не решила", "без понятия", "не уверен", "не уверена")
    _TASK = ("поработа", "проект", "задач", "сдела", "напиш", "провер", "учеб", "учёб", "работ", "презентац", "код", "тест")

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
    def _last_assistant(cls, history: Iterable[Mapping[str, Any]] | None) -> str:
        for item in reversed(list(history or [])):
            if isinstance(item, Mapping) and item.get("role") == "assistant":
                return cls._normalize(str(item.get("content", "")))
        return ""

    @classmethod
    def _pending_kind(cls, last_assistant: str) -> str | None:
        if not last_assistant:
            return None
        for kind, patterns in cls._PENDING_RULES:
            if any(pattern in last_assistant for pattern in patterns):
                return kind
        return None

    @classmethod
    def _classify_reply(cls, text: str) -> str:
        normalized = cls._normalize(text)
        if not normalized:
            return "empty"
        if any(word in normalized for word in cls._UNKNOWN):
            return "unknown"
        if any(word in normalized for word in cls._NEGATIVE):
            return "negative"
        if any(word in normalized for word in cls._POSITIVE):
            return "positive"
        return "neutral"

    @classmethod
    def _pending_reply(cls, kind: str, query: str) -> dict[str, Any] | None:
        mood = cls._classify_reply(query)
        if kind == "good_morning_slept":
            if mood == "positive":
                text = "Отлично, сэр! Тогда можем приступать. Какие планы на сегодня?"
            elif mood == "negative":
                text = (
                    "Понимаю, сэр. Надеюсь, сегодня получится немного восстановиться. "
                    "Может, начнём с чего-нибудь несложного?"
                )
            else:
                text = "Понял, сэр. Тогда предлагаю начать с чего-то небольшого — с чего вам удобнее?"
        elif kind == "plans":
            if any(word in cls._normalize(query) for word in cls._TASK):
                text = "Принято, сэр. Тогда давайте разберём задачу по шагам: что уже известно?"
            elif mood == "unknown":
                text = (
                    "Ничего страшного, сэр. Могу предложить начать с чего-то небольшого: "
                    "работа, учёба или разговор?"
                )
            else:
                text = "Понял, сэр. Тогда предлагаю начать с первого шага — что нужно сделать в первую очередь?"
        elif kind == "task_detail":
            text = "Понял, сэр. Зафиксировал. Дальше можем действовать по шагам."
        elif kind == "whats_new":
            low = cls._normalize(query)
            if mood in ("empty", "unknown"):
                text = "Понял, сэр. Если появится задача — я готов."
            elif any(word in low for word in ("купил", "купила", "приобрел", "подарили")):
                text = "Поздравляю с покупкой, сэр! Чем могу помочь по этому поводу?"
            elif any(word in low for word in ("устал", "устала", "плохо", "тяжело")):
                text = "Понимаю, сэр. Если захотите отдохнуть — я рядом."
            elif any(word in low for word in ("работ", "проект", "задач")):
                text = "Звучит продуктивно, сэр. Чем могу помочь по этому поводу?"
            else:
                text = "Спасибо, что поделились, сэр. Чем могу помочь по этому поводу?"
        elif kind == "how_are_you":
            if mood == "positive":
                text = "Рад слышать, сэр! Что сегодня будем делать?"
            elif mood == "negative":
                text = "Сочувствую, сэр. Если хотите, начнём с чего-то простого."
            elif mood == "unknown":
                text = "Понимаю, сэр. Давайте подумаем вместе: работа, учёба или отдых?"
            else:
                text = "Спасибо, что рассказали, сэр. Чем могу помочь?"
        else:
            return None
        return {
            "source": "conversational_pending",
            "id": "pending_" + kind,
            "title": "Продолжение диалога",
            "answer": text,
            "score": 1.0,
            "audio_path": None,
            "audio_variant": None,
            "sources": ["backend/services/conversation_resolver.py"],
            "context_used": True,
            "pending_kind": kind,
        }

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

        # Pending dialogue: the user answers the question Jarvis asked last.
        last_assistant = cls._last_assistant(history)
        kind = cls._pending_kind(last_assistant)
        if kind is not None:
            reply = cls._pending_reply(kind, query)
            if reply is not None:
                return reply

        return None
