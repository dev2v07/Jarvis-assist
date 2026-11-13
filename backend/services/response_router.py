"""Fast decision layer between recognized text and Jarvis response paths."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    """A deterministic route; no LLM call is made while deciding."""

    kind: str
    text: str
    intent: str | None = None


class ResponseRouter:
    """Route commands to rules and everything else to conversation."""

    GREETINGS = {"привет", "здравствуй", "добрый день", "доброе утро"}

    def route(self, text: str) -> RouteDecision:
        normalized = " ".join(str(text or "").lower().split()).strip()
        if not normalized:
            return RouteDecision("empty", normalized)
        if normalized in self.GREETINGS:
            return RouteDecision("preset", normalized, "hello")

        # The existing command table remains the source of truth. Import it
        # lazily so this small router remains usable in isolated tests.
        from computer_control import find_intent

        intent = find_intent(normalized)
        if intent:
            return RouteDecision("command", normalized, intent)
        return RouteDecision("conversation", normalized)

