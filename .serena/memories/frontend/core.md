# Frontend architecture

- frontend/launch_jarvis.py is the supported entrypoint; one interpreter runs backend child process and PySide6 UI, with lock-file protection and compatibility checks for an already-running API.
- frontend/jarvis_ui.py is the main PySide6 window/HUD/navigation layer. It talks to the local API, embeds a Qt WebEngine chat surface, and contains desktop settings/history/account/device integrations.
- Chat requests run away from the Qt GUI thread; voice push-to-talk/dictation has a separate bounded worker path.
- Settings/AI/chat-read HTTP operations use `start_network_operation`: a bounded Python `threading.Thread` queues results back through the GUI bridge. Do not restore per-request QObject/QThread ownership: on this Windows host it reproduced a `shiboken6.abi3.dll` access violation during queued worker teardown (see REC-UI-019). Long-duration runtime validation remains open.
- frontend/voice_input.py is a Vosk push-to-talk adapter; backend/services/voice_runtime.py has the primary runtime voice path. Treat these as separate paths until a shared contract is deliberately introduced.
- frontend/chat_composer.py, voice_mode_overlay.py, jarvis_hud.py, profile_dialog.py and account_ui.py are focused UI components.
- The UI forces software Qt/Chromium rendering by default on this Windows host due to prior DirectComposition/GPU instability.
- Autostart is user-scoped through HKCU Run; no administrator requirement is intended.
