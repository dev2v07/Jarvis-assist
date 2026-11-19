# Jarvis commands on Windows

- Install core runtime: python -m pip install -r backend/requirements-core.txt
- Install optional UI/voice/device features in the same interpreter: python -m pip install -r backend/requirements-optional.txt
- Create the documented shared environment: python -m venv backend/jarvis_env; then use backend\jarvis_env\Scripts\python.exe for installs and runs.
- Start product: python frontend/launch_jarvis.py
- Start backend directly for API work: set PYTHONPATH=backend, then python backend/main.py; normal launcher behavior is preferred because it owns backend/UI lifecycle.
- Syntax smoke check: python -m compileall -q backend frontend core
- Unit tests: set PYTHONPATH=backend, then python -m unittest discover -s backend/tests -p test_*.py -v
- Build Windows artifacts: powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1 after PyInstaller/Inno Setup prerequisites are present.
- Voice-library catalog generation: python backend/voice_engine/build_voice_library.py; bounded/resumable generation uses generate_voice_library.py --limit N or --all and must not be run as uncontrolled bulk work.
- Read-only repository checks: git status --short --branch; git log -1 --oneline.
- Avoid stopping an existing port-8000 process during diagnostics; launcher explicitly rejects incompatible listeners.
