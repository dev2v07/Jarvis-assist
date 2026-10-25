from __future__ import annotations
import os
import uuid
from typing import Dict, Set
from urllib.parse import urlparse
from core.agent_base import Agent
from config import SAFE_NETWORK_DOMAINS, WINDOWS_SYSTEM_PATHS, WORKSPACE_DIR


class PolicyManager(Agent):
    def __init__(self, bus, app):
        super().__init__('policy', bus)
        self.app = app
        self.allowed_domains: Set[str] = set(SAFE_NETWORK_DOMAINS)
        self.allowed_write_paths: Set[str] = {str(WORKSPACE_DIR.resolve())}
        self.pending_requests: Dict[str, dict] = {}

    def is_system_path(self, path: str) -> bool:
        abs_path = os.path.abspath(path).lower()
        return any(abs_path.startswith(item.lower()) for item in WINDOWS_SYSTEM_PATHS)

    def _workspace_allowed(self, path: str) -> bool:
        workspace = str(WORKSPACE_DIR.resolve())
        try:
            resolved = str(os.path.abspath(path))
            return resolved.startswith(workspace)
        except Exception:
            return False

    async def handle_message(self, msg):
        msg_type = msg.get('type')
        payload = msg.get('payload', {})

        if msg_type == 'check_permission':
            request_id = payload.get('request_id', str(uuid.uuid4()))
            action_type = payload.get('action_type', 'generic')
            target = payload.get('target', '')
            original_msg_id = payload.get('original_msg_id')
            allowed = self._is_allowed(action_type, target)
            if allowed:
                await self._reply(msg['from'], request_id, True, target, action_type, original_msg_id)
                return

            self.pending_requests[request_id] = {
                'reply_to': msg['from'],
                'target': target,
                'action_type': action_type,
                'original_msg_id': original_msg_id,
            }
            await self.bus.send('main', {
                'id': str(uuid.uuid4()),
                'from': self.name,
                'to': 'main',
                'type': 'permission_request',
                'payload': {
                    'request_id': request_id,
                    'type': action_type,
                    'target': target,
                    'reason': payload.get('reason', 'Требуется подтверждение действия.'),
                    'original_msg_id': original_msg_id,
                },
            })

        elif msg_type == 'resolve_permission':
            request_id = payload['request_id']
            pending = self.pending_requests.pop(request_id, None)
            if not pending:
                return
            allowed = bool(payload['allowed'])
            if allowed:
                self._remember_allow(pending['action_type'], pending['target'])
            await self._reply(
                pending['reply_to'],
                request_id,
                allowed,
                pending['target'],
                pending['action_type'],
                pending['original_msg_id'],
            )

    def _remember_allow(self, action_type: str, target: str):
        if action_type in {'file_read', 'file_write', 'backup'} and target:
            self.allowed_write_paths.add(str(os.path.abspath(target)))
        elif action_type == 'network' and target:
            parsed = urlparse(target if '://' in target else f'https://{target}')
            if parsed.netloc:
                self.allowed_domains.add(parsed.netloc)

    def _is_allowed(self, action_type: str, target: str) -> bool:
        if action_type in {'file_read', 'file_write', 'backup'}:
            return bool(target) and self._workspace_allowed(target) and not self.is_system_path(target)
        if action_type == 'network':
            parsed = urlparse(target if '://' in target else f'https://{target}')
            return parsed.netloc in self.allowed_domains
        return True

    async def _reply(self, to: str, request_id: str, allowed: bool, target: str, action_type: str, original_msg_id: str | None):
        await self.bus.send(to, {
            'id': str(uuid.uuid4()),
            'from': self.name,
            'to': to,
            'type': 'permission_result',
            'payload': {
                'request_id': request_id,
                'allowed': allowed,
                'target': target,
                'action_type': action_type,
                'original_msg_id': original_msg_id,
            },
        })
