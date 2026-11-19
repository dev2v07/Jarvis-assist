# Jarvis technology stack

- Platform/runtime: Windows; Python 3.11+ expected by README.
- Backend: FastAPI, uvicorn, Pydantic, requests, python-dotenv, Ollama client, psutil; local API on 127.0.0.1:8000.
- Desktop: PySide6 6.10.2 optional dependency, Qt WebEngine/WebChannel/Multimedia; software Qt compositor is configured in frontend/jarvis_ui.py for this host.
- Voice: faster-whisper and Silero/VAD-related adapters are optional; TTS, PyAudio, openwakeword, pvporcupine and Vosk-related paths are capability-dependent.
- Data/media: SQLite via stdlib/service repositories; WAV catalogs under data/; optional OpenCV/Pillow, torch/torchaudio, transformers and diffusers for device/voice capabilities.
- Providers: Ollama is the documented default (qwen3:8b); OpenAI-compatible, DeepSeek, Codex/Claude placeholders and FreeLLMAPI adapters exist behind runtime/provider configuration.
- Account boundary: optional Flask/Flask-CORS account server with PostgreSQL-oriented configuration, SMTP and Google identity integration; local account state uses SQLite and Windows DPAPI helpers.
- Packaging: PyInstaller script plus Inno Setup recipe under packaging/; no pyproject.toml or setup.py was found. Dependencies are split into requirements-core.txt, requirements-optional.txt and requirements-device.txt.
- Environment examples: backend/.env.example and backend/account_server/.env.example; local backend/dev.env is loaded by backend/config.py and must not be treated as source-controlled configuration.
