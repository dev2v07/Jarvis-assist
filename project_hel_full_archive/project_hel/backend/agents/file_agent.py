from __future__ import annotations
import uuid
from core.agent_base import Agent
from utils.tooling import list_files_safe

class FileAgent(Agent):
    def __init__(self, bus):
        super().__init__('file', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return
        files = list_files_safe('.')
        result = 'Файловый агент обработал шаг. Содержимое workspace:\n' + files
        await self.bus.send('critic', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'critic',
            'type': 'critique',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
