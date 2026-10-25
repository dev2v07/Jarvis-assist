from __future__ import annotations

import uuid
from core.agent_base import Agent
from services.llm_service import llm_service


class SocialAgent(Agent):

    def __init__(self, bus):
        super().__init__("social", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        request_id = payload["original_msg_id"]
        step = payload.get("step", "")
        goal = payload.get("goal", "")

        try:

            response = await llm_service.chat(
                [
                    {
                        "role": "user",
                        "content": step or goal
                    }
                ],
                system_prompt=(
                    "Ты социальный модуль голосового ассистента Jarvis. "
                    "Отвечай дружелюбно, кратко и естественно."
                ),
            )

            if not response:
                response = "Я пока не знаю как ответить."

        except Exception as e:

            response = f"Ошибка SocialAgent: {str(e)}"

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": request_id,
                    "result": response
                },
            },
        )