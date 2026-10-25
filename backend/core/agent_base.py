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