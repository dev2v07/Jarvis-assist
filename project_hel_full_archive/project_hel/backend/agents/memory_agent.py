from __future__ import annotations
import uuid
from core.agent_base import Agent
from services.storage_service import store_fact, retrieve_facts

class MemoryAgent(Agent):
    def __init__(self, bus):
        super().__init__('memory', bus)

    async def handle_message(self, msg):
        msg_type = msg['type']
        payload = msg['payload']
        if msg_type == 'extract_facts':
            user = payload.get('user_message', '')
            if user:
                store_fact(user)
        elif msg_type == 'retrieve_facts':
            facts = retrieve_facts(payload.get('query', ''))
            await self.bus.send(msg['from'], {
                'id': str(uuid.uuid4()),
                'from': self.name,
                'to': msg['from'],
                'type': 'facts_result',
                'payload': {'facts': facts, 'original_msg_id': payload['original_msg_id']},
            })
