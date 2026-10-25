from __future__ import annotations

import uuid

from core.agent_base import Agent
from services.llm_service import llm_service


class GameCoachAgent(Agent):

    def __init__(self, bus):
        super().__init__("game_coach", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        step = payload.get("step", "")
        goal = payload.get("goal", "")

        try:

            # ---------------------------------------
            # запрос к LLM
            # ---------------------------------------

            response = await llm_service.chat(

                [
                    {
                        "role": "user",
                        "content": step or goal
                    }
                ],

                system_prompt="""
Ты игровой AI тренер.

Твоя задача:
- давать советы по играм
- предлагать стратегии
- объяснять тактику
- помогать улучшать скилл игрока

Отвечай коротко и понятно.
"""
            )

            result = response

        except Exception as e:

            result = f"GameCoachAgent error: {str(e)}"

        await self.bus.send(

            "executor",

            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": payload["original_msg_id"],
                    "result": result
                },
            },
        )