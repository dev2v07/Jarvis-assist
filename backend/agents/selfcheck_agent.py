from core.agent_base import Agent
import uuid
import asyncio


class SelfCheckAgent(Agent):

    def __init__(self, bus):
        super().__init__("selfcheck", bus)

    async def handle_message(self, msg):

        if msg.get("type") == "health_check":

            await self.bus.send(
                "main",
                {
                    "id": str(uuid.uuid4()),
                    "from": self.name,
                    "to": "main",
                    "type": "health_ok",
                    "payload": {
                        "status": "ok"
                    },
                },
            )

    async def run(self):

        while True:

            await asyncio.sleep(60)

            await self.bus.send(
                "main",
                {
                    "id": str(uuid.uuid4()),
                    "from": self.name,
                    "to": "main",
                    "type": "health_check",
                    "payload": {},
                },
            )