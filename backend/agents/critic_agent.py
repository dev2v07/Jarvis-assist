from __future__ import annotations

import uuid

from core.agent_base import Agent
from services.llm_service import llm_service


class CriticAgent(Agent):

    def __init__(self, bus):
        super().__init__("critic", bus)

    async def handle_message(self, msg):

        if msg["type"] != "review_result":
            return

        payload = msg["payload"]

        request_id = payload["original_msg_id"]
        result = payload.get("result", "")
        goal = payload.get("goal", "")
        artifacts = payload.get("artifacts", [])

        final = result.strip() if result else "Результат отсутствует."

        # ---------------------------------------
        # LLM анализ результата
        # ---------------------------------------

        try:

            improved = await llm_service.chat(

                [
                    {
                        "role": "user",
                        "content": f"""
Задача пользователя:
{goal}

Результат выполнения:
{final}

Проверь результат и:
1. Исправь возможные ошибки
2. Сделай ответ понятным
3. Структурируй информацию
"""
                    }
                ],

                system_prompt="""
Ты AI критик системы Jarvis.

Твоя задача:
- проверять результат выполнения задачи
- исправлять ошибки
- улучшать формулировку ответа

Никогда не выдумывай факты.
"""
            )

            if improved and improved.strip():

                final = improved.strip()

        except Exception:
            pass

        # ---------------------------------------
        # артефакты
        # ---------------------------------------

        artifacts = [a for a in artifacts if a]

        if artifacts:

            lines = []

            for a in artifacts:

                lines.append(
                    f"- {a.get('name','artifact')} "
                    f"({a.get('type','unknown')}): "
                    f"{a.get('path','')}"
                )

            final += "\n\nАртефакты:\n" + "\n".join(lines)

        # ---------------------------------------
        # защита от пустых ответов
        # ---------------------------------------

        if len(final) < 15:

            final += "\n\n[Jarvis]: результат получился слишком кратким."

        # ---------------------------------------
        # отправка в main
        # ---------------------------------------

        await self.bus.send(

    "main",

    {
        "id": str(uuid.uuid4()),
        "from": self.name,
        "to": "main",
        "type": "review_result",
        "payload": {
            "original_msg_id": request_id,
            "result": final
        },
    },
)