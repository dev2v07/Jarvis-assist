"""Single-owner coordination for Jarvis voice sessions.

This is deliberately an in-memory lifecycle guard, not a second history or
session database. Voice turns continue to be persisted by ChatStore.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any


class VoiceSessionManager:
    """Allow exactly one active voice owner at a time."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active: dict[str, Any] | None = None

    def start(self, *, source: str, chat_id: str, replace: bool = False) -> dict[str, Any]:
        source = str(source or "widget").strip().lower()
        if source not in {"widget", "chat"}:
            raise ValueError("source must be widget or chat")
        chat_id = str(chat_id or "default")
        with self._lock:
            if self._active and not replace:
                raise RuntimeError("voice session already active")
            session = {
                "session_id": "voice_" + uuid.uuid4().hex,
                "source": source,
                "chat_id": chat_id,
                "state": "starting",
                "active": True,
            }
            self._active = session
            return dict(session)

    def stop(self, *, session_id: str | None = None, source: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            if not self._active:
                return None
            if session_id and session_id != self._active["session_id"]:
                return None
            if source and source != self._active["source"]:
                return None
            ended = dict(self._active)
            ended["state"] = "stopped"
            ended["active"] = False
            self._active = None
            return ended

    def update(self, **values: Any) -> dict[str, Any] | None:
        with self._lock:
            if not self._active:
                return None
            self._active.update(values)
            return dict(self._active)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._active or {"active": False})

    @property
    def active(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._active) if self._active else None
