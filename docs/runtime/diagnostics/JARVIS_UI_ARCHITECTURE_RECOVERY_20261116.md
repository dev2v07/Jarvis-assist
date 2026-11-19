# Jarvis UI Architecture Recovery Report

## Scope

This checkpoint restores the factual desktop/backend map and records the minimal fixes for the confirmed settings and sidebar regressions. No business logic, databases, user files or backend entrypoints were removed.

## Factual architecture

- `frontend/launch_jarvis.py` is the normal desktop entrypoint. It owns the desktop interpreter, checks the configured API, and starts or reuses one compatible local backend.
- `backend/main.py` is the production local FastAPI composition root. The current listener is `127.0.0.1:8000`.
- `core/api.py` and `core/jarvis_api.py` are legacy/simple FastAPI entrypoints and are not imported by the normal launcher. `backend/account_server` is a separate optional PostgreSQL/OAuth service boundary.
- `frontend/jarvis_ui.py` owns the PySide6 shell, HUD, sidebar, settings stack and chat WebEngine. `ChatStore` and provider/runtime services remain backend-owned.
- `KnowledgeSearchService`, `ConversationResolver`, `VoiceRuntime` and `AccountCoordinator` remain the existing service boundaries; no parallel production manager was introduced.

The normal local run therefore has one backend process and one primary FastAPI application. Test and optional service entrypoints remain isolated and were not deleted.

## Confirmed causes

The settings shell contained hidden pages whose size hints exceeded the fixed `1280x850` window. The personalization page required a 720 px minimum, the devices page required 900 px, and the AI/general cards also advertised wide layouts. Selecting or laying out Settings caused Qt to attempt a roughly `1600x1063` native geometry, producing repeated `QWindowsWindow::setGeometry` warnings and a nonresponsive-looking shell.

The standalone AI provider dialog had synchronous `requests` calls in `load_current`, `fetch_models`, `test_provider` and `save_provider`. These calls were made in the Qt GUI thread and could block for 4–20 seconds. Existing worker classes were present in the file but were only used by the embedded AI page, not by this dialog.

## Changes

`frontend/jarvis_ui.py` now:

- bounds settings pages and the stacked settings content to the fixed shell;
- activates the main/container/sidebar layouts after the first native show and widget-mode visibility transition;
- routes standalone AI provider I/O through `ProviderOperationWorker` and `QThread` with loading/error/success status text;
- reuses an already-visible AI dialog instead of creating duplicates.

## Verification

- Backend unittest discovery: **96/96 PASS** with `PYTHONPATH=backend` and `backend/jarvis_env`.
- Frontend unittest discovery: **20/20 PASS**.
- `C:\Python314\python.exe -m py_compile frontend\jarvis_ui.py frontend\launch_jarvis.py`: **PASS**.
- `git diff --check`: **PASS**.
- Live Jarvis UI: Settings page opened; accessibility tree exposed the menu, pinned chat list, recent chat list and settings navigation: **PASS**.
- Post-restart stderr: no further `Unable to set geometry` warning; known QtWebEngine GLES fallback remains: **PASS for this regression / known rendering limitation**.
- AI provider click-by-click live acceptance: **BLOCKED**, because Windows screenshot/bounds capture became unavailable while changing the stacked page. The non-blocking worker path is covered by source inspection and compile/tests, not claimed as full visual acceptance.

## Remaining limitations

- The current port-8000 listener is an existing user-owned process; it was inspected and not stopped.
- QtWebEngine still logs GLES3-to-GLES2 fallback on this host.
- Full manual AI provider test/save/model-fetch and microphone/TTS acceptance remain separate runtime gates.
