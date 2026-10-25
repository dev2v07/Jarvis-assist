from __future__ import annotations
import uuid
from core.agent_base import Agent


class VoiceAgent(Agent):
    def __init__(self, bus):
        super().__init__('voice', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return
        result = 'VoiceAgent подключён как каркас. Можно добавить STT/TTS провайдер.'
        await self.bus.send('executor', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'executor',
            'type': 'tool_result',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
