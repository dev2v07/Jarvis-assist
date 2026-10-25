from __future__ import annotations
import asyncio
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import API_HOST, API_PORT, CORS_ORIGINS
from models.schemas import ChatRequest, ChatResponse, PermissionResponse, PlanApprovalRequest, HealthResponse
from core.message_bus import MessageBus
from core.modes import MODES
from agents.main_agent import MainAgent
from agents.policy_manager import PolicyManager
from agents.memory_agent import MemoryAgent
from agents.planner_agent import PlannerAgent
from agents.executor_agent import ExecutorAgent
from agents.critic_agent import CriticAgent
from agents.network_agent import NetworkAgent
from agents.file_agent import FileAgent
from agents.vision_agent import VisionAgent
from agents.voice_agent import VoiceAgent
from agents.performance_agent import PerformanceAgent
from agents.social_agent import SocialAgent
from agents.game_coach_agent import GameCoachAgent
from agents.backup_agent import BackupAgent

app = FastAPI(title='Project Hel API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.pending_permissions = {}
app.pending_plans = {}

bus = MessageBus()
main_agent = MainAgent(bus, app)
policy_manager = PolicyManager(bus, app)
memory_agent = MemoryAgent(bus)
planner_agent = PlannerAgent(bus)
executor_agent = ExecutorAgent(bus)
critic_agent = CriticAgent(bus)
network_agent = NetworkAgent(bus)
file_agent = FileAgent(bus)
vision_agent = VisionAgent(bus)
voice_agent = VoiceAgent(bus)
performance_agent = PerformanceAgent(bus)
social_agent = SocialAgent(bus)
game_coach_agent = GameCoachAgent(bus)
backup_agent = BackupAgent(bus)

AGENTS = [
    main_agent, policy_manager, memory_agent, planner_agent, executor_agent,
    critic_agent, network_agent, file_agent, vision_agent, voice_agent,
    performance_agent, social_agent, game_coach_agent, backup_agent,
]

async def start_agents():
    await asyncio.gather(*(agent.run() for agent in AGENTS))

@app.on_event('startup')
async def startup_event():
    asyncio.create_task(start_agents())
    await backup_agent.on_start()

@app.get('/health', response_model=HealthResponse)
async def health():
    return HealthResponse(status='ok', agents=bus.registered_agents(), model_backend='local_stub')

@app.get('/modes')
async def modes():
    return [{'key': key, **value} for key, value in MODES.items()]

@app.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest):
    msg_id = str(uuid.uuid4())
    future = asyncio.get_running_loop().create_future()
    main_agent.pending[msg_id] = future
    await memory_agent.handle_message({'type': 'extract_facts', 'payload': {'user_message': request.message}})
    await bus.send('planner', {
        'id': msg_id,
        'from': 'main',
        'to': 'planner',
        'type': 'create_plan',
        'payload': {'goal': request.message, 'context': f'Режим: {request.mode}', 'original_msg_id': msg_id},
    })
    try:
        result = await asyncio.wait_for(future, timeout=60.0)
        return ChatResponse(response=result, request_id=msg_id)
    except asyncio.TimeoutError:
        main_agent.pending.pop(msg_id, None)
        raise HTTPException(status_code=504, detail='Timeout')

@app.post('/permission_response')
async def permission_response(request: PermissionResponse):
    app.pending_permissions.pop(request.request_id, None)
    await bus.send('policy', {
        'id': str(uuid.uuid4()),
        'from': 'main',
        'to': 'policy',
        'type': 'resolve_permission',
        'payload': {'request_id': request.request_id, 'allowed': request.allowed},
    })
    return {'status': 'ok'}

@app.post('/plan_approval')
async def plan_approval(request: PlanApprovalRequest):
    payload = app.pending_plans.pop(request.original_msg_id, None)
    if not payload:
        return {'status': 'not_found'}
    if not request.approved:
        future = main_agent.pending.pop(request.original_msg_id, None)
        if future and not future.done():
            future.set_result('План отклонён пользователем.')
        return {'status': 'ok'}
    await bus.send('planner', {
        'id': str(uuid.uuid4()),
        'from': 'main',
        'to': 'planner',
        'type': 'plan_approved',
        'payload': {'original_msg_id': request.original_msg_id, 'mode': 'general'},
    })
    return {'status': 'ok'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT, reload=False)
