# Jarvis Assist release audit — 2026-11-13

## Scope and sources

The audit covered the repository tree, `docs/HANDOFF.md`,
`docs/HANDOFF_ASSIST.md`, the backend entry point, the PySide6 desktop client,
voice adapters, settings, requirements and the existing GitHub workflow. The
historical handoff files were preserved; this report is a release snapshot and
does not replace them.

## Architecture found

- `backend/main.py` is the canonical FastAPI entry point on loopback port 8000.
- `backend/agents/` contains planner, executor, critic and feature agents.
- `backend/services/` contains chat storage, LLM/provider configuration,
  runtime events, device capability reporting and voice runtime control.
- `backend/voice_engine/` contains STT/VAD/TTS adapters and the voice-model
  registry. Jarvis is the default profile; Kesha is a Silero `ru_v3`/`aidar`
  adapter when its local checkpoint and Torch are available.
- `frontend/jarvis_ui.py` is the PySide6 desktop client. It owns HUD/settings,
  QSettings persistence, voice controls and calls the local backend API.
- `frontend/jarvis_hud.py` provides the transparent widget and metric layers.
- `core/` contains shared API/message infrastructure used by the backend.

## Handoff reconciliation

The handoffs describe a long sequence of UI, voice-runtime and training work.
The current source confirms the major recent decisions: the voice registry is
separate from the UI; command data remains in the backend voice-engine area;
S1/S2 GPT-SoVITS work is local development data; and the voice engine must not
block application startup. Some historical entries describe experiments that
are no longer present (legacy voice scripts were removed), so the source tree
is the authority for the release snapshot.

## Current checks

- Targeted Python compilation passed for backend, frontend launcher and voice
  registry modules.
- Backend test discovery passed 22/22 tests in the audit run.
- Existing CI compiles `backend frontend core` and runs backend tests.
- Full GUI, audio playback, installed EXE, uninstall and reboot autostart tests
  have not yet been claimed; they require the packaging/runtime phase.

## Public-release boundaries

The repository contains local virtual environments, downloaded model sources,
training logs, checkpoints, datasets and generated audio. They are not runtime
source and must remain outside public Git history and the installer. The
unfinished Jarvis voice is documented as “in development”; it is not bundled
or represented as a ready model.

## Changes made after audit

- Added `frontend/launch_jarvis.py` to start backend and desktop client from one
  source-tree command.
- Added `frontend/autostart.py` and a General-settings checkbox for optional
  current-user Windows autostart.
- Added release documentation, MIT license and public-artifact ignore rules.

## Open release gates

PyInstaller/Inno Setup availability, a real frozen build, a clean staged Git
tree, GitHub authentication and runtime screenshots remain release gates. No
GitHub push is claimed until those gates are actually verified.
