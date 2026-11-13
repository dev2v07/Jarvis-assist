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
        history = payload.get("history") or []
        custom_instructions = str(payload.get("custom_instructions") or "").strip()
        preferred_address = str(payload.get("preferred_address") or "").strip()
        chat_system_prompt = str(payload.get("chat_system_prompt") or "").strip()

        self.publish_runtime_event("item.started", msg, {"item_type": "social"})

        try:

            messages = []
            for item in history[-12:]:
                role = "assistant" if item.get("role") in {"assistant", "agent"} else "user"
                content = str(item.get("content") or "").strip()
                if content:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": step or goal})

            prompt_parts = [
                "Ты Jarvis — живой персональный AI-ассистент пользователя.",
                "Отвечай естественно, по-человечески и прямо на последнюю реплику.",
                "Не описывай свою работу, не создавай варианты ответа, не добавляй мета-комментарии.",
                "Для простого приветствия отвечай коротко и тепло, без шаблонных анкет и лишних уточнений.",
                "Не исправляй и не переписывай собственный ответ после его формулировки.",
            ]
            if preferred_address:
                prompt_parts.append(f"Обращайся к пользователю как: {preferred_address}.")
            if custom_instructions:
                prompt_parts.append(f"Пользовательские инструкции:\n{custom_instructions[:12000]}")
            if chat_system_prompt:
                prompt_parts.append(f"Дополнительные инструкции этого чата:\n{chat_system_prompt[:12000]}")

            response_parts = []
            system_prompt = "\n".join(prompt_parts)
            async for delta in llm_service.chat_stream(messages, system_prompt=system_prompt):
                response_parts.append(delta)
                self.publish_runtime_event(
                    "message.delta",
                    msg,
                    {
                        "message_id": request_id,
                        "content": delta,
                        "accumulated": "".join(response_parts),
                    },
                )
            response = "".join(response_parts).strip()

            if not response:
                response = "Я пока не знаю как ответить."

            self.publish_runtime_event("item.completed", msg, {"item_type": "social"})

        except Exception as e:

            response = f"Ошибка SocialAgent: {str(e)}"
            self.publish_runtime_event(
                "item.failed",
                msg,
                {"item_type": "social", "error": str(e)},
            )

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": request_id,
                    "chat_id": payload.get("chat_id"),
                    "turn_id": payload.get("turn_id"),
                    "result": response
                },
            },
        )
