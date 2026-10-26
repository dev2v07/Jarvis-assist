import asyncio
import uuid
import uvicorn
import os

from fastapi import FastAPI
from pydantic import BaseModel

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

from config import LOG_DIR, update_runtime_config

# -----------------------------
# APP
# -----------------------------

app = FastAPI(title="Jarvis Backend")

print("Startup check:", check())

# -----------------------------
# MESSAGE BUS
# -----------------------------

bus = MessageBus()

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

    await start_agents()

    print("Jarvis agents started")


# -----------------------------
# REQUEST MODEL
# -----------------------------


class ChatRequest(BaseModel):

    message: str


class HardwareSettings(BaseModel):
    audio_input_device: int = -1
    video_input_device: int = 0


@app.post("/hardware/settings")
def save_hardware_settings(settings: HardwareSettings):
    """Persist physical audio/video device selections for voice and vision modules."""
    updates = {
        "JARVIS_MICROPHONE_INDEX": str(settings.audio_input_device),
        "JARVIS_CAMERA_INDEX": str(settings.video_input_device),
    }
    update_runtime_config(updates)
    os.environ.update(updates)
    return {"ok": True, **updates}


# -----------------------------
# CHAT ENDPOINT
# -----------------------------


@app.post("/chat")
async def chat(req: ChatRequest):

    msg_id = str(uuid.uuid4())

    loop = asyncio.get_event_loop()

    future = loop.create_future()

    main_agent.pending[msg_id] = future

    await bus.send(
        "planner",
        {
            "type": "create_plan",
            "payload": {
                "goal": req.message,
                "id": msg_id,
            },
        },
    )

    result = await future

    return {"response": result}


# -----------------------------
# HEALTH
# -----------------------------


@app.get("/health")
def health():

    return system_health()


# -----------------------------
# RUN SERVER
# -----------------------------


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
