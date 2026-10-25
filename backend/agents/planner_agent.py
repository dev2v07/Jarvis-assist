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

        steps = self.create_plan(goal)

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
                },
            },
        )

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
            return match.group(1)

        tokens = text.split()

        for t in tokens:
            if "." in t and "/" not in t:
                return t.strip(",.")

        return None