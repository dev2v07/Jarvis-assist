import asyncio
import uuid
import uvicorn
import os
import requests
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from urllib.parse import quote
from pydantic import BaseModel, Field

# -----------------------------
# CORE
# -----------------------------

from core.message_bus import MessageBus

# -----------------------------
# AGENTS
# -----------------------------

from agents.main_agent import MainAgent
from agents.planner_agent import Planner
from agents.executor_agent import ExecutorAgent
from agents.critic_agent import CriticAgent

from agents.file_agent import FileAgent
from agents.network_agent import NetworkAgent
from agents.web_agent import WebAgent
from agents.vision_agent import VisionAgent
try:
    from agents.voice_agent import VoiceAgent
except Exception as exc:
    # Голосовой стек не должен блокировать запуск текстового ядра.
    VoiceAgent = None
    print(f"Voice agent disabled: {exc}")
from agents.memory_agent import MemoryAgent
from agents.backup_agent import BackupAgent
from agents.performance_agent import PerformanceAgent
from agents.game_coach_agent import GameCoachAgent
from agents.social_agent import SocialAgent

from agents.policy_manager import PolicyManager
from agents.selfcheck_agent import SelfCheckAgent

# -----------------------------
# SERVICES
# -----------------------------

from health import system_health
from startup_check import check
from utils.logging_setup import configure_logging

# -----------------------------
# CONFIG
# -----------------------------

from config import API_PORT, LOG_DIR, UPLOAD_DIR, update_runtime_config, read_runtime_config
from services.chat_store import ChatStore
from services.runtime_service import runtime_registry
from services.voice_runtime import VoiceRuntime
from services.voice_session_manager import VoiceSessionManager
from voice_engine.tts import select_voice_model, voice_models_status
from services.app_server import AppServer
from services.device_capabilities import device_capabilities
from services.filesystem_service import FileSystemService
from services.application_service import ApplicationService
from services.local_response_service import LocalResponseService
from services.offline_knowledge_service import OfflineKnowledgeService
from services.knowledge_index_service import KnowledgeIndexService
from services.knowledge_search_service import KnowledgeSearchService
from services.programming_mentor_service import ProgrammingMentorService
from services.coding_sandbox_service import CodingSandboxService
from services.music_intelligence_service import MusicIntelligenceService
from services.music_production_service import MusicProductionService
from services.voice_production_service import VoiceProductionService
from services.guitar_encyclopedia_service import GuitarEncyclopediaService
from services.psychology_service import PsychologyService
from services.literature_service import LiteratureService
from services.daw_control_service import DawControlService
from services.mixing_service import MixingService
from services.config_service import get_settings_bundle, save_llm_settings, test_llm_settings
from services.llm_service import LocalLLMService
from utils.tooling import backup_data

# -----------------------------
# APP
# -----------------------------

app = FastAPI(title="Jarvis Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        f"http://127.0.0.1:{API_PORT}",
        "http://localhost",
        "http://localhost:8000",
        f"http://localhost:{API_PORT}",
        # The PySide6 QWebEngine chat is loaded from a local file and sends
        # this explicit origin on its fetch requests. Keep it scoped to the
        # local desktop UI; do not replace the allow-list with a wildcard.
        "file://",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

print("Startup check:", check())

# -----------------------------
# MESSAGE BUS
# -----------------------------

bus = MessageBus()
chat_store = ChatStore()
app_server = AppServer(chat_store, runtime_registry)
voice_sessions = VoiceSessionManager()
filesystem_service = FileSystemService(Path(__file__).resolve().parent)
application_service = ApplicationService(Path(__file__).resolve().parent)
local_response_service = LocalResponseService(Path(__file__).resolve().parent)
offline_knowledge_service = OfflineKnowledgeService(Path(__file__).resolve().parent)
knowledge_index_service = KnowledgeIndexService(Path(__file__).resolve().parent)
knowledge_search_service = KnowledgeSearchService(Path(__file__).resolve().parent, local_response_service)
voice_runtime = VoiceRuntime(
    Path(__file__).resolve().parent,
    chat_store,
    voice_sessions,
    knowledge_search_service=knowledge_search_service,
)
programming_mentor_service = ProgrammingMentorService(Path(__file__).resolve().parent)
coding_sandbox_service = CodingSandboxService(Path(__file__).resolve().parent)
music_intelligence_service = MusicIntelligenceService(Path(__file__).resolve().parent)
music_production_service = MusicProductionService(Path(__file__).resolve().parent)
voice_production_service = VoiceProductionService(Path(__file__).resolve().parent)
guitar_encyclopedia_service = GuitarEncyclopediaService(Path(__file__).resolve().parent)
psychology_service = PsychologyService(Path(__file__).resolve().parent)
literature_service = LiteratureService(Path(__file__).resolve().parent)
daw_control_service = DawControlService(Path(__file__).resolve().parent)
mixing_service = MixingService()
active_chat_tasks: dict[str, asyncio.Task] = {}

# -----------------------------
# AGENTS
# -----------------------------

main_agent = MainAgent(bus, app)

planner = Planner(bus)
executor = ExecutorAgent(bus)
critic = CriticAgent(bus)

file_agent = FileAgent(bus)
network_agent = NetworkAgent(bus)
web_agent = WebAgent(bus)
vision_agent = VisionAgent(bus)
voice_agent = VoiceAgent(bus) if VoiceAgent else None
memory_agent = MemoryAgent(bus)
backup_agent = BackupAgent(bus)
performance_agent = PerformanceAgent(bus)
game_agent = GameCoachAgent(bus)
social_agent = SocialAgent(bus)

policy_manager = PolicyManager(bus, app)
selfcheck_agent = SelfCheckAgent(bus)

agents = [
    main_agent,
    planner,
    executor,
    critic,
    file_agent,
    network_agent,
    web_agent,
    vision_agent,
    *([voice_agent] if voice_agent else []),
    memory_agent,
    backup_agent,
    performance_agent,
    game_agent,
    social_agent,
    policy_manager,
    selfcheck_agent,
]

# -----------------------------
# START AGENTS
# -----------------------------


async def start_agents():

    for agent in agents:
        # Agent.start() переводит агент в состояние _running=True.
        # Прямой вызов run() оставлял цикл завершённым сразу после старта.
        agent.start()


@app.on_event("startup")
async def startup_event():

    configure_logging(LOG_DIR)

    # Keep the selected local model warm so the first free-form question does
    # not pay the cold-start cost. The warmup is one bounded request and does
    # not write to ChatStore or trigger the voice runtime.
    if os.getenv("JARVIS_OLLAMA_WARMUP", "true").strip().lower() not in {"0", "false", "no", "off"}:
        warmup = await LocalLLMService().warmup_ollama()
        print(
            "Ollama warmup:",
            warmup.get("status"),
            warmup.get("model", ""),
            warmup.get("error_type", ""),
        )

    await start_agents()

    print("Jarvis agents started")


@app.on_event("shutdown")
async def shutdown_event():
    """Release voice and agent tasks before the backend process exits."""

    voice_runtime.stop()
    for agent in reversed(agents):
        try:
            await agent.stop()
        except Exception as exc:
            print(f"Shutdown warning for {agent.name}: {exc}")
    print("Jarvis agents stopped")


# -----------------------------
# REQUEST MODEL
# -----------------------------


class ChatRequest(BaseModel):

    message: str
    attachments: list[dict] = Field(default_factory=list)
    chat_id: str = "default"
    reply_to: str | None = None
    turn_id: str | None = None
    custom_instructions: str = ""
    preferred_address: str = ""
    chat_system_prompt: str = ""


class HardwareSettings(BaseModel):
    audio_input_device: int = -1
    video_input_device: int = 0


class RuntimeContextRequest(BaseModel):
    session_id: str
    client: str = "desktop"
    platform: str = "windows"
    mode: str = "general"
    locale: str = "ru-RU"
    metadata: dict = {}


class RuntimeEventRequest(BaseModel):
    event_type: str
    source: str
    request_id: str | None = None
    payload: dict = Field(default_factory=dict)


class LLMSettingsRequest(BaseModel):
    provider: str = "ollama"
    openai_base_url: str = ""
    openai_model: str = ""
    openai_api_key: str | None = None
    deepseek_base_url: str = ""
    deepseek_model: str = ""
    deepseek_api_key: str | None = None
    ollama_base_url: str = ""
    ollama_model: str = ""
    ollama_think: str = "false"
    codex_base_url: str = ""
    codex_model: str = ""
    codex_api_key: str | None = None
    claude_base_url: str = ""
    claude_model: str = ""
    claude_api_key: str | None = None
    freellmapi_base_url: str = ""
    freellmapi_model: str = ""
    freellmapi_api_key: str | None = None
    llm_request_timeout: int = 45
    llm_max_retries: int = 2


class MentorProgressRequest(BaseModel):
    completed: bool = False
    score: int = 0
    note: str = ""


class MentorExerciseRequest(BaseModel):
    code: str
    timeout: int = 8


class SandboxRunRequest(BaseModel):
    project: str
    code: str
    timeout: int = 8


class CodingProjectRequest(BaseModel):
    project: str
    files: dict[str, str]
    run_tests: bool = True


class DawActionRequest(BaseModel):
    action: str
    daw: str = ""
    project_path: str = ""
    confirmed: bool = False


class DawSnapshotRequest(BaseModel):
    project_path: str
    snapshot_name: str = "checkpoint"
    confirmed: bool = False


@app.get("/settings/llm")
def llm_settings():
    return get_settings_bundle()


@app.post("/settings/llm/test")
async def llm_settings_test(payload: LLMSettingsRequest):
    return await test_llm_settings(payload.model_dump())


@app.post("/settings/llm")
def llm_settings_save(payload: LLMSettingsRequest):
    return save_llm_settings(payload.model_dump(exclude_none=True))


@app.get("/settings/llm/models")
def llm_models(provider: str = "ollama", base_url: str = "", api_key: str = ""):
    """Return models from providers that expose a standard model catalogue."""
    provider = provider.strip().lower().replace("-", "_")
    try:
        # Keep persisted credentials server-side. The UI only receives a mask,
        # so an empty api_key here means "use the already saved profile key".
        if not api_key and provider in {"openai", "openai_compatible", "deepseek", "freellmapi"}:
            runtime = read_runtime_config(mask_secrets=False)
            key_name = {
                "openai": "HEL_OPENAI_API_KEY",
                "openai_compatible": "HEL_OPENAI_API_KEY",
                "deepseek": "HEL_DEEPSEEK_API_KEY",
                "freellmapi": "HEL_FREELLMAPI_API_KEY",
            }[provider]
            api_key = str(runtime.get(key_name) or "").strip()
        if provider == "ollama":
            url = (base_url or "http://127.0.0.1:11434").rstrip("/") + "/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return {"ok": True, "models": [item.get("name") for item in data.get("models", []) if item.get("name")]}
        if provider in {"openai", "openai_compatible", "deepseek", "freellmapi"} and base_url and api_key:
            response = requests.get(
                base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=8
            )
            response.raise_for_status()
            data = response.json()
            return {"ok": True, "models": [item.get("id") for item in data.get("data", []) if item.get("id")]}
        return {"ok": False, "models": [], "message": "Для этого провайдера каталог моделей не подключён."}
    except (requests.RequestException, ValueError, TypeError):
        return {"ok": False, "models": [], "message": "Не удалось получить список моделей."}


@app.get("/chat/sessions")
def chat_sessions(include_archived: bool = False):
    return {"sessions": chat_store.list_sessions(include_archived=include_archived)}


class ChatSessionRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None


@app.post("/chat/sessions")
def create_chat_session(payload: ChatSessionRequest):
    return chat_store.create_session(payload.title)


@app.patch("/chat/sessions/{chat_id}")
def rename_chat_session(chat_id: str, payload: ChatSessionRequest):
    session = chat_store.rename_session(chat_id, payload.title or "Новый чат")
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@app.post("/chat/sessions/{chat_id}/pin")
def toggle_chat_session_pin(chat_id: str):
    try:
        session = chat_store.toggle_session_pin(chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@app.post("/chat/sessions/{chat_id}/archive")
def toggle_chat_session_archive(chat_id: str):
    session = chat_store.archive_session(chat_id)
    if not session:
        raise HTTPException(status_code=400, detail="Default or missing chat cannot be archived")
    return session


@app.delete("/chat/sessions/{chat_id}")
def delete_chat_session(chat_id: str):
    if not chat_store.delete_session(chat_id):
        raise HTTPException(status_code=400, detail="Default or missing chat cannot be deleted")
    return {"ok": True, "chat_id": chat_id}


@app.post("/hardware/settings")
def save_hardware_settings(settings: HardwareSettings):
    """Persist physical audio/video device selections for voice and vision modules."""
    updates = {
        "JARVIS_MICROPHONE_INDEX": str(settings.audio_input_device),
        "JARVIS_CAMERA_INDEX": str(settings.video_input_device),
    }
    update_runtime_config(updates)
    os.environ.update(updates)
    voice_runtime.set_device(settings.audio_input_device)
    return {"ok": True, **updates}


class VoiceStartRequest(BaseModel):
    microphone_index: int = -1
    microphone_enabled: bool = True
    source: str = "widget"
    chat_id: str | None = None
    replace: bool = False


class VoiceMicrophoneRequest(BaseModel):
    enabled: bool = True


class VoiceModelRequest(BaseModel):
    model_id: str


@app.post("/voice/start")
def voice_start(req: VoiceStartRequest):
    source = str(req.source or "widget").lower()
    chat_id = str(req.chat_id or "")
    if source == "widget" and not chat_id:
        created = chat_store.create_session("Голосовой разговор")
        chat_id = str(created.get("id"))
    elif source == "chat":
        if not chat_id or not chat_store.get_session(chat_id):
            raise HTTPException(status_code=404, detail="Chat session not found")
    active = voice_sessions.active
    if active and not req.replace:
        if active.get("source") == source and active.get("chat_id") == chat_id and voice_runtime.enabled:
            result = voice_runtime.status()
            result["voice_session"] = active
            return result
        raise HTTPException(status_code=409, detail="Another voice session is active")
    if active:
        voice_runtime.stop()
    try:
        session = voice_sessions.start(source=source, chat_id=chat_id, replace=False)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    voice_runtime.set_device(req.microphone_index)
    try:
        result = voice_runtime.start()
        result = voice_runtime.set_microphone_enabled(req.microphone_enabled)
    except Exception:
        voice_sessions.stop(session_id=session["session_id"])
        raise
    result["voice_session"] = session
    return result


@app.post("/voice/microphone")
def voice_microphone(req: VoiceMicrophoneRequest):
    return voice_runtime.set_microphone_enabled(req.enabled)


@app.post("/voice/stop")
def voice_stop():
    result = voice_runtime.stop()
    result["voice_session"] = voice_sessions.status()
    return result


@app.post("/voice/session/start")
def voice_session_start(req: VoiceStartRequest):
    req.source = "chat"
    return voice_start(req)


@app.post("/voice/session/stop")
def voice_session_stop():
    return voice_stop()


@app.get("/voice/status")
def voice_status():
    result = voice_runtime.status()
    result["voice_model"] = voice_models_status()
    result["voice_session"] = voice_sessions.status()
    return result


@app.get("/voice/models")
def voice_models():
    return voice_models_status()


@app.get("/voice/library")
def voice_library_status():
    return local_response_service.summary()


@app.get("/voice/knowledge")
def voice_knowledge_status():
    """Report the separate offline-knowledge catalog without exposing answers."""
    return offline_knowledge_service.summary()


@app.get("/knowledge/index")
def knowledge_index_status():
    """Report the read-only Knowledge 3.0 foundation index."""
    return knowledge_index_service.summary()


@app.get("/knowledge/integrity")
def knowledge_integrity():
    return knowledge_index_service.integrity()


@app.get("/knowledge/search")
def knowledge_search(query: str, limit: int = 20):
    """Search verified local knowledge, programming lessons and local music metadata."""
    return {"query": query, "results": knowledge_search_service.search(query, limit)}


@app.get("/knowledge/answer")
def knowledge_answer(query: str):
    """Resolve a local answer and expose a linked WAV when one is ready."""
    return {"query": query, "answer": knowledge_search_service.answer(query)}


@app.get("/knowledge/catalog")
def knowledge_catalog(offset: int = 0, limit: int = 50, kind: str = "", status: str = ""):
    catalog = knowledge_search_service.catalog()
    rows = catalog["records"]
    if kind:
        rows = [row for row in rows if row["kind"] == kind]
    if status:
        rows = [row for row in rows if row["content_status"] == status]
    start = max(0, int(offset))
    count = max(1, min(int(limit), 100))
    return {"total": len(rows), "offset": start, "limit": count,
            "collisions": catalog["collisions"], "records": rows[start:start + count]}


@app.get("/knowledge/items/{canonical_id}")
def knowledge_item(canonical_id: str):
    item = knowledge_search_service.get(canonical_id)
    if item is None:
        raise HTTPException(status_code=404, detail="knowledge item not found")
    return item


@app.get("/knowledge/context")
def knowledge_context(query: str, limit: int = 6):
    return knowledge_search_service.context_bundle(query, limit)


@app.get("/knowledge/music/summary")
def music_knowledge_summary():
    return music_intelligence_service.summary()


@app.get("/knowledge/music/search")
def music_knowledge_search(query: str, limit: int = 30):
    return {"query": query, "results": music_intelligence_service.search(query, limit)}


@app.get("/knowledge/music/artist")
def music_artist_report(name: str):
    try:
        return music_intelligence_service.artist_report(name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/knowledge/music/compare")
def music_compare_artists(names: list[str]):
    return music_intelligence_service.compare_artists(names)


@app.get("/knowledge/music/recommend")
def music_recommend(name: str, limit: int = 10):
    try:
        return music_intelligence_service.recommend_similar(name, limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/knowledge/music/metadata")
def music_metadata_analysis():
    return music_intelligence_service.metadata_analysis()


@app.get("/knowledge/audio/summary")
def audio_knowledge_summary():
    return music_production_service.summary()


@app.get("/knowledge/audio/search")
def audio_knowledge_search(query: str, limit: int = 30):
    return {"query": query, "results": music_production_service.search(query, limit)}


@app.get("/knowledge/daw/summary")
def daw_summary():
    return daw_control_service.summary()


@app.get("/knowledge/daw/search")
def daw_search(query: str = ""):
    return {"query": query, "results": daw_control_service.search(query)}


@app.get("/knowledge/daw/plugins")
def daw_plugins(query: str = "", limit: int = 250):
    return daw_control_service.plugin_inventory(query, limit)


@app.get("/knowledge/daw/project")
def daw_project_inspect(project_path: str):
    try:
        return daw_control_service.inspect_project(project_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Папка не найдена: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/knowledge/daw/project/report")
def daw_project_report(project_path: str):
    try:
        return daw_control_service.project_report(project_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Папка не найдена: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/daw/project/snapshot")
def daw_project_snapshot(request: DawSnapshotRequest):
    try:
        return daw_control_service.snapshot_project(request.project_path, request.snapshot_name, request.confirmed)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Папка не найдена: {exc}") from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/knowledge/daw/action/plan")
def daw_action_plan(request: DawActionRequest):
    try:
        return daw_control_service.plan_action(request.action, request.daw, request.project_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/daw/action/execute")
def daw_action_execute(request: DawActionRequest):
    try:
        return daw_control_service.execute_action(
            request.action, request.daw, request.project_path, request.confirmed
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/mixing/analyze")
def mixing_analyze(audio_path: str):
    try:
        return mixing_service.analyze(audio_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Файл не найден: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/mixing/suggest")
def mixing_suggest(audio_path: str, instrument: str = ""):
    try:
        return mixing_service.suggest_chain(audio_path, instrument)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Файл не найден: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/mixing/render-preview")
def mixing_render_preview(audio_path: str, preset: str = "clean_headroom", confirmed: bool = False):
    try:
        return mixing_service.render_preview(audio_path, preset, confirmed)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Файл не найден: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/mixing/compare")
def mixing_compare(mix_path: str, reference_path: str):
    try:
        return mixing_service.compare(mix_path, reference_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Файл не найден: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/mastering/report")
def mastering_report(audio_path: str):
    try:
        return mixing_service.mastering_report(audio_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Файл не найден: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/mastering/suggest")
def mastering_suggest(audio_path: str, genre: str = "", goal: str = ""):
    try:
        return mixing_service.suggest_mastering_chain(audio_path, genre, goal)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Файл не найден: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/mentor/voice/lessons")
def voice_lessons(category: str = ""):
    return {"lessons": voice_production_service.lessons(category)}


@app.get("/mentor/voice/search")
def voice_lesson_search(query: str, limit: int = 20):
    return {"query": query, "results": voice_production_service.search(query, limit)}


@app.get("/mentor/voice/workflow")
def voice_workflow(guitars: str = "", scope: str = "", issue: str = "", session_id: str = "", command: str = ""):
    """Build a safe, step-by-step vocal troubleshooting session."""
    return voice_production_service.workflow(guitars=guitars, scope=scope, issue=issue, session_id=session_id, command=command)


@app.get("/knowledge/guitars/summary")
def guitar_summary():
    return guitar_encyclopedia_service.summary()


@app.get("/knowledge/guitars/search")
def guitar_search(query: str, limit: int = 20):
    return {"query": query, "results": guitar_encyclopedia_service.search(query, limit)}


@app.post("/knowledge/guitars/compare")
def guitar_compare(ids: list[str]):
    return {"models": guitar_encyclopedia_service.compare(ids)}


@app.get("/mentor/psychology/safety")
def psychology_safety():
    return psychology_service.safety()


@app.get("/mentor/psychology/cards")
def psychology_cards(topic: str = ""):
    return {"cards": psychology_service.cards(topic)}


@app.get("/mentor/psychology/search")
def psychology_search(query: str, limit: int = 20):
    return {"query": query, "results": psychology_service.search(query, limit)}


@app.get("/knowledge/literature/works")
def literature_works(author: str = ""):
    return {"works": literature_service.works(author)}


@app.get("/knowledge/literature/search")
def literature_search(query: str, limit: int = 20):
    return {"query": query, "results": literature_service.search(query, limit)}


@app.get("/mentor/programming/lessons")
def programming_lessons(language: str = ""):
    return {"lessons": programming_mentor_service.lessons(language), "progress": programming_mentor_service.progress()}


@app.get("/mentor/programming/progress")
def programming_progress_summary():
    return programming_mentor_service.progress()


@app.get("/mentor/programming/lessons/{lesson_id}")
def programming_lesson(lesson_id: str):
    lesson = programming_mentor_service.get(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Programming lesson not found")
    return {"lesson": lesson, "progress": programming_mentor_service.progress().get("lessons", {}).get(lesson_id)}


@app.post("/mentor/programming/lessons/{lesson_id}/progress")
def programming_progress(lesson_id: str, payload: MentorProgressRequest):
    try:
        return programming_mentor_service.save_progress(lesson_id, payload.completed, payload.score, payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Programming lesson not found") from exc


@app.post("/mentor/programming/lessons/{lesson_id}/check")
def programming_exercise_check(lesson_id: str, payload: MentorExerciseRequest):
    try:
        lesson = programming_mentor_service.get(lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Programming lesson not found")
        language = str(lesson.get("language", "")).lower()
        result = coding_sandbox_service.run_python(f"mentor-{lesson_id}", payload.code, payload.timeout) if language == "python" else {"ok": True, "returncode": 0, "stdout": "", "stderr": "", "execution": "static_only"}
        evaluation = programming_mentor_service.evaluate(
            lesson_id, payload.code, result.get("stdout", ""), result.get("stderr", "")
        )
        evaluation["sandbox"] = {key: result.get(key) for key in ("ok", "timed_out", "returncode")}
        if evaluation["passed"]:
            programming_mentor_service.save_progress(lesson_id, True, evaluation["score"], "Автоматическая проверка упражнения пройдена")
        return evaluation
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Programming lesson not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/coding/sandbox/python")
def coding_sandbox_python(payload: SandboxRunRequest):
    try:
        return coding_sandbox_service.run_python(payload.project, payload.code, payload.timeout)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/coding/sandbox/javascript")
def coding_sandbox_javascript(payload: SandboxRunRequest):
    try:
        return coding_sandbox_service.run_javascript(payload.project, payload.code, payload.timeout)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/coding/projects/python")
def coding_create_python_project(payload: CodingProjectRequest):
    try:
        return coding_sandbox_service.create_python_project(payload.project, payload.files, payload.run_tests)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/coding/projects/javascript")
def coding_create_javascript_project(payload: CodingProjectRequest):
    try:
        return coding_sandbox_service.create_javascript_project(payload.project, payload.files, payload.run_tests)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/commands/catalog")
def commands_catalog():
    from computer_control import COMMANDS

    return {
        "commands": [
            {"intent": intent, "phrases": list(phrases or [])}
            for intent, phrases in COMMANDS.items()
        ],
        "source": "backend/voice_engine/commands.yaml",
    }


@app.post("/commands/index")
def commands_index(max_entries: int = 12000):
    count = filesystem_service.scan(max_entries=max(100, min(int(max_entries), 50000)))
    return {"ok": True, "indexed": count, "database": str(filesystem_service.db_path)}


@app.get("/commands/applications")
def commands_applications(refresh: bool = False):
    apps = application_service.discover() if refresh else application_service.apps
    return {"applications": apps, "path": str(application_service.path)}


@app.post("/voice/model")
def voice_model(req: VoiceModelRequest):
    try:
        return select_voice_model(req.model_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chat/cancel/{turn_id}")
async def cancel_chat(turn_id: str):
    """Cancel the current synchronous chat waiter and prevent late UI delivery."""
    task = active_chat_tasks.get(str(turn_id))
    if not task or task.done():
        return {"ok": True, "cancelled": False, "turn_id": str(turn_id)}
    task.cancel()
    return {"ok": True, "cancelled": True, "turn_id": str(turn_id)}


@app.get("/runtime/providers")
def runtime_providers(probe: bool = True):
    """Return normalized provider status without exposing credentials."""
    return runtime_registry.providers.snapshot(probe=probe)


@app.post("/runtime/context")
def runtime_context(req: RuntimeContextRequest):
    """Create a platform-neutral request context for a client adapter."""
    return runtime_registry.create_context(
        session_id=req.session_id,
        client=req.client,
        platform=req.platform,
        mode=req.mode,
        locale=req.locale,
        metadata=req.metadata,
    ).to_dict()


@app.post("/runtime/events")
def publish_runtime_event(req: RuntimeEventRequest):
    """Publish one bounded runtime event for future SSE/IPC adapters."""
    return runtime_registry.publish_event(
        event_type=req.event_type,
        source=req.source,
        request_id=req.request_id,
        payload=req.payload,
    ).to_dict()


@app.get("/runtime/events")
def runtime_events(limit: int = 50, chat_id: str | None = None, turn_id: str | None = None):
    return {"events": runtime_registry.list_events(limit=limit, chat_id=chat_id, turn_id=turn_id)}


# -----------------------------
# CHAT ENDPOINT
# -----------------------------


@app.post("/chat")
async def chat(req: ChatRequest):

    msg_id = str(uuid.uuid4())
    turn_id = str(req.turn_id or uuid.uuid4())
    current_task = asyncio.current_task()
    if current_task is not None:
        active_chat_tasks[turn_id] = current_task
    existing_thread = chat_store.get_session(req.chat_id) is not None
    runtime_registry.publish_event(
        event_type="thread.resumed" if existing_thread else "thread.started",
        source="chat",
        request_id=msg_id,
        payload={"chat_id": req.chat_id, "turn_id": turn_id},
    )
    runtime_registry.publish_event(
        event_type="turn.started",
        source="chat",
        request_id=msg_id,
        payload={"chat_id": req.chat_id, "turn_id": turn_id},
    )

    first_title = str(req.message or "").strip().replace("\n", " ")[:60]
    chat_store.touch_session(req.chat_id, title=first_title or "Вложение")
    user_message = chat_store.add_message(
        chat_id=req.chat_id,
        role="user",
        content=req.message,
        attachments=req.attachments[:12],
        reply_to=req.reply_to,
        message_id=msg_id,
    )
    # Copying user-selected files can block on slow disks, network mounts or
    # large media. Keep that work out of FastAPI's event loop.
    cached_attachments = await asyncio.to_thread(
        chat_store.register_attachments,
        req.attachments[:12],
        message_id=msg_id,
    )
    chat_store.replace_message_attachments(msg_id, cached_attachments)
    user_message = chat_store.get_message(msg_id) or user_message

    # Keep a small, ordered context window for conversational replies.  The
    # current message is stored separately below, so only earlier turns are
    # sent to the agents.
    context_messages = chat_store.list_messages(req.chat_id, limit=12, latest=True)
    context_messages = [
        {"role": item.get("role", "user"), "content": item.get("content", "")}
        for item in context_messages
        if item.get("id") != msg_id and item.get("content")
    ]

    loop = asyncio.get_event_loop()

    future = loop.create_future()

    main_agent.pending[msg_id] = future

    original_goal = req.message.strip()
    goal = original_goal
    safe_attachments = []
    semantic_attachments = []
    for attachment in cached_attachments:
        if not isinstance(attachment, dict):
            continue
        name = str(attachment.get("name") or "Вложение").strip()[:180]
        kind = str(attachment.get("kind") or "file").strip()[:40]
        if kind in {"mult", "sticker"} or attachment.get("emote"):
            # Semantic picker items are already part of the message payload;
            # never let the planner interpret a filename as a URL/tool input.
            semantic_attachments.append(name)
        else:
            safe_attachments.append(f"{name} ({kind})")
    if safe_attachments:
        goal += "\n\nПрикреплённые материалы: " + ", ".join(safe_attachments)
    if semantic_attachments:
        goal += (
            "\n\nСемантические мульты/стикеры: "
            + ", ".join(semantic_attachments)
            + ". Это локальные визуальные вложения, а не URL и не имена хостов. "
              "Не выполняй по ним сетевые запросы, загрузку или открытие инструментом; "
              "считай их уже прикреплёнными материалами пользователя."
        )

    # Uploading a document/media item is a chat event, not a file-agent
    # command.  Previously an empty message (or "Отправляю файл") plus an
    # attachment was routed to FileAgent, whose only safe fallback is
    # "не понял действие".  Preserve explicit read/write/delete requests,
    # but acknowledge a plain upload through the conversational path.
    operation_words = (
        "прочитай", "открой", "покажи содержимое", "сохрани", "запиши",
        "создай", "удали", "удалить", "перемести", "скопируй",
    )
    upload_words = ("отправ", "прикреп", "загруз", "вложени")
    if safe_attachments and (
        not original_goal or any(word in original_goal.lower() for word in upload_words)
    ) and not any(word in original_goal.lower() for word in operation_words):
        goal = (
            "Пользователь передал вложение. "
            "Подтверди получение в одном коротком живом ответе; "
            "не запускай операции с диском без отдельной команды."
        )

    # Resolve verified local knowledge before waking the planner/LLM. This
    # keeps the normal chat path fast and preserves the same source order as
    # the voice runtime. Dynamic questions continue through the existing
    # planner unchanged.
    local_answer = None
    if original_goal and not safe_attachments:
        local_answer = knowledge_search_service.answer(original_goal, context_messages)
    if local_answer is not None:
        result_text = str(local_answer.get("answer") or "").strip()
        assistant_message = chat_store.add_message(
            chat_id=req.chat_id,
            role="assistant",
            content=result_text,
        )
        runtime_registry.publish_event(
            event_type="item.completed",
            source="knowledge3",
            request_id=msg_id,
            payload={
                "chat_id": req.chat_id,
                "turn_id": turn_id,
                "item_type": "knowledge_answer",
                "message_id": assistant_message.get("id"),
                "source": local_answer.get("source"),
            },
        )
        runtime_registry.publish_event(
            event_type="turn.completed",
            source="knowledge3",
            request_id=msg_id,
            payload={"chat_id": req.chat_id, "turn_id": turn_id, "source": local_answer.get("source")},
        )
        main_agent.pending.pop(msg_id, None)
        active_chat_tasks.pop(turn_id, None)
        return {
            "response": result_text,
            "turn_id": turn_id,
            "message_id": assistant_message.get("id"),
            "user_message_id": user_message.get("id"),
            "attachments": user_message.get("attachments", []),
            "knowledge": local_answer,
        }

    knowledge_bundle = knowledge_search_service.context_bundle(original_goal, 6) if original_goal and not safe_attachments else {"multi_source": False}
    if knowledge_bundle.get("multi_source"):
        context_lines = []
        for item in knowledge_bundle.get("sources", []):
            context_lines.append(f"[{item['module']}] {item['title']}: {item['answer']}")
        goal = goal + "\n\nПроверенный локальный контекст Knowledge 3.0. Используй его, не выдумывай источники:\n" + "\n".join(context_lines)

    await bus.send(
        "planner",
        {
            "type": "create_plan",
            "payload": {
                "goal": goal,
                "id": msg_id,
                "chat_id": req.chat_id,
                "turn_id": turn_id,
                "history": context_messages,
                "custom_instructions": req.custom_instructions.strip(),
                "preferred_address": req.preferred_address.strip(),
                "chat_system_prompt": req.chat_system_prompt.strip(),
            },
        },
    )

    try:
        result = await future
    except asyncio.CancelledError:
        main_agent.pending.pop(msg_id, None)
        runtime_registry.publish_event(
            event_type="turn.aborted",
            source="chat",
            request_id=msg_id,
            payload={"chat_id": req.chat_id, "turn_id": turn_id},
        )
        raise
    finally:
        active_chat_tasks.pop(turn_id, None)

    assistant_message = chat_store.add_message(
        chat_id=req.chat_id,
        role="assistant",
        content=str(result),
    )
    runtime_registry.publish_event(
        event_type="item.completed",
        source="chat",
        request_id=msg_id,
        payload={
            "chat_id": req.chat_id,
            "turn_id": turn_id,
            "item_type": "assistant_message",
            "message_id": assistant_message.get("id"),
            "content": str(result),
        },
    )
    runtime_registry.publish_event(
        event_type="turn.completed",
        source="chat",
        request_id=msg_id,
        payload={"chat_id": req.chat_id, "turn_id": turn_id},
    )

    return {
        "response": result,
        "turn_id": turn_id,
        "message_id": assistant_message.get("id"),
        "user_message_id": user_message.get("id"),
        "attachments": user_message.get("attachments", []),
    }


async def app_server_turn_runner(
    thread_id: str,
    turn_id: str,
    text: str,
    attachments: list[dict],
) -> dict:
    return await chat(
        ChatRequest(
            message=text,
            attachments=attachments,
            chat_id=thread_id,
            turn_id=turn_id,
        )
    )


app_server.set_turn_runner(app_server_turn_runner)


@app.post("/app-server/rpc")
async def app_server_rpc(request: dict):
    """JSON-RPC 2.0 transport for local Codex-like app-server clients."""
    return await app_server.handle(request)


@app.websocket("/app-server/ws")
async def app_server_websocket(websocket: WebSocket):
    """Bidirectional local transport with lifecycle event notifications."""
    await websocket.accept()
    cursor = 0
    try:
        while True:
            try:
                request = await asyncio.wait_for(websocket.receive_json(), timeout=0.25)
                response = await app_server.handle(request)
                if response is not None:
                    await websocket.send_json(response)
            except asyncio.TimeoutError:
                pass

            events = runtime_registry.list_events(limit=256)
            for event in events[cursor:]:
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "method": "event",
                    "params": event,
                })
            cursor = len(events)
    except WebSocketDisconnect:
        return


@app.get("/chat/history")
def chat_history(chat_id: str = "default", limit: int = 100, latest: bool = False):
    return {"messages": chat_store.list_messages(chat_id, limit, latest=latest)}


@app.get("/api/messages")
def api_messages(
    chat_id: str = "default",
    limit: int = 100,
    after_id: str | None = None,
    before_id: str | None = None,
    ids: str = "",
):
    requested_ids = [value for value in ids.split(",") if value] if ids else None
    return {
        "data": chat_store.list_messages(
            chat_id,
            limit,
            after_id=after_id,
            before_id=before_id,
            ids=requested_ids,
        )
    }


@app.delete("/api/messages/{message_id}")
def api_delete_message(message_id: str):
    if not chat_store.delete_message(message_id):
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True, "message_id": message_id}


@app.get("/api/media/{attachment_id}")
def media_cache(attachment_id: str):
    """Serve only files registered by Jarvis' chat attachment cache."""
    record = chat_store.attachment_path(attachment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path, name, media_type = record
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment is no longer available")
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}"},
    )


class ReactionRequest(BaseModel):
    reaction: str
    actor: str = "user"


@app.post("/chat/messages/{message_id}/reaction")
def toggle_message_reaction(message_id: str, req: ReactionRequest):
    return chat_store.toggle_reaction(message_id, req.reaction, req.actor)


@app.post("/chat/messages/{message_id}/pin")
def toggle_message_pin(message_id: str, actor: str = "user"):
    return chat_store.toggle_pin(message_id, actor)


# -----------------------------
# HEALTH
# -----------------------------


@app.get("/health")
def health():

    return system_health()


@app.get("/backups/status")
def backups_status():
    return backup_agent.status()


@app.post("/backups/run")
async def backups_run():
    """Run a backup off the event loop; intended for an explicit user action."""

    path = await asyncio.to_thread(backup_data, backup_agent.sources, backup_agent.backup_root)
    backup_agent._last_backup = path
    backup_agent._last_error = None
    return {"path": path, "status": "completed"}


# -----------------------------
# DEVICES / MULTIMODAL CAPABILITIES
# -----------------------------


@app.get("/devices/capabilities")
def device_capability_status(probe: bool = False):
    """Return real optional-device availability without starting heavy workers."""

    return device_capabilities.snapshot(probe=probe)


@app.post("/devices/camera/snapshot")
async def device_camera_snapshot(index: int = 0):
    """Capture one camera frame on demand; no persistent video worker is created."""

    result = await device_capabilities.capture_camera(index, UPLOAD_DIR)
    return result


# -----------------------------
# RUN SERVER
# -----------------------------


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=API_PORT,
        reload=False,
    )
