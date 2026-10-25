from __future__ import annotations
import re
import uuid
from core.agent_base import Agent
from core.modes import MODES
from services.llm_service import llm_service
from services.tool_router import pick_route

MODE_PROMPTS = {k: v['description'] for k, v in MODES.items()}


class PlannerAgent(Agent):
    def __init__(self, bus):
        super().__init__('planner', bus)
        self.pending: dict[str, dict] = {}

    async def handle_message(self, msg):
        if msg['type'] == 'create_plan':
            payload = msg['payload']
            goal = payload['goal']
            context = payload.get('context', '')
            original_msg_id = payload['original_msg_id']
            mode = payload.get('mode', 'general')
            steps = await self._plan(goal, context)
            if steps:
                self.pending[original_msg_id] = {'steps': steps, 'goal': goal, 'mode': mode}
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
            pending = self.pending.pop(original_id, None)
            if pending:
                await self.bus.send('executor', {
                    'id': str(uuid.uuid4()),
                    'from': self.name,
                    'to': 'executor',
                    'type': 'execute_plan',
                    'payload': {
                        'original_msg_id': original_id,
                        'goal': pending['goal'],
                        'steps': pending['steps'],
                        'mode': msg['payload'].get('mode', pending.get('mode', 'general')),
                    },
                })

    async def _plan(self, goal: str, context: str) -> list[dict]:
        match = re.search(r'Режим:\s*([\w_]+)', context)
        mode = match.group(1) if match else 'general'
        llm_steps = await llm_service.plan_steps(goal, mode, context)
        if llm_steps:
            return [self._make_step(step, mode, idx + 1, goal) for idx, step in enumerate(llm_steps)]
        return self._heuristic_plan(goal, mode)

    def _make_step(self, title: str, mode: str, idx: int, goal: str) -> dict:
        route = pick_route(title, mode)
        target = self._extract_url(title) or self._extract_path(title) or self._extract_url(goal) or self._extract_path(goal)
        requires_permission = route in {'files', 'network', 'backup'}
        lower = title.lower()
        action = 'fetch' if route == 'network' else 'read'
        if any(token in lower for token in ['запис', 'созда', 'сохрани', 'write']):
            action = 'write'
        return {
            'id': f'step_{idx}',
            'title': title,
            'route': route,
            'target': target,
            'action': action,
            'requires_permission': requires_permission,
            'status': 'pending',
        }

    def _heuristic_plan(self, goal: str, mode: str) -> list[dict]:
        text = goal.lower().strip()
        file_name = self._extract_path(goal)
        url = self._extract_url(goal)

        if mode == 'backup' or any(token in text for token in ['резерв', 'backup']):
            raw = [
                'Проверить доступность данных для резервного копирования',
                'Создать резервную копию локальных данных',
                'Подготовить итоговый отчёт о резервном копировании',
            ]
        elif mode == 'sysadmin' or any(token in text for token in ['cpu', 'ram', 'систем', 'производительн', 'диск']):
            raw = [
                'Собрать показатели системы',
                'Проверить загрузку CPU, RAM и диска',
                'Подготовить итоговый отчёт по состоянию системы',
            ]
        elif mode == 'file' or any(token in text for token in ['файл', 'каталог', 'директор', 'папк', '.txt', '.md', '.json', '.csv', '.docx']):
            if any(token in text for token in ['создай', 'создать', 'сохрани', 'запиши', 'write', 'save']):
                target = file_name or 'notes.txt'
                raw = [
                    f'Проверить структуру workspace перед записью файла {target}',
                    f'Записать результат запроса в файл {target}',
                    f'Подтвердить пользователю сохранение файла {target}',
                ]
            elif any(token in text for token in ['прочитай', 'открой', 'read', 'show', 'покажи']) and file_name:
                raw = [
                    f'Проверить наличие файла {file_name} в workspace',
                    f'Прочитать файл {file_name}',
                    f'Подготовить краткое резюме содержимого файла {file_name}',
                ]
            else:
                raw = [
                    'Показать содержимое workspace',
                    'Проверить наличие релевантных файлов и каталогов',
                    'Подготовить ответ пользователю по файловой структуре',
                ]
        elif url or any(token in text for token in ['http', 'сайт', 'url', 'интернет']):
            target = url or 'указанный ресурс'
            raw = [
                f'Проверить параметры сетевого обращения к {target}',
                f'Выполнить сетевой запрос к {target}',
                f'Подготовить итоговый отчёт о сетевом запросе к {target}',
            ]
        else:
            general_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS['general'])
            raw = [
                f'Проанализировать запрос и цель: {goal}',
                f'Выбрать действие и инструмент для режима {mode}: {general_prompt}',
                'Подготовить итоговый ответ пользователю на основе результатов шагов',
            ]
        return [self._make_step(step, mode, idx + 1, goal) for idx, step in enumerate(raw)]

    def _extract_url(self, text: str) -> str | None:
        match = re.search(r'(https?://\S+)', text)
        return match.group(1) if match else None

    def _extract_path(self, text: str) -> str | None:
        match = re.search(r'([\w./\\-]+\.[\w]+)', text)
        return match.group(1) if match else None
