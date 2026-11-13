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
- Full GUI and audio playback tests remain open. Backend health and source
  launcher were verified.
- Inno Setup produced `dist/Jarvis-Assistant-Setup.exe` (about 450 MB).
- A silent install to a temporary directory returned exit code 0 and created
  Start-menu and desktop shortcuts. A silent uninstall returned exit code 0
  and left the test directory empty.
- Reboot autostart has not been verified by an actual reboot.

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

The public Git tree was scanned for common secret formats; GitHub Push
Protection initially found a token in an old legacy file, so that file was
removed from local history before the normal push. The public `master` branch
is now published.

The attribution link is implemented in the source app directly below the
profile card and is hidden in transparent HUD mode. The installer wizard also
contains the clickable attribution link and publisher URL.

The frozen GUI gate is still open: the latest `JarvisAssistant.exe` was
launched, but its window reported `Unhandled exception in script` caused by
`DLL load failed while importing QtCore: Не найдена указанная процедура`.
Consequently, installed-GUI voice/audio playback has not been claimed as
verified. The source backend health check remains independently verified.

Runtime PNG screenshots and a real reboot autostart test remain open. The
installer compiles successfully, but should not be described as a fully
usable desktop release until the frozen PySide6/QtCore startup issue is fixed.
The installer is oversized because the current backend bundle includes
PyTorch and optional voice/device dependencies.
