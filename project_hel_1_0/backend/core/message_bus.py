import asyncio
from typing import Any, Dict

class MessageBus:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def register_agent(self, agent_name: str):
        if agent_name not in self._queues:
            self._queues[agent_name] = asyncio.Queue()

    async def send(self, to: str, message: Dict[str, Any]):
        if to not in self._queues:
            raise KeyError(f'Agent not registered: {to}')
        await self._queues[to].put(message)

    async def receive(self, agent_name: str) -> Dict[str, Any]:
        if agent_name not in self._queues:
            raise KeyError(f'Agent not registered: {agent_name}')
        return await self._queues[agent_name].get()

    def registered_agents(self) -> list[str]:
        return sorted(self._queues.keys())
