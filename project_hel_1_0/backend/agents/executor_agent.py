from __future__ import annotations
import re
import uuid
from pathlib import Path

from core.agent_base import Agent
from services.tool_router import pick_route
from config import WORKSPACE_DIR
from utils.logging_setup import get_logger

logger = get_logger('hel.executor')


class ExecutorAgent(Agent):
    def __init__(self, bus):
        super().__init__('executor', bus)
        self.sessions: dict[str, dict] = {}

    async def handle_message(self, msg):
        msg_type = msg.get('type')
        payload = msg.get('payload', {})

        if msg_type == 'execute_plan':
            request_id = payload['original_msg_id']
            self.sessions[request_id] = {
                'goal': payload.get('goal', ''),
                'mode': payload.get('mode', 'general'),
                'steps': payload.get('steps', []),
                'index': 0,
                'results': [],
                'waiting_permission': None,
            }
            logger.info('execution_started', extra={'event': 'execution_started', 'request_id': request_id, 'status': 'running'})
            await self._run_next_step(request_id)

        elif msg_type == 'tool_result':
            request_id = payload['original_msg_id']
            session = self.sessions.get(request_id)
            if not session:
                return
            step = session['steps'][session['index']]
            session['results'].append({'step': step, 'result': payload['result'], 'artifact': payload.get('artifact')})
            await self.bus.send('main', {
                'id': str(uuid.uuid4()),
                'from': self.name,
                'to': 'main',
                'type': 'step_finished',
                'payload': {
                    'original_msg_id': request_id,
                    'step': step.get('title', str(step)),
                    'result': payload['result'],
                    'artifact': payload.get('artifact'),
                },
            })
            session['index'] += 1
            session['waiting_permission'] = None
            await self._run_next_step(request_id)

        elif msg_type == 'permission_result':
            request_id = payload.get('original_msg_id')
            session = self.sessions.get(request_id)
            if not session:
                return
            pending = session.get('waiting_permission')
            if not pending or pending['request_id'] != payload['request_id']:
                return
            if not payload.get('allowed'):
                self.sessions.pop(request_id, None)
                await self.bus.send('main', {
                    'id': str(uuid.uuid4()),
                    'from': self.name,
                    'to': 'main',
                    'type': 'request_failed',
                    'payload': {
                        'original_msg_id': request_id,
                        'error': f"Пользователь отклонил действие: {pending['reason']}",
                    },
                })
                return
            session['waiting_permission'] = None
            await self._dispatch_step(request_id, pending['step'])

    async def _run_next_step(self, request_id: str):
        session = self.sessions.get(request_id)
        if not session:
            return
        if session['index'] >= len(session['steps']):
            results = session['results']
            result_text = '\n\n'.join([str(item['result']) for item in results if item.get('result')]) or 'Задача выполнена.'
            logger.info('execution_completed', extra={'event': 'execution_completed', 'request_id': request_id, 'status': 'completed'})
            await self.bus.send('critic', {
                'id': str(uuid.uuid4()),
                'from': self.name,
                'to': 'critic',
                'type': 'review_result',
                'payload': {
                    'original_msg_id': request_id,
                    'result': result_text,
                    'goal': session.get('goal', ''),
                    'artifacts': [r.get('artifact') for r in results if r.get('artifact')],
                },
            })
            self.sessions.pop(request_id, None)
            return

        step = session['steps'][session['index']]
        await self.bus.send('main', {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': 'main',
            'type': 'step_started',
            'payload': {
                'original_msg_id': request_id,
                'step': step.get('title', str(step)),
                'index': session['index'] + 1,
                'total': len(session['steps']),
            },
        })

        if step.get('requires_permission'):
            pending = self._build_permission(request_id, step, session)
            session['waiting_permission'] = pending
            await self.bus.send('policy', {
                'id': str(uuid.uuid4()),
                'from': self.name,
                'to': 'policy',
                'type': 'check_permission',
                'payload': pending,
            })
            return

        await self._dispatch_step(request_id, step)

    async def _dispatch_step(self, request_id: str, step: dict):
        session = self.sessions.get(request_id)
        if not session:
            return
        route = step.get('route') or pick_route(step.get('title', ''), session['mode'])
        target = step.get('target')
        destination = {
            'files': 'file',
            'network': 'network',
            'system': 'performance',
            'vision': 'vision',
            'voice': 'voice',
            'backup': 'backup',
        }.get(route, 'performance')
        logger.info('dispatch_tool', extra={'event': 'dispatch_tool', 'request_id': request_id, 'step': step.get('title', ''), 'agent': destination})
        await self.bus.send(destination, {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': destination,
            'type': 'tool_request',
            'payload': {
                'original_msg_id': request_id,
                'step': step.get('title', ''),
                'step_meta': step,
                'goal': session.get('goal', ''),
                'mode': session.get('mode', 'general'),
                'target': target,
            },
        })

    def _build_permission(self, request_id: str, step: dict, session: dict) -> dict:
        route = step.get('route') or pick_route(step.get('title', ''), session['mode'])
        target = step.get('target')
        if route == 'files':
            raw_target = target or self._extract_path(step.get('title', ''))
            if raw_target:
                target = str((Path(WORKSPACE_DIR) / raw_target).resolve()) if not str(raw_target).startswith(str(WORKSPACE_DIR)) else str(Path(raw_target).resolve())
            else:
                target = str(Path(WORKSPACE_DIR).resolve())
            action_type = 'file_write' if step.get('action') == 'write' else 'file_read'
            reason = f'Доступ к файловой системе: {target}'
        elif route == 'network':
            target = target or self._extract_url(step.get('title', '')) or step.get('title')
            action_type = 'network'
            reason = f'Сетевой запрос: {target}'
        elif route == 'backup':
            target = str(WORKSPACE_DIR)
            action_type = 'backup'
            reason = 'Создание резервной копии локальных данных'
        else:
            action_type = 'general'
            target = target or step.get('title')
            reason = f'Выполнить действие: {step.get("title", "")}'
        return {
            'request_id': str(uuid.uuid4()),
            'original_msg_id': request_id,
            'action_type': action_type,
            'target': target,
            'reason': reason,
            'step': step,
        }

    def _extract_url(self, text: str) -> str | None:
        match = re.search(r'(https?://\S+)', text)
        return match.group(1) if match else None

    def _extract_path(self, text: str) -> str | None:
        match = re.search(r'([\w./\\-]+\.[\w]+)', text)
        return match.group(1) if match else None
