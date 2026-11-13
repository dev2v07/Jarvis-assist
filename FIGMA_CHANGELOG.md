# Figma Change Log

## 2026-10-28 — Current UI inventory transferred to JARVIS

- Target: [JARVIS Figma file](https://www.figma.com/design/Pa9zk1REUvBbZ7xf4aSgW5/JARVIS)
- Added page: `Current UI`
- Added top-level frames:
  - `01 Assistant — Default`
  - `02 Chat — Active`
  - `03 Chat — Voice recording`
  - `04 History`
  - `05 Settings — General`
  - `06 Settings — AI providers`
  - `07 Settings — IRON / HUD`
  - `08 Dialogs — Chat / Profile / Weather`
- Source reviewed: `frontend/jarvis_ui.py`, `frontend/jarvis_hud.py`, `frontend/chat_composer.py`, `frontend/assets/CHAT/chat.html`, `frontend/profile_dialog.py`, `docs/REDESIGN_AUDIT_20261028.md`, and current settings/session behavior recorded in `docs/HANDOFF.md`.
- Captured current-state details: 1280×850 desktop shell, native Qt sidebar, TECH-A HUD, WebEngine chat, composer idle/voice-recording states, session history, general/AI/IRON settings, and modal surfaces.
- Figma verification: metadata confirmed 8 top-level frames; screenshots reviewed for assistant, active chat, settings, and dialogs. Fixed compact `ON` pill wrapping, restored HUD to 710×710, and increased the profile dialog height to contain its save action.
- Limitation: this is a structured current-state reference for redesign; it is not a pixel capture of the live Qt/WebEngine window. The source uses raster HUD assets and runtime data that are represented as editable Figma placeholders/labels.
- Rollback point: remove or archive the `Current UI` page in Figma; no application source files were changed by this queue.

## 2026-10-28 — Glass UI redesign from `Референсы`

- Target: same [JARVIS Figma file](https://www.figma.com/design/Pa9zk1REUvBbZ7xf4aSgW5/JARVIS)
- Reference inspected: page `Референсы`, dark frame `5:1319` and light frame `5:1610`.
- Added page: `Glass UI`
- Added frames:
  - `01 Jarvis Glass — Chat` (`6:311`, 1440×900)
  - `02 Jarvis Glass — Assistant` (`6:314`, 1440×900)
  - `03 Jarvis Glass — Settings` (`6:317`, 1440×900)
- Design direction: dark glass surfaces, green/cyan/violet ambient glow, thin translucent borders, shared sidebar and icon rail, command hero, chat composer, TECH-A core, runtime status, settings navigation and accent controls.
- Verification: all three frames were screenshot-checked; page metadata confirms the three top-level screens and their dimensions.
- Limitation: this is an editable Figma redesign direction based on the reference language; it does not yet replace the Qt/WebEngine implementation.
- Rollback point: archive/delete the `Glass UI` page; `Референсы` and `Current UI` remain unchanged.

## 2026-10-28 — Current accent correction

- Updated the `Glass UI` page accent from the earlier cyan approximation to the confirmed current Jarvis accent `#00AAFF` (RGB 0, 170, 255).
- Updated active navigation, Jarvis marks, chips, buttons, HUD rings, borders, status indicators and accent text across the three Glass UI frames.
- Verification: `01 Jarvis Glass — Chat` screenshot rechecked; the accent is visibly blue and matches the supplied current-color reference.
