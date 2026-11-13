"""Local JSON-RPC app-server facade for Jarvis threads and turns.

This is intentionally an adapter around Jarvis' existing chat pipeline.  The
Planner, Executor and specialist agents remain the execution engine; this
module gives desktop and future clients a Codex-like lifecycle boundary.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from services.chat_store import ChatStore
from services.runtime_service import RuntimeRegistry


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


TurnRunner = Callable[[str, str, str, list[dict[str, Any]]], Awaitable[dict[str, Any]]]


class AppServer:
    """Dispatch the stable subset of Codex app-server methods used by Jarvis."""

    def __init__(self, chat_store: ChatStore, runtime: RuntimeRegistry):
        self.chat_store = chat_store
        self.runtime = runtime
        self._turn_runner: TurnRunner | None = None
        self._tasks: dict[str, asyncio.Task] = {}

    def set_turn_runner(self, runner: TurnRunner) -> None:
        self._turn_runner = runner

    async def handle(self, request: Mapping[str, Any]) -> dict[str, Any] | None:
        if request.get("jsonrpc") not in (None, "2.0"):
            return self._error(request.get("id"), -32600, "jsonrpc must be 2.0")
        method = str(request.get("method") or "")
        request_id = request.get("id")
        params = request.get("params") or {}
        if not method or not isinstance(params, Mapping):
            return self._error(request_id, -32600, "invalid JSON-RPC request")

        try:
            result = await self._dispatch(method, dict(params))
        except JsonRpcError as exc:
            return self._error(request_id, exc.code, exc.message, exc.data)
        except Exception as exc:
            return self._error(request_id, -32000, "app-server request failed", {"type": type(exc).__name__})

        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    async def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": "2026-01-01",
                "serverInfo": {"name": "jarvis-app-server", "version": "0.1"},
                "capabilities": {
                    "threads": True,
                    "turns": True,
                    "events": True,
                    "interrupt": True,
                },
            }
        if method in {"thread/start", "thread/create"}:
            return self._thread_start(params)
        if method in {"thread/read", "thread/resume"}:
            return self._thread_read(params)
        if method == "thread/list":
            return {"threads": self.chat_store.list_sessions(include_archived=bool(params.get("includeArchived")))}
        if method == "turn/start":
            return await self._turn_start(params)
        if method in {"turn/interrupt", "turn/abort"}:
            return await self._turn_interrupt(params)
        if method == "runtime/events":
            return {
                "events": self.runtime.list_events(
                    limit=int(params.get("limit", 50)),
                    chat_id=params.get("threadId") or params.get("chatId"),
                    turn_id=params.get("turnId"),
                )
            }
        raise JsonRpcError(-32601, f"method not found: {method}")

    def _thread_start(self, params: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(params.get("threadId") or uuid.uuid4())
        existing = self.chat_store.get_session(thread_id)
        thread = existing or self.chat_store.create_session(
            title=str(params.get("name") or params.get("title") or "Новый чат"),
            chat_id=thread_id,
        )
        if not existing:
            self.runtime.publish_event(
                event_type="thread.started",
                source="app-server",
                payload={"chat_id": thread_id, "thread_id": thread_id},
            )
        return {"thread": self._thread_view(thread)}

    def _thread_read(self, params: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(params.get("threadId") or params.get("chatId") or "")
        if not thread_id:
            raise JsonRpcError(-32602, "threadId is required")
        thread = self.chat_store.get_session(thread_id)
        if not thread:
            raise JsonRpcError(-32004, "thread not found")
        return {
            "thread": self._thread_view(thread),
            "messages": self.chat_store.list_messages(thread_id, int(params.get("limit", 500))),
        }

    async def _turn_start(self, params: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(params.get("threadId") or params.get("chatId") or "")
        if not thread_id:
            raise JsonRpcError(-32602, "threadId is required")
        if not self.chat_store.get_session(thread_id):
            self.chat_store.create_session(title="Новый чат", chat_id=thread_id)
        if not self._turn_runner:
            raise JsonRpcError(-32000, "turn runner is not configured")
        text = self._extract_text(params.get("input", params.get("message", "")))
        if not text:
            raise JsonRpcError(-32602, "input text is required")
        turn_id = str(params.get("turnId") or uuid.uuid4())
        if turn_id in self._tasks and not self._tasks[turn_id].done():
            raise JsonRpcError(-32009, "turn is already running")
        attachments = [item for item in params.get("attachments", []) if isinstance(item, dict)]
        task = asyncio.create_task(self._run_turn(thread_id, turn_id, text, attachments))
        self._tasks[turn_id] = task
        return {"turn": {"id": turn_id, "threadId": thread_id, "status": "inProgress"}}

    async def _run_turn(self, thread_id: str, turn_id: str, text: str, attachments: list[dict[str, Any]]) -> None:
        try:
            await self._turn_runner(thread_id, turn_id, text, attachments)
        except asyncio.CancelledError:
            self.runtime.publish_event(
                event_type="turn.aborted",
                source="app-server",
                payload={"chat_id": thread_id, "turn_id": turn_id},
            )
            raise
        except Exception as exc:
            self.runtime.publish_event(
                event_type="turn.failed",
                source="app-server",
                payload={"chat_id": thread_id, "turn_id": turn_id, "error": type(exc).__name__},
            )
        finally:
            self._tasks.pop(turn_id, None)

    async def _turn_interrupt(self, params: dict[str, Any]) -> dict[str, Any]:
        turn_id = str(params.get("turnId") or "")
        task = self._tasks.get(turn_id)
        if not task or task.done():
            return {"turnId": turn_id, "interrupted": False}
        task.cancel()
        return {"turnId": turn_id, "interrupted": True}

    @staticmethod
    def _extract_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, Mapping) and item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text") or item.get("content") or ""))
            return "\n".join(part.strip() for part in parts if part.strip())
        return ""

    @staticmethod
    def _thread_view(thread: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": str(thread.get("id")),
            "name": thread.get("title") or "Новый чат",
            "status": "idle",
            "pinned": bool(thread.get("pinned")),
            "archived": bool(thread.get("archived")),
            "createdAt": thread.get("created_at"),
            "updatedAt": thread.get("updated_at"),
        }

    @staticmethod
    def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}
