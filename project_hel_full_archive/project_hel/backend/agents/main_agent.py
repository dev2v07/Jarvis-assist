from __future__ import annotations
from core.agent_base import Agent

class MainAgent(Agent):
    def __init__(self, bus, app):
        super().__init__('main', bus)
        self.app = app
        self.pending: dict[str, object] = {}

    async def handle_message(self, msg):
        msg_type = msg.get('type')
        payload = msg.get('payload', {})
        if msg_type == 'plan_approval':
            original_id = payload['original_msg_id']
            self.app.pending_plans[original_id] = payload
        elif msg_type == 'permission_request':
            request_id = payload['request_id']
            self.app.pending_permissions[request_id] = payload
        elif msg_type == 'final_response':
            original_id = payload['original_msg_id']
            future = self.pending.pop(original_id, None)
            if future and not future.done():
                future.set_result(payload['result'])
