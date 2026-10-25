from __future__ import annotations
import json
import re
import uuid
from core.agent_base import Agent
from core.modes import MODES
from services.llm_service import llm_service

MODE_PROMPTS = {k: v['description'] for k, v in MODES.items()}

class PlannerAgent(Agent):
    def __init__(self, bus):
        super().__init__('planner', bus)
        self.pending: dict[str, list[str]] = {}

    async def handle_message(self, msg):
        if msg['type'] == 'create_plan':
            payload = msg['payload']
            goal = payload['goal']
            context = payload.get('context', '')
            original_msg_id = payload['original_msg_id']
            steps = await self._plan(goal, context)
            if steps:
                self.pending[original_msg_id] = steps
                await self.bus.send('main', {
                    'id': str(uuid.uuid4()),
                    'from': self.name,
                    'to': 'main',
                    'type': 'plan_approval',
                    'payload': {'original_msg_id': original_msg_id, 'goal': goal, 'steps': steps},
                })
            else:
                await self.bus.send('main', {
                    'id': str(uuid.uuid4()),
                    'from': self.name,
                    'to': 'main',
                    'type': 'final_response',
                    'payload': {'original_msg_id': original_msg_id, 'result': 'Не удалось построить план.'},
                })
        elif msg['type'] == 'plan_approved':
            original_id = msg['payload']['original_msg_id']
            steps = self.pending.pop(original_id, None)
            if steps:
                await self.bus.send('executor', {
                    'id': str(uuid.uuid4()),
                    'from': self.name,
                    'to': 'executor',
                    'type': 'execute_step',
                    'payload': {
                        'step': steps[0],
                        'context': '',
                        'original_msg_id': original_id,
                        'remaining_steps': steps[1:],
                        'mode': msg['payload'].get('mode', 'general'),
                    },
                })

    async def _plan(self, goal: str, context: str) -> list[str]:
        match = re.search(r'Режим:\s*([\w_]+)', context)
        mode = match.group(1) if match else 'general'
        system_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS['general'])
        messages = [{'role': 'user', 'content': goal}]
        _ = await llm_service.chat(messages, system_prompt=system_prompt)
        base_steps = [
            f'Понять задачу пользователя: {goal}',
            f'Выбрать подходящий инструмент для режима {mode}',
            'Сформировать и вернуть итоговый ответ пользователю',
        ]
        return base_steps
