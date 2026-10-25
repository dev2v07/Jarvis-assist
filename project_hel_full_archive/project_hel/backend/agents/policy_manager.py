from __future__ import annotations
import asyncio
import os
import uuid
from typing import Dict, Set
from core.agent_base import Agent
from config import WORKSPACE_DIR, WINDOWS_SYSTEM_PATHS

class PolicyManager(Agent):
    def __init__(self, bus, app):
        super().__init__('policy', bus)
        self.app = app
        self.allowed_domains: Set[str] = set()
        self.allowed_write_paths: Set[str] = set()
        self.pending_requests: Dict[str, asyncio.Future] = {}

    def is_system_path(self, path: str) -> bool:
        abs_path = os.path.abspath(path).lower()
        return any(abs_path.startswith(item.lower()) for item in WINDOWS_SYSTEM_PATHS)

    async def handle_message(self, msg):
        msg_type = msg.get('type')
        payload = msg.get('payload', {})
        if msg_type == 'check_file_write':
            path = os.path.abspath(payload['path'])
            request_id = payload.get('request_id', str(uuid.uuid4()))
            allowed = (path.startswith(str(WORKSPACE_DIR)) or path in self.allowed_write_paths) and not self.is_system_path(path)
            if not allowed:
                await self.bus.send('main', {
                    'id': str(uuid.uuid4()),
                    'from': self.name,
                    'to': 'main',
                    'type': 'permission_request',
                    'payload': {
                        'request_id': request_id,
                        'type': 'file_write',
                        'target': path,
                        'reason': payload.get('reason', ''),
                    },
                })
            else:
                await self._reply(msg['from'], request_id, True, path)
        elif msg_type == 'resolve_permission':
            request_id = payload['request_id']
            future = self.pending_requests.pop(request_id, None)
            if future and not future.done():
                future.set_result(payload['allowed'])

    async def _reply(self, to: str, request_id: str, allowed: bool, target: str):
        await self.bus.send(to, {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': to,
            'type': 'permission_result',
            'payload': {'request_id': request_id, 'allowed': allowed, 'target': target},
        })
