from __future__ import annotations

from core.agent_base import Agent
from utils.logging_setup import get_logger

logger = get_logger('hel.main_agent')


class MainAgent(Agent):
    def __init__(self, bus, app):
        super().__init__('main', bus)
        self.app = app

    def _state(self, request_id: str):
        return self.app.request_states.get(request_id) or self.app.state_store.get_request(request_id)

    def _save_state(self, state: dict):
        self.app.request_states[state['request_id']] = state
        self.app.state_store.upsert_request(state)

    def _push_event(self, request_id: str, event_type: str, data=None):
        state = self._state(request_id)
        if not state:
            return
        state['events'].append({'type': event_type, 'data': data or {}})
        self._save_state(state)

    async def handle_message(self, msg):
        msg_type = msg.get('type')
        payload = msg.get('payload', {})
        request_id = payload.get('original_msg_id') or payload.get('request_id')

        if msg_type == 'plan_approval':
            original_id = payload['original_msg_id']
            self.app.pending_plans[original_id] = payload
            state = self._state(original_id)
            if state:
                state['status'] = 'awaiting_plan_approval'
                state['plan'] = payload.get('steps', [])
                self._save_state(state)
                self._push_event(original_id, 'plan_requested', {'goal': payload.get('goal'), 'steps': payload.get('steps', [])})
                logger.info('plan_requested', extra={'event': 'plan_requested', 'request_id': original_id, 'status': state['status']})

        elif msg_type == 'permission_request':
            request_id = payload['request_id']
            self.app.pending_permissions[request_id] = payload
            original_id = payload.get('original_msg_id')
            state = self._state(original_id)
            if state:
                state['status'] = 'awaiting_permission'
                state['permission_request'] = payload
                self._save_state(state)
                self._push_event(original_id, 'permission_requested', payload)
                logger.info('permission_requested', extra={'event': 'permission_requested', 'request_id': original_id, 'status': state['status']})

        elif msg_type == 'step_started':
            state = self._state(request_id)
            if state:
                state['status'] = 'running'
                state['current_step'] = payload.get('step')
                self._save_state(state)
                self._push_event(request_id, 'step_started', {'step': payload.get('step'), 'index': payload.get('index'), 'total': payload.get('total')})
                logger.info('step_started', extra={'event': 'step_started', 'request_id': request_id, 'step': payload.get('step'), 'status': state['status']})

        elif msg_type == 'step_finished':
            state = self._state(request_id)
            if state:
                state['completed_steps'].append({'step': payload.get('step', ''), 'result': payload.get('result', '')})
                state['current_step'] = None
                self._save_state(state)
                self._push_event(request_id, 'step_finished', {'step': payload.get('step'), 'result': payload.get('result')})
                logger.info('step_finished', extra={'event': 'step_finished', 'request_id': request_id, 'step': payload.get('step'), 'status': state['status']})

        elif msg_type == 'final_response':
            original_id = payload['original_msg_id']
            state = self._state(original_id)
            if state:
                state['status'] = 'completed'
                state['result'] = payload['result']
                state['current_step'] = None
                state['permission_request'] = None
                self._save_state(state)
                self._push_event(original_id, 'final_response', {'result': payload['result']})
                logger.info('final_response', extra={'event': 'final_response', 'request_id': original_id, 'status': state['status']})

        elif msg_type == 'request_failed':
            state = self._state(request_id)
            if state:
                state['status'] = 'failed'
                state['error'] = payload.get('error', 'Unknown error')
                state['current_step'] = None
                self._save_state(state)
                self._push_event(request_id, 'request_failed', {'error': state['error']})
                logger.error('request_failed', extra={'event': 'request_failed', 'request_id': request_id, 'status': state['status']})
