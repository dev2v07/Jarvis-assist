from __future__ import annotations
import uuid
from core.agent_base import Agent
from services.llm_service import llm_service


class CriticAgent(Agent):
    def __init__(self, bus):
        super().__init__('critic', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'review_result':
            return
        payload = msg['payload']
        result = payload['result']
        final = result.strip() if result else 'Пустой результат.'
        try:
            improved = await llm_service.chat(
                [{'role': 'user', 'content': final}],
                system_prompt='Сожми и структурируй результат в понятный ответ на русском языке. Не выдумывай факты.',
            )
            if improved.strip():
                final = improved.strip()
        except Exception:
            pass
        artifacts = [a for a in payload.get('artifacts', []) if a]
        if artifacts:
            lines = [f"- {a.get('name', 'artifact')} ({a.get('type', 'unknown')}): {a.get('path', '')}" for a in artifacts]
            final += '\n\nАртефакты:\n' + '\n'.join(lines)
        if len(final) < 10:
            final += '\n\n[Критик]: ответ получился слишком кратким, стоит дополнить деталями.'
        await self.bus.send('main', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'main',
            'type': 'final_response',
            'payload': {'original_msg_id': payload['original_msg_id'], 'result': final},
        })
