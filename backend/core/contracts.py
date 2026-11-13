"""Stable, platform-neutral contracts for the Jarvis runtime.

The desktop client, future web/mobile clients and device adapters must be able
to exchange these small JSON-compatible objects without importing Qt, FastAPI
or a concrete LLM provider.  The first queue only introduces and verifies the
contracts; existing chat and agent pipelines continue to use their current
messages until a dedicated migration queue is approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


CONTRACT_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _required(value: str, field_name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field_name} must not be empty")
    return result


@dataclass(frozen=True)
class RequestContext:
    """Identity and routing context shared by every Jarvis client."""

    request_id: str
    session_id: str
    client: str = "desktop"
    platform: str = "windows"
    mode: str = "general"
    locale: str = "ru-RU"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _required(self.request_id, "request_id"))
        object.__setattr__(self, "session_id", _required(self.session_id, "session_id"))
        object.__setattr__(self, "client", _required(self.client, "client"))
        object.__setattr__(self, "platform", _required(self.platform, "platform"))
        object.__setattr__(self, "mode", _required(self.mode, "mode"))
        object.__setattr__(self, "locale", _required(self.locale, "locale"))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "client": self.client,
            "platform": self.platform,
            "mode": self.mode,
            "locale": self.locale,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RequestContext":
        return cls(
            request_id=str(value.get("request_id", "")),
            session_id=str(value.get("session_id", "")),
            client=str(value.get("client", "desktop")),
            platform=str(value.get("platform", "windows")),
            mode=str(value.get("mode", "general")),
            locale=str(value.get("locale", "ru-RU")),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass(frozen=True)
class AgentResult:
    """Provider-independent result returned by an agent or tool adapter."""

    request_id: str
    agent: str
    status: str
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _required(self.request_id, "request_id"))
        object.__setattr__(self, "agent", _required(self.agent, "agent"))
        object.__setattr__(self, "status", _required(self.status, "status"))
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "data", dict(self.data or {}))
        object.__setattr__(self, "artifacts", list(self.artifacts or []))
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must not be negative")

    @classmethod
    def success(
        cls,
        request_id: str,
        agent: str,
        text: str = "",
        *,
        data: Mapping[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        duration_ms: int | None = None,
    ) -> "AgentResult":
        return cls(
            request_id=request_id,
            agent=agent,
            status="completed",
            text=text,
            data=dict(data or {}),
            artifacts=list(artifacts or []),
            duration_ms=duration_ms,
        )

    @classmethod
    def failure(
        cls,
        request_id: str,
        agent: str,
        error: str,
        *,
        data: Mapping[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> "AgentResult":
        return cls(
            request_id=request_id,
            agent=agent,
            status="failed",
            error=_required(error, "error"),
            data=dict(data or {}),
            duration_ms=duration_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "agent": self.agent,
            "status": self.status,
            "text": self.text,
            "data": dict(self.data),
            "artifacts": list(self.artifacts),
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class RuntimeEvent:
    """Versioned event envelope for SSE, WebSocket, IPC and MQTT adapters."""

    event_type: str
    source: str
    request_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    occurred_at: str = field(default_factory=_utc_now)
    schema_version: int = CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", _required(self.event_type, "event_type"))
        object.__setattr__(self, "source", _required(self.source, "source"))
        if self.request_id is not None:
            object.__setattr__(self, "request_id", _required(self.request_id, "request_id"))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "event_id", _required(self.event_id, "event_id"))
        object.__setattr__(self, "occurred_at", _required(self.occurred_at, "occurred_at"))
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "request_id": self.request_id,
            "occurred_at": self.occurred_at,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuntimeEvent":
        return cls(
            schema_version=int(value.get("schema_version", CONTRACT_SCHEMA_VERSION)),
            event_id=str(value.get("event_id", "")),
            event_type=str(value.get("event_type", "")),
            source=str(value.get("source", "")),
            request_id=value.get("request_id"),
            occurred_at=str(value.get("occurred_at", "")),
            payload=dict(value.get("payload") or {}),
        )


@dataclass(frozen=True)
class ProviderStatus:
    """Normalized provider health result for UI and device clients."""

    provider: str
    available: bool
    model: str | None = None
    latency_ms: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _required(self.provider, "provider"))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms must not be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "available": self.available,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


def new_request_context(
    *,
    session_id: str,
    client: str = "desktop",
    platform: str = "windows",
    mode: str = "general",
    locale: str = "ru-RU",
    metadata: Mapping[str, Any] | None = None,
) -> RequestContext:
    """Create a new context at an adapter boundary."""

    return RequestContext(
        request_id=uuid4().hex,
        session_id=session_id,
        client=client,
        platform=platform,
        mode=mode,
        locale=locale,
        metadata=dict(metadata or {}),
    )
