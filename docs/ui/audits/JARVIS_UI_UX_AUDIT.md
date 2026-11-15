# Jarvis — UI/UX audit

Audit date: 2026-11-15. This combines source inspection with the available runtime evidence. No Jarvis window was running during this audit; the current source launcher and the older frozen EXE were not started to avoid mixing stale build behavior with the dirty source tree.

## Evidence boundary

- Confirmed statically: widgets/classes, button wiring, endpoint URLs, HUD constants, QSettings usage and worker/thread boundaries.
- Confirmed by existing project evidence: recent HUD anchor corrections, fullscreen logic and voice-session design are documented in current handoffs.
- Not confirmed here: current visual screenshot, resize/fullscreen geometry on this checkout, real microphone capture, Silero/Vosk device behavior, TTS playback, WebEngine rendering, or persistence across an actual process restart.

## UI inventory

| Area | Elements found | Backend or local owner |
|---|---|---|
| Main window | frameless/transparent modes, title/system controls, resize/fullscreen, pages | `JarvisUI`, QSettings, local Qt |
| HUD | START, top CHAT/AGENTS/FUNCTION/HISTORY, bottom PROV/MOD/VID/SET/OUT, TECH-A side buttons | `JarvisHUD`, `jarvis_ui.py`; some actions are local/navigation |
| Chat | session list, message history, composer, attachments, reactions, pins, delete/archive/rename/favorite flows | `/chat*`, `/api/messages*`, `ChatStore` |
| Composer | text field, send, local dictation microphone, voice-chat button, attachment/tools menu | local worker plus `/voice/session/*` |
| Voice widget | START/STOP, status overlay, microphone enabled state, draggable floating status widget | `/voice/start`, `/voice/status`, `/voice/stop` |
| Settings | general/autostart, LLM provider/model/API fields, hardware/audio/video, voice model/profile, appearance | settings endpoints, Windows Run key, QSettings |
| Detached widgets | weather card and voice status overlay | local Qt; weather uses external API/config path |
| Account | login/register/verify/reset/profile dialogs | local account coordinator/provider boundary; server coupling not proven |
| Media | attachments/media URLs, video dialog, audio playback support | `/api/media/*`, Qt Multimedia/WebEngine |
| Tools/integrations | computer/browser/Figma/plugins menu entries | several are explicit connection points/stubs rather than verified integrations |

## HUD geometry baseline

The current handoff records these canonical points; this audit does not alter or reinterpret them:

| Group | Elements |
|---|---|
| Top | CHAT `(266,137)`, AGENTS `(333,137)`, FUNCTION `(407,137)`, HISTORY `(493,137)` |
| Bottom | PROV `(232,548)`, MOD `(291,548)`, VID `(350,548)`, SET `(409,548)`, OUT `(468,548)` |
| Center | START `(280,280)`, visual size `150×150`, HUD center `(355,355)` |
| Side | COMP, DOCS, CTRL, DESK, XPLR, CHRM, GAME, CFG from TECH-A source points |

Existing handoff evidence says the HUD container was fixed to `JarvisHUD.HUD_SIZE` during resize and saved anchors were synchronized after drag. The same handoff explicitly says screenshot capture timed out, so visual acceptance remains open.

## Interaction audit

| Interaction | Static result | Runtime verdict |
|---|---|---|
| send message | worker uses `POST /chat`; runtime event worker polls deltas | code path present; not live-tested |
| switch/create/rename/archive/pin/delete chat | callbacks call corresponding session routes | code path present; cross-chat context isolation not observed live |
| history reload | `/chat/history` and session refresh callbacks exist | persistence after restart not observed |
| dictation | bounded worker, device/model errors mapped to user messages | not tested with microphone |
| widget voice | creates a chat for a new widget source and rejects competing sessions unless replace | unit/handoff evidence; microphone/TTS not tested |
| chat voice | binds session to selected chat and stops on chat change | unit/handoff evidence; no live UI verification |
| settings | provider/model test and save calls exist; local QSettings used for UI settings | provider and error UX not fully observed |
| integrations menu | code exposes connection points; current handoff says browser/Figma/plugin automation is not implemented as a complete feature | not a confirmed working feature |
| fullscreen/resize | code and handoff include explicit state restoration and fixed HUD sizing | visual runtime gate open |

## UI/Backend risks

1. Many frontend callbacks embed `http://127.0.0.1:8000` directly. There is no typed central API client, so route names, timeout policies and error rendering are duplicated.
2. Chat requests use a 60-second request worker timeout while runtime event polling has a short polling timeout. The UI can stop receiving deltas while the backend task remains active unless cancellation completes correctly.
3. Several settings and capability requests are asynchronous but the audit has not observed loading, timeout, retry and stale-state rendering in the actual window.
4. The large `jarvis_ui.py` combines layout, networking, persistence, Windows process control and state transitions. This is the primary UI regression hotspot.
5. The visual baseline is documented, but screenshot-based acceptance is still unavailable in this run. Claims of pixel-faithful current geometry would therefore be unsupported.

## Required manual acceptance pass

Run on the current source tree with one controlled backend instance:

1. Launch through `frontend/launch_jarvis.py`; record process IDs and `/health`.
2. Exercise window restore, resize, fullscreen and close; capture screenshots at minimum/standard/maximized sizes.
3. Create two chats, send one message to each, switch repeatedly, reload history and restart once; verify no message/context mixing.
4. Test dictation separately from chat voice.
5. Test widget voice and chat voice mutual exclusion, transcript persistence, stop/restart and microphone release.
6. Test provider timeout/error, disabled provider, missing model and LLM settings save/reload.
7. Test every visible HUD/button action and record whether it navigates, calls backend, is a stub, or fails.
