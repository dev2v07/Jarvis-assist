from __future__ import annotations
import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import API_HOST, API_PORT, CORS_ORIGINS, LOG_DIR, LOG_LEVEL, REQUEST_HISTORY_LIMIT, ensure_runtime_config
from models.schemas import (
    ChatAcceptedResponse,
    ChatRequest,
    HealthResponse,
    LLMSettingsResponse,
    LLMSettingsUpdate,
    PermissionResponse,
    PlanApprovalRequest,
    RequestStatusResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
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
from services.llm_service import llm_service
from services.state_store import SQLiteStateStore
from services.config_service import get_llm_settings, get_settings_bundle, save_llm_settings, test_llm_settings
from utils.logging_setup import configure_logging, get_logger

ensure_runtime_config()
configure_logging(LOG_DIR, LOG_LEVEL)
logger = get_logger('hel.app')
bus = MessageBus()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('application_starting', extra={'event': 'application_starting'})
    app.state.agent_task = asyncio.create_task(start_agents())
    await backup_agent.on_start()
    try:
        yield
    finally:
        logger.info('application_stopping', extra={'event': 'application_stopping'})
        app.state.agent_task.cancel()
        try:
            await app.state.agent_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title='Project Hel API', version='1.5.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=['*'], allow_headers=['*'])
app.pending_permissions = {}
app.pending_plans = {}
app.request_states = {}
app.state_store = SQLiteStateStore()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception('unhandled_exception', extra={'event': 'unhandled_exception', 'path': str(request.url.path)})
    return JSONResponse(status_code=500, content={'detail': 'Internal server error'})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning('validation_error', extra={'event': 'validation_error', 'path': str(request.url.path)})
    return JSONResponse(status_code=422, content={'detail': exc.errors()})


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

AGENTS = [main_agent, policy_manager, memory_agent, planner_agent, executor_agent, critic_agent, network_agent, file_agent, vision_agent, voice_agent, performance_agent, social_agent, game_coach_agent, backup_agent]


def save_state(state: dict):
    app.request_states[state['request_id']] = state
    app.state_store.upsert_request(state)


async def start_agents():
    await asyncio.gather(*(agent.run() for agent in AGENTS))


@app.get('/health', response_model=HealthResponse)
async def health():
    return HealthResponse(status='ok', agents=bus.registered_agents(), model_backend=llm_service.backend_name)


@app.get('/modes')
async def modes():
    return [{'key': key, **value} for key, value in MODES.items()]


@app.get('/requests')
async def list_requests(limit: int = 20):
    return app.state_store.list_recent_requests(limit=min(limit, REQUEST_HISTORY_LIMIT))


@app.get('/config/llm', response_model=LLMSettingsResponse)
async def get_config_llm():
    return LLMSettingsResponse(**get_llm_settings())


@app.post('/config/llm', response_model=LLMSettingsResponse)
async def update_config_llm(request: LLMSettingsUpdate):
    settings = save_llm_settings(request.model_dump())
    return LLMSettingsResponse(**get_llm_settings())


@app.get('/settings', response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(**get_settings_bundle())


@app.post('/settings', response_model=SettingsResponse)
async def update_settings(request: SettingsUpdateRequest):
    return SettingsResponse(**save_llm_settings(request.model_dump()))


@app.post('/settings/test')
async def settings_test(request: SettingsUpdateRequest):
    return await test_llm_settings(request.model_dump())


@app.post('/chat', response_model=ChatAcceptedResponse)
async def chat(request: ChatRequest):
    msg_id = str(uuid.uuid4())
    logger.info('chat_request_received', extra={'event': 'chat_request_received', 'request_id': msg_id, 'status': 'planning'})
    state = {
        'request_id': msg_id,
        'status': 'planning',
        'goal': request.message,
        'mode': request.mode,
        'events': [{'type': 'request_created', 'data': {'message': request.message, 'mode': request.mode}}],
        'plan': [],
        'current_step': None,
        'completed_steps': [],
        'result': None,
        'error': None,
        'permission_request': None,
        'artifacts': [],
    }
    save_state(state)
    await memory_agent.handle_message({'type': 'extract_facts', 'payload': {'user_message': request.message}})
    await bus.send('planner', {'id': msg_id, 'from': 'main', 'to': 'planner', 'type': 'create_plan', 'payload': {'goal': request.message, 'context': f'Режим: {request.mode}', 'original_msg_id': msg_id, 'mode': request.mode}})
    return ChatAcceptedResponse(request_id=msg_id, status='accepted')


@app.get('/requests/{request_id}', response_model=RequestStatusResponse)
async def request_status(request_id: str):
    state = app.request_states.get(request_id) or app.state_store.get_request(request_id)
    if not state:
        return RequestStatusResponse(request_id=request_id, status='not_found', goal='', mode='general', error='Request not found')
    return RequestStatusResponse(**state)


@app.post('/permission_response')
async def permission_response(request: PermissionResponse):
    payload = app.pending_permissions.pop(request.request_id, None)
    if payload and payload.get('original_msg_id') in app.request_states:
        state = app.request_states[payload['original_msg_id']]
        state['permission_request'] = None
        state['status'] = 'running' if request.allowed else 'failed'
        state['events'].append({'type': 'permission_resolved', 'data': {'allowed': request.allowed, 'request_id': request.request_id}})
        save_state(state)
    await bus.send('policy', {'id': str(uuid.uuid4()), 'from': 'main', 'to': 'policy', 'type': 'resolve_permission', 'payload': {'request_id': request.request_id, 'allowed': request.allowed}})
    return {'status': 'ok'}


@app.post('/plan_approval')
async def plan_approval(request: PlanApprovalRequest):
    payload = app.pending_plans.pop(request.original_msg_id, None)
    state = app.request_states.get(request.original_msg_id)
    if not payload:
        return {'status': 'not_found'}
    if state:
        state['events'].append({'type': 'plan_resolved', 'data': {'approved': request.approved}})
    if not request.approved:
        if state:
            state['status'] = 'completed'
            state['result'] = 'План отклонён пользователем.'
            save_state(state)
        return {'status': 'ok'}
    if state:
        state['status'] = 'running'
        save_state(state)
    await bus.send('planner', {'id': str(uuid.uuid4()), 'from': 'main', 'to': 'planner', 'type': 'plan_approved', 'payload': {'original_msg_id': request.original_msg_id, 'mode': state['mode'] if state else 'general'}})
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT, reload=False)
