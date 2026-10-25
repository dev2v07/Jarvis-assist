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

    async def run(self):
        while True:
            message = await self.bus.receive(self.name)
            await self.handle_message(message)

    async def handle_message(self, msg: Dict[str, Any]):
        raise NotImplementedError
