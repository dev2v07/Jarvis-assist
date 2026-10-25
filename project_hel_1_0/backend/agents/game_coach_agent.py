from __future__ import annotations
import uuid
from core.agent_base import Agent


class GameCoachAgent(Agent):
    def __init__(self, bus):
        super().__init__('game_coach', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return
        result = 'GameCoachAgent: можно добавить разбор стратегий, билды и анализ скриншотов.'
        await self.bus.send('executor', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'executor',
            'type': 'tool_result',
            'payload': {'original_msg_id': msg['payload']['original_msg_id'], 'result': result},
        })
