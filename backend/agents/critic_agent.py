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

        self.publish_runtime_event("item.started", msg, {"item_type": "critic"})

        final = result.strip() if result else "Результат отсутствует."

        # Conversational replies should reach the user as one answer.  Running
        # a second LLM pass over a greeting made small local models emit three
        # competing rewrites and invented commentary.
        conversational = not artifacts and len(goal.strip()) <= 120 and not any(
            token in goal.lower()
            for token in ("создай", "сделай", "открой", "найди", "проверь", "прочитай", "удали", "запиши")
        )

        if not conversational:
            try:
                improved = await llm_service.chat(
                    [{"role": "user", "content": f"""
Задача пользователя:
{goal}

Результат выполнения:
{final}

Верни только один окончательный ответ пользователю. Исправь только фактические
ошибки и сделай текст понятным. Не добавляй варианты ответа, мета-комментарии,
разделы «исправленный ответ», «улучшенная формулировка», «структурированная
информация», планы проверки или выдуманные детали.
"""}],
                    system_prompt="""
Ты финальный редактор Jarvis. Верни только один короткий ответ пользователю.
Не перечисляй альтернативные формулировки и не описывай собственную работу.
Сохраняй факты результата и не выдумывай новые.
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

        # Short answers are valid conversational answers ("Да", "Спасибо",
        # "Здравствуйте"). Never append internal diagnostics to user text.
        if not final.strip():
            final = "Я не смог сформировать ответ."

        self.publish_runtime_event("item.completed", msg, {"item_type": "critic"})

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
            "chat_id": payload.get("chat_id"),
            "turn_id": payload.get("turn_id"),
            "result": final
        },
    },
)
