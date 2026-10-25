from __future__ import annotations
import uuid
from core.agent_base import Agent
from services.tool_router import pick_route

class ExecutorAgent(Agent):
    def __init__(self, bus):
        super().__init__('executor', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'execute_step':
            return
        payload = msg['payload']
        step = payload['step']
        mode = payload.get('mode', 'general')
        route = pick_route(step, mode)
        original_msg_id = payload['original_msg_id']

        if route == 'backup':
            target = 'backup'
        elif route == 'files':
            target = 'file'
        elif route == 'network':
            target = 'network'
        elif route == 'system':
            target = 'performance'
        elif route == 'vision':
            target = 'vision'
        elif route == 'voice':
            target = 'voice'
        else:
            target = 'social'

        await self.bus.send(target, {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': target,
            'type': 'tool_request',
            'payload': {
                'step': step,
                'mode': mode,
                'original_msg_id': original_msg_id,
            },
        })

    async def return_tool_result(self, original_msg_id: str, result: str):
        await self.bus.send('critic', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'critic',
            'type': 'critique',
            'payload': {'original_msg_id': original_msg_id, 'result': result},
        })
