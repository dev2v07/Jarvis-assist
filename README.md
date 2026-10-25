# Jarvis

Jarvis is a personal AI assistant platform in development. The current canonical runtime is:

- backend: `backend/main.py` on `http://127.0.0.1:8000`;
- desktop client: `frontend/jarvis_ui.py`;
- target clients: web, smartphone, smart speaker and smart-home adapters.

## Local launch

Backend:

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Desktop frontend, in a second terminal:

```powershell
python frontend\jarvis_ui.py
```

## Configuration

Copy `backend/.env.example` to a local environment file and keep real secrets outside Git. Ollama is optional at process startup; without it Jarvis uses the configured fallback behavior.

## Development protocol

All change queues, backups, checks and rollback points are recorded in [docs/HANDOFF.md](docs/HANDOFF.md). The target architecture is documented in [docs/JARVIS_TZ.md](docs/JARVIS_TZ.md).
