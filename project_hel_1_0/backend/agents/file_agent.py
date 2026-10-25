from __future__ import annotations
import re
import uuid
from core.agent_base import Agent
from utils.tooling import list_files_safe, read_file_safe, write_file_safe


class FileAgent(Agent):
    def __init__(self, bus):
        super().__init__('file', bus)

    async def handle_message(self, msg):
        if msg['type'] != 'tool_request':
            return

        payload = msg['payload']
        step = payload.get('step', '')
        goal = payload.get('goal', '')
        target = payload.get('target') or self._extract_path(step) or self._extract_path(goal) or '.'
        normalized = f'{goal} {step}'.lower()

        if any(token in normalized for token in ['прочитай', 'открой', 'read']) and target not in {'.', ''}:
            result = f'Файл прочитан: {target}\n\n{read_file_safe(target)[:4000]}'
        elif any(token in normalized for token in ['сохрани', 'запиши', 'создай', 'write']) and target not in {'.', ''}:
            content = self._build_content(goal, step)
            result = write_file_safe(target, content)
        else:
            files = list_files_safe('.')
            result = 'Файловый агент обработал шаг. Содержимое workspace:\n' + files

        await self.bus.send('executor', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'executor',
            'type': 'tool_result',
            'payload': {'original_msg_id': payload['original_msg_id'], 'result': result},
        })

    def _extract_path(self, text: str) -> str | None:
        match = re.search(r'([\w./\\-]+\.[\w]+)', text)
        return match.group(1) if match else None

    def _build_content(self, goal: str, step: str) -> str:
        explicit = re.search(r'[:]\s*(.+)$', goal)
        if explicit:
            body = explicit.group(1).strip()
        else:
            body = f'Создано агентом Hel на основе запроса: {goal}'
        return body + '\n'
