# Backend architecture

- backend/main.py is the FastAPI composition root and imports all major agents/services; route surface covers settings, chat sessions/messages, voice, knowledge/mentors, coding sandbox/projects, commands, runtime events, app-server RPC, backups, health and devices.
- Startup performs a system check, optional bounded Ollama warmup, starts all configured agents; shutdown stops VoiceRuntime and agents in reverse order.
- Core orchestration uses MessageBus plus Planner, ExecutorAgent, CriticAgent and specialized agents.
- ChatStore owns local chat/application persistence; AppServer exposes JSON-RPC-style app integration; RuntimeRegistry and provider adapters manage LLM capabilities.
- VoiceRuntime owns microphone/session/command-conversation routing and receives the shared KnowledgeSearchService from main.py; VoiceSessionManager owns active sessions.
- Knowledge services split responsibilities: index/integrity, search facade, local response matching, offline catalog, structured knowledge3, domain mentors, music/audio/DAW/mixing.
- Account client code is under backend/account; backend/account_server is a separate optional service boundary and must not be assumed active in local desktop mode.
- StoragePaths is the canonical path registry for chat_state, request_history, account_state and filesystem_index.
- Focused handoff: docs/HANDOFF_ASSIST.md contains the latest Assist/voice/knowledge queues and explicit next steps; it warns against uncontrolled audio generation and unconfirmed DAW changes.
