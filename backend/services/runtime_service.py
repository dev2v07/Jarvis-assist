"""Runtime/provider boundary for platform-neutral Jarvis clients.

This service deliberately sits beside the existing chat pipeline.  It exposes
small contract objects for future desktop/web/mobile/device adapters without
changing the current MessageBus or chat transport.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any, Mapping

import requests

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    LLM_PROVIDER,
    read_runtime_config,
)
from core.contracts import (
    ProviderStatus,
    RequestContext,
    RuntimeEvent,
    new_request_context,
)


class ProviderStatusService:
    """Return normalized, non-secret status for configured providers."""

    _PROVIDERS = (
        "stub",
        "ollama",
        "openai",
        "openai_compatible",
        "claude",
        "freellmapi",
    )

    def snapshot(self, *, probe: bool = True) -> dict[str, Any]:
        config = read_runtime_config(mask_secrets=False)
        selected = str(config.get("HEL_LLM_PROVIDER") or LLM_PROVIDER or "stub").lower()
        statuses = [self._status(provider, config, probe=probe) for provider in self._PROVIDERS]

        return {
            "schema_version": 1,
            "selected_provider": selected,
            "providers": [status.to_dict() for status in statuses],
        }

    def _status(
        self,
        provider: str,
        config: Mapping[str, str],
        *,
        probe: bool,
    ) -> ProviderStatus:
        if provider == "stub":
            return ProviderStatus(
                provider=provider,
                available=True,
                model="built-in",
                metadata={"configured": True, "implemented": True},
            )

        if provider == "ollama":
            base_url = config.get("HEL_OLLAMA_BASE_URL") or OLLAMA_BASE_URL
            model = config.get("HEL_OLLAMA_MODEL") or OLLAMA_MODEL
            if not probe:
                return ProviderStatus(
                    provider=provider,
                    available=bool(base_url and model),
                    model=model,
                    metadata={"configured": bool(base_url and model), "implemented": True},
                )

            try:
                response = requests.get(
                    f"{base_url.rstrip('/')}/api/tags",
                    timeout=0.75,
                )
                available = response.status_code == 200
                model_names = []
                if available:
                    try:
                        model_names = [
                            str(item.get("name"))
                            for item in response.json().get("models", [])
                            if item.get("name")
                        ]
                    except (TypeError, ValueError, AttributeError):
                        available = False
                model_available = model in model_names
                return ProviderStatus(
                    provider=provider,
                    available=available and model_available,
                    model=model,
                    error=(None if available and model_available else
                           (f"model_not_found:{model}" if available else f"http_{response.status_code}")),
                    metadata={
                        "configured": True,
                        "implemented": True,
                        "base_url": base_url,
                        "model_available": model_available,
                        "models_count": len(model_names),
                    },
                )
            except requests.RequestException as exc:
                return ProviderStatus(
                    provider=provider,
                    available=False,
                    model=model,
                    error=type(exc).__name__,
                    metadata={"configured": True, "implemented": True, "base_url": base_url},
                )

        if provider in {"openai", "openai_compatible"}:
            api_key = config.get("HEL_OPENAI_API_KEY") or OPENAI_API_KEY
            model = config.get("HEL_OPENAI_MODEL") or OPENAI_MODEL
            base_url = config.get("HEL_OPENAI_BASE_URL") or OPENAI_BASE_URL
            configured = bool(api_key and model and base_url)
            return ProviderStatus(
                provider=provider,
                available=configured,
                model=model,
                error=None if configured else "api_key_missing",
                metadata={
                    "configured": configured,
                    "implemented": True,
                    "base_url": base_url,
                },
            )

        if provider == "claude":
            api_key = (
                config.get("HEL_ANTHROPIC_API_KEY")
                or config.get("ANTHROPIC_API_KEY")
                or ""
            )
            model = config.get("HEL_ANTHROPIC_MODEL") or "claude-3-5-sonnet"
            configured = bool(api_key)
            return ProviderStatus(
                provider=provider,
                available=False,
                model=model,
                error="adapter_not_connected",
                metadata={"configured": configured, "implemented": False},
            )

        api_key = config.get("HEL_FREELLMAPI_KEY") or config.get("FREELLMAPI_KEY") or ""
        model = config.get("HEL_FREELLMAPI_MODEL") or "default"
        configured = bool(api_key)
        return ProviderStatus(
            provider="freellmapi",
            available=False,
            model=model,
            error="adapter_not_connected",
            metadata={"configured": configured, "implemented": False},
        )


class RuntimeRegistry:
    """Small in-memory context/event registry for the current backend process."""

    def __init__(self, *, max_events: int = 256) -> None:
        self._events: deque[RuntimeEvent] = deque(maxlen=max_events)
        self._lock = Lock()
        self.providers = ProviderStatusService()

    def create_context(
        self,
        *,
        session_id: str,
        client: str = "desktop",
        platform: str = "windows",
        mode: str = "general",
        locale: str = "ru-RU",
        metadata: Mapping[str, Any] | None = None,
    ) -> RequestContext:
        return new_request_context(
            session_id=session_id,
            client=client,
            platform=platform,
            mode=mode,
            locale=locale,
            metadata=metadata,
        )

    def publish_event(
        self,
        *,
        event_type: str,
        source: str,
        request_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_type=event_type,
            source=source,
            request_id=request_id,
            payload=dict(payload or {}),
        )
        with self._lock:
            self._events.append(event)
        return event

    def list_events(
        self,
        *,
        limit: int = 50,
        chat_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 256))
        with self._lock:
            events = list(self._events)
        if chat_id is not None:
            events = [event for event in events if event.payload.get("chat_id") == chat_id]
        if turn_id is not None:
            events = [event for event in events if event.payload.get("turn_id") == turn_id]
        events = events[-safe_limit:]
        return [event.to_dict() for event in events]


runtime_registry = RuntimeRegistry()
