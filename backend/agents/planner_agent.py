from core.agent_base import Agent
import uuid
import re


class Planner(Agent):

    def __init__(self, bus):
        super().__init__("planner", bus)

    async def handle_message(self, msg):

        if msg["type"] != "create_plan":
            return

        goal = msg["payload"]["goal"]
        msg_id = msg["payload"].get("id") or msg["payload"].get("original_msg_id")

        self.publish_runtime_event("item.started", msg, {"item_type": "planner", "goal": goal})

        steps = self._formalize_plan(goal, self.create_plan(goal))

        self.publish_runtime_event(
            "plan.created",
            msg,
            {"goal": goal, "steps": steps, "step_count": len(steps)},
        )

        self.publish_runtime_event(
            "item.completed",
            msg,
            {"item_type": "planner", "step_count": len(steps)},
        )

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "execute_plan",
                "payload": {
                    "original_msg_id": msg_id,
                    "goal": goal,
                    "mode": "social",
                    "steps": steps,
                    "chat_id": msg["payload"].get("chat_id"),
                    "turn_id": msg["payload"].get("turn_id"),
                    "history": msg["payload"].get("history", []),
                    "custom_instructions": msg["payload"].get("custom_instructions", ""),
                    "preferred_address": msg["payload"].get("preferred_address", ""),
                    "chat_system_prompt": msg["payload"].get("chat_system_prompt", ""),
                },
            },
        )

    @staticmethod
    def _formalize_plan(goal, steps):
        """Add stable step IDs and cheap verification metadata.

        This is deliberately deterministic and local: it adds no LLM call to
        the fast path and gives the UI a useful, inspectable execution plan.
        """

        formal = []
        for index, raw_step in enumerate(steps or [], start=1):
            step = dict(raw_step)
            step.setdefault("id", f"step-{index}")
            step.setdefault("title", str(goal))
            step.setdefault("expected", "non_empty_result")
            step.setdefault("verification", {"strategy": "non_empty_result", "required": True})
            formal.append(step)
        return formal

    # ---------------------------------------------------
    # основной планировщик
    # ---------------------------------------------------

    def create_plan(self, goal):

        g = goal.lower()
        steps = []

        # ------------------------------------------------
        # youtube
        # ------------------------------------------------

        if any(word in g for word in ["youtube", "ютуб"]):

            steps.append(
                {
                    "title": "Open YouTube",
                    "route": "web",
                    "action": "open_url",
                    "target": "https://youtube.com",
                }
            )

            return steps

        # ------------------------------------------------
        # браузер
        # ------------------------------------------------

        if any(word in g for word in ["браузер", "browser", "интернет"]):

            steps.append(
                {
                    "title": "Open Browser",
                    "route": "web",
                    "action": "open_url",
                    "target": "https://google.com",
                }
            )

            return steps

        # ------------------------------------------------
        # музыка
        # ------------------------------------------------

        if any(word in g for word in ["музыку", "музыка", "music"]):

            steps.append(
                {
                    "title": "Open Yandex Music",
                    "route": "web",
                    "action": "open_url",
                    "target": "https://music.yandex.ru",
                }
            )

            return steps

        # ------------------------------------------------
        # скриншот
        # ------------------------------------------------

        if any(word in g for word in ["скрин", "screenshot", "экран"]):

            steps.append(
                {
                    "title": "Take Screenshot",
                    "route": "vision",
                    "action": "screenshot",
                }
            )

            return steps

        # ------------------------------------------------
        # работа с файлами
        # ------------------------------------------------

        if any(word in g for word in ["файл", "file"]):

            steps.append(
                {
                    "title": goal,
                    "route": "files",
                    "action": "file_operation",
                }
            )

            return steps

        # ------------------------------------------------
        # проверить сайт
        # ------------------------------------------------

        url = self._extract_url(g)

        if url:

            steps.append(
                {
                    "title": f"Check website {url}",
                    "route": "network",
                    "action": "fetch",
                    "target": url,
                }
            )

            return steps

        # ------------------------------------------------
        # системная информация
        # ------------------------------------------------

        if any(word in g for word in ["cpu", "ram", "память", "нагрузку"]):

            steps.append(
                {
                    "title": "Check system performance",
                    "route": "system",
                    "action": "monitor",
                }
            )

            return steps

        # ------------------------------------------------
        # fallback → social agent
        # ------------------------------------------------

        steps.append(
            {
                "title": goal,
                "route": "social",
                "action": "ai_response",
            }
        )

        return steps

    # ---------------------------------------------------
    # извлечение url
    # ---------------------------------------------------

    def _extract_url(self, text):

        match = re.search(r"(https?://\S+)", text)

        if match:
            return match.group(1).rstrip(",.;:!?)]}")

        # Bare domains are accepted only when they look like domains.  A
        # filename such as ``air_kiss.gif`` is semantic chat media, not a URL;
        # treating every dotted token as a network target was the reason Mail.Ru
        # emotes were sent to NetworkAgent in Jarvis instead of remaining
        # attachments.  This mirrors Crazy Tad's separation of media metadata
        # from tool routing.
        bare_domain = re.search(
            r"(?<![\w-])(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:com|ru|org|net|io|dev|ai|app|me|tv|info|biz)(?:/[^\s]*)?",
            text,
            re.IGNORECASE,
        )
        if bare_domain:
            return bare_domain.group(0).rstrip(",.;:!?)]}")

        return None
