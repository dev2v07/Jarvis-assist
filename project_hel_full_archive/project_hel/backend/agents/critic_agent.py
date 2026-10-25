from __future__ import annotations
import uuid
from core.agent_base import Agent

class CriticAgent(Agent):
    def __init__(self, bus):
        super().__init__('critic', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'critique':
            return
        payload = msg['payload']
        result = payload['result']
        final = result.strip() if result else 'Пустой результат.'
        if len(final) < 10:
            final += '\n\n[Критик]: ответ получился слишком кратким, стоит дополнить деталями.'
        await self.bus.send('main', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'main',
            'type': 'final_response',
            'payload': {'original_msg_id': payload['original_msg_id'], 'result': final},
        })
