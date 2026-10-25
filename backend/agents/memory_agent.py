from __future__ import annotations

import uuid
import time
import re

from core.agent_base import Agent
from services.storage_service import store_fact, retrieve_facts


class MemoryAgent(Agent):

    def __init__(self, bus):
        super().__init__("memory", bus)

    async def handle_message(self, msg):

        msg_type = msg.get("type")
        payload = msg.get("payload", {})

        # -----------------------------------
        # извлечение фактов
        # -----------------------------------

        if msg_type == "extract_facts":

            user_message = payload.get("user_message", "")

            facts = self.extract_facts(user_message)

            for fact in facts:

                store_fact({
                    "text": fact,
                    "timestamp": int(time.time())
                })

        # -----------------------------------
        # получение памяти
        # -----------------------------------

        elif msg_type == "retrieve_facts":

            query = payload.get("query", "")

            facts = retrieve_facts(query)

            await self.bus.send(
                msg["from"],
                {
                    "id": str(uuid.uuid4()),
                    "from": self.name,
                    "to": msg["from"],
                    "type": "facts_result",
                    "payload": {
                        "facts": facts,
                        "original_msg_id": payload["original_msg_id"],
                    },
                },
            )

    # -----------------------------------
    # извлечение фактов
    # -----------------------------------

    def extract_facts(self, text: str):

        text = text.lower()

        facts = []

        patterns = [

            r"меня зовут ([а-яa-z]+)",
            r"я живу в ([а-яa-z\s]+)",
            r"мой город ([а-яa-z\s]+)",
            r"мне (\d+) лет",
            r"я работаю ([а-яa-z\s]+)",
            r"мой проект ([а-яa-z\s]+)",
            r"мой ник ([a-z0-9_]+)"

        ]

        for pattern in patterns:

            match = re.search(pattern, text)

            if match:

                facts.append(match.group(0))

        return facts