import asyncio
from typing import Any, Dict


class MessageBus:

    def __init__(self):

        self._queues: dict[str, asyncio.Queue] = {}

    # ----------------------------
    # register
    # ----------------------------

    def register_agent(self, agent_name: str):

        if agent_name not in self._queues:

            self._queues[agent_name] = asyncio.Queue()

            print(f"[Bus] registered: {agent_name}")

    # ----------------------------
    # send
    # ----------------------------

    async def send(self, to: str, message: Dict[str, Any]):

        if to not in self._queues:
            raise KeyError(f"Agent not registered: {to}")

        await self._queues[to].put(message)

    # ----------------------------
    # broadcast
    # ----------------------------

    async def broadcast(self, message: Dict[str, Any]):

        for q in self._queues.values():

            await q.put(message)

    # ----------------------------
    # receive
    # ----------------------------

    async def receive(self, agent_name: str, timeout: float | None = None):

        if agent_name not in self._queues:
            raise KeyError(f"Agent not registered: {agent_name}")

        queue = self._queues[agent_name]

        if timeout:

            try:
                return await asyncio.wait_for(queue.get(), timeout)

            except asyncio.TimeoutError:
                return None

        return await queue.get()

    # ----------------------------
    # helpers
    # ----------------------------

    def registered_agents(self):

        return sorted(self._queues.keys())

    def queue_sizes(self):

        return {
            name: q.qsize()
            for name, q in self._queues.items()
        }