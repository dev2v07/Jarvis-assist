from __future__ import annotations
import asyncio
from typing import Any, Dict
from core.message_bus import MessageBus


class Agent:

    def __init__(self, name: str, bus: MessageBus):

        self.name = name
        self.bus = bus

        self.bus.register_agent(name)

        self._task: asyncio.Task | None = None
        self._running = False


    # ---------------------------
    # start agent
    # ---------------------------

    def start(self):

        if not self._task:
            self._running = True
            on_start = getattr(self, "on_start", None)
            if on_start:
                self._lifecycle_task = asyncio.create_task(on_start())
            self._task = asyncio.create_task(self.run())


    # ---------------------------
    # stop agent
    # ---------------------------

    async def stop(self):

        self._running = False

        if self._task:
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

        on_stop = getattr(self, "on_stop", None)
        if on_stop:
            await on_stop()


    # ---------------------------
    # main loop
    # ---------------------------

    async def run(self):

        while self._running:

            try:

                message = await self.bus.receive(self.name)

                await self.handle_message(message)

            except Exception as e:

                print(f"[{self.name}] error:", e)


    # ---------------------------
    # message handler
    # ---------------------------

    async def handle_message(self, msg: Dict[str, Any]):

        raise NotImplementedError

    def publish_runtime_event(self, event_type: str, msg: Dict[str, Any], payload: Dict[str, Any] | None = None):
        """Publish a Codex-like lifecycle event without changing bus contracts."""
        from services.runtime_service import runtime_registry

        source_payload = msg.get("payload", {}) or {}
        runtime_registry.publish_event(
            event_type=event_type,
            source=self.name,
            request_id=source_payload.get("original_msg_id") or source_payload.get("id"),
            payload={
                "chat_id": source_payload.get("chat_id"),
                "turn_id": source_payload.get("turn_id"),
                "agent": self.name,
                **dict(payload or {}),
            },
        )
