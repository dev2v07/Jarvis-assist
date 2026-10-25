from __future__ import annotations

import re
import uuid
import os

from core.agent_base import Agent
from utils.tooling import (
    list_files_safe,
    read_file_safe,
    write_file_safe
)


class FileAgent(Agent):

    def __init__(self, bus):
        super().__init__("file", bus)

    async def handle_message(self, msg):

        if msg["type"] != "tool_request":
            return

        payload = msg["payload"]

        request_id = payload["original_msg_id"]
        step = payload.get("step", "")
        goal = payload.get("goal", "")
        target = payload.get("target") or self._extract_path(step) or self._extract_path(goal)

        text = f"{goal} {step}".lower()

        try:

            # ------------------------------------
            # LIST FILES
            # ------------------------------------

            if any(k in text for k in ["список", "list", "покажи файлы"]):

                files = list_files_safe(".")

                result = "Содержимое workspace:\n" + files

            # ------------------------------------
            # READ FILE
            # ------------------------------------

            elif any(k in text for k in ["прочитай", "открой", "read"]):

                if not target:
                    result = "Не указан файл для чтения"

                else:

                    content = read_file_safe(target)

                    result = f"Файл: {target}\n\n{content[:4000]}"

            # ------------------------------------
            # WRITE FILE
            # ------------------------------------

            elif any(k in text for k in ["сохрани", "запиши", "создай", "write"]):

                if not target:
                    result = "Не указан файл для записи"

                else:

                    content = self._build_content(goal, step)

                    result = write_file_safe(target, content)

            # ------------------------------------
            # DELETE FILE
            # ------------------------------------

            elif any(k in text for k in ["удали", "delete"]):

                if not target:
                    result = "Не указан файл"

                else:

                    os.remove(target)

                    result = f"Файл удалён: {target}"

            # ------------------------------------
            # DEFAULT
            # ------------------------------------

            else:

                files = list_files_safe(".")

                result = "Файловый агент не понял действие.\n\nWorkspace:\n" + files

        except Exception as e:

            result = f"FileAgent error: {str(e)}"

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": request_id,
                    "result": result,
                },
            },
        )

    # ----------------------------------------
    # PATH EXTRACTOR
    # ----------------------------------------

    def _extract_path(self, text: str) -> str | None:

        match = re.search(r"([\w./\\-]+\.[\w]+)", text)

        if match:
            return match.group(1)

        return None

    # ----------------------------------------
    # BUILD FILE CONTENT
    # ----------------------------------------

    def _build_content(self, goal: str, step: str) -> str:

        explicit = re.search(r":\s*(.+)$", goal)

        if explicit:

            body = explicit.group(1).strip()

        else:

            body = f"Создано Jarvis на основе запроса:\n{goal}"

        return body + "\n"