from __future__ import annotations
import uuid
from urllib.parse import urlparse
from core.agent_base import Agent

class NetworkAgent(Agent):
    def __init__(self, bus):
        super().__init__('network', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return
        step = msg['payload']['step']
        domain = ''
        for token in step.split():
            if token.startswith('http'):
                domain = urlparse(token).netloc
                break
        result = 'Сетевой агент: внешние запросы не включены в шаблоне. '
        result += f'Шаг: {step}'
        await self.bus.send('critic', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'critic',
            'type': 'critique',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
