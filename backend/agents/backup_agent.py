from __future__ import annotations

import asyncio
import uuid
import time
import os
from datetime import datetime, timezone

from core.agent_base import Agent
from config import (
    BACKUP_ROOT,
    CHROMA_PATH,
    FACTS_PATH,
    UPLOAD_DIR,
    BACKUP_SCHEDULE_HOURS
    ,STATE_DB_PATH
)

from utils.tooling import backup_data, list_backups


class BackupAgent(Agent):

    def __init__(self, bus):
        super().__init__("backup", bus)

        self.backup_root = str(BACKUP_ROOT)

        self.sources = [
            str(CHROMA_PATH),
            str(FACTS_PATH),
            str(UPLOAD_DIR),
            str(STATE_DB_PATH),
        ]

        self._scheduler_task = None
        self._last_backup: str | None = None
        self._last_error: str | None = None
        self._next_backup_at: str | None = None

    # --------------------------------
    # запуск агента
    # --------------------------------

    async def on_start(self):

        if not self._scheduler_task:

            self._scheduler_task = asyncio.create_task(
                self._scheduler()
            )

    async def on_stop(self):
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

    # --------------------------------
    # планировщик backup
    # --------------------------------

    async def _scheduler(self):

        while True:

            try:

                self._next_backup_at = datetime.now(timezone.utc).timestamp() + BACKUP_SCHEDULE_HOURS * 3600
                await asyncio.sleep(BACKUP_SCHEDULE_HOURS * 3600)
                path = await asyncio.to_thread(backup_data, self.sources, self.backup_root)
                self._last_backup = path
                self._last_error = None
                self.publish_runtime_event("backup.completed", {"payload": {}}, {"path": path})
                print(f"[BackupAgent] Backup created: {path}")

            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    raise
                self._last_error = str(e)
                print(f"[BackupAgent ERROR] {e}")

    def status(self) -> dict:
        return {
            "enabled": bool(self._scheduler_task and not self._scheduler_task.done()),
            "interval_hours": BACKUP_SCHEDULE_HOURS,
            "sources": self.sources,
            "last_backup": self._last_backup,
            "last_error": self._last_error,
            "next_backup_at": self._next_backup_at,
        }

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
