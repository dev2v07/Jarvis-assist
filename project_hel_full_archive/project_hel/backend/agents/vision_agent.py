from __future__ import annotations
import uuid
from core.agent_base import Agent

class VisionAgent(Agent):
    def __init__(self, bus):
        super().__init__('vision', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return
        step = msg['payload']['step']
        result = f'VisionAgent готов анализировать изображения. Полученный шаг: {step}'
        await self.bus.send('critic', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'critic',
            'type': 'critique',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
