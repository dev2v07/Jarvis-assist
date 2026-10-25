import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient
import main


def run_request(client, message, mode='general', auto_allow=True):
    response = client.post('/chat', json={'message': message, 'mode': mode})
    response.raise_for_status()
    request_id = response.json()['request_id']

    for _ in range(60):
        state = client.get(f'/requests/{request_id}').json()
        if state['status'] == 'awaiting_plan_approval':
            client.post('/plan_approval', json={'original_msg_id': request_id, 'approved': True})
        elif state['status'] == 'awaiting_permission' and state.get('permission_request') and auto_allow:
            client.post('/permission_response', json={
                'request_id': state['permission_request']['request_id'],
                'allowed': True,
            })
        elif state['status'] in ('completed', 'failed'):
            return state
        time.sleep(0.2)
    raise RuntimeError(f'Timeout waiting for request {request_id}')


with TestClient(main.app) as client:
    system_state = run_request(client, 'Покажи состояние системы', 'sysadmin')
    assert system_state['status'] == 'completed', system_state

    create_state = run_request(client, 'Создай файл notes.txt: привет мир', 'file')
    assert create_state['status'] == 'completed', create_state

    read_state = run_request(client, 'Прочитай файл notes.txt', 'file')
    assert read_state['status'] == 'completed', read_state
    assert 'привет мир' in read_state['result'], read_state['result']

print('Smoke test passed.')
