from __future__ import annotations
import asyncio
import uuid
from core.agent_base import Agent
from config import BACKUP_ROOT, CHROMA_PATH, FACTS_PATH, UPLOAD_DIR, BACKUP_SCHEDULE_HOURS
from utils.tooling import backup_data, list_backups


class BackupAgent(Agent):
    def __init__(self, bus):
        super().__init__('backup', bus)
        self.backup_root = str(BACKUP_ROOT)
        self.sources = [str(CHROMA_PATH), str(FACTS_PATH), str(UPLOAD_DIR)]
        self._scheduler_task = None

    async def on_start(self):
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler())

    async def _scheduler(self):
        while True:
            await asyncio.sleep(BACKUP_SCHEDULE_HOURS * 3600)
            backup_data(self.sources, self.backup_root)

    async def handle_message(self, msg):
        if msg['type'] == 'tool_request':
            result = f"Резервная копия создана: {backup_data(self.sources, self.backup_root)}"
        elif msg['type'] == 'list_backups':
            result = "\n".join(list_backups(self.backup_root)) or 'Нет резервных копий.'
        else:
            return
        await self.bus.send('executor', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'executor',
            'type': 'tool_result',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
