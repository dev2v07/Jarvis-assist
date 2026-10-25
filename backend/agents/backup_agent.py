from __future__ import annotations

import asyncio
import uuid
import time
import os

from core.agent_base import Agent
from config import (
    BACKUP_ROOT,
    CHROMA_PATH,
    FACTS_PATH,
    UPLOAD_DIR,
    BACKUP_SCHEDULE_HOURS
)

from utils.tooling import backup_data, list_backups


class BackupAgent(Agent):

    def __init__(self, bus):
        super().__init__("backup", bus)

        self.backup_root = str(BACKUP_ROOT)

        self.sources = [
            str(CHROMA_PATH),
            str(FACTS_PATH),
            str(UPLOAD_DIR)
        ]

        self._scheduler_task = None

    # --------------------------------
    # запуск агента
    # --------------------------------

    async def on_start(self):

        if not self._scheduler_task:

            self._scheduler_task = asyncio.create_task(
                self._scheduler()
            )

    # --------------------------------
    # планировщик backup
    # --------------------------------

    async def _scheduler(self):

        while True:

            try:

                await asyncio.sleep(
                    BACKUP_SCHEDULE_HOURS * 3600
                )

                path = backup_data(
                    self.sources,
                    self.backup_root
                )

                print(f"[BackupAgent] Backup created: {path}")

            except Exception as e:

                print(f"[BackupAgent ERROR] {e}")

    # --------------------------------
    # обработка сообщений
    # --------------------------------

    async def handle_message(self, msg):

        msg_type = msg.get("type")

        payload = msg.get("payload", {})

        request_id = payload.get("original_msg_id")

        try:

            # -------------------------
            # создать backup
            # -------------------------

            if msg_type == "tool_request":

                path = backup_data(
                    self.sources,
                    self.backup_root
                )

                result = f"Backup создан:\n{path}"

            # -------------------------
            # список backup
            # -------------------------

            elif msg_type == "list_backups":

                backups = list_backups(
                    self.backup_root
                )

                if backups:

                    result = "Резервные копии:\n" + "\n".join(backups)

                else:

                    result = "Резервные копии отсутствуют"

            else:
                return

        except Exception as e:

            result = f"BackupAgent error: {str(e)}"

        await self.bus.send(
            "executor",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "executor",
                "type": "tool_result",
                "payload": {
                    "original_msg_id": request_id,
                    "result": result
                },
            },
        )