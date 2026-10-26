# Jarvis — canonical project structure

## Current source of truth

- `backend/` — Python API, runtime, agents, services and tools;
- `frontend/` — current PySide6 desktop client;
- `core/` — shared compatibility modules;
- `docs/JARVIS_TZ.md` — target product and cross-platform architecture;
- `docs/HANDOFF.md` — change log, verification and rollback points.

## Legacy and non-source material

The workspace contains historical Jarvis generations, archives, installers, model files and experiments. They are preserved for reference and are not part of the active runtime. New code must not import from these directories without an explicit migration entry in `HANDOFF.md`.

## Platform rule

Desktop, web, smartphone, smart speaker and smart-home clients must depend on the backend/core contracts. Platform-specific code belongs in adapters, not in Planner, Executor or the shared event schema.

## Stage 0 completion baseline

## TECH-A network readouts

The left-side network block preserves the original Rainmeter terminology from
`TECH-A 6 CPU.ini`:

- `UP` / `UPLOAD` — outgoing network traffic (`NetOut`);
- `UPLOAD.Total` — cumulative outgoing traffic in bytes;
- `DN` / `DOWNLOAD` — incoming network traffic (`NetIn`);
- `DOWNLOAD.Total` — cumulative incoming traffic in bytes.

In Jarvis, the four values remain dynamic and are formatted automatically in
`B`, `KB`, `MB`, `GB`, or `TB`. The `UP` and `DN` labels are preserved by the
source `BG3.png` layer and are not drawn a second time by the HUD code. They are
visual direction labels, not interactive controls.

The two thin progress arcs in the NET area are live as well. Their normalized
values follow the original TECH-A formulas: outgoing traffic is divided by
`1,048,576` bytes/s and incoming traffic by `6,144,000` bytes/s. The arcs are
smoothed in the HUD, so short network bursts do not cause flicker.

The four primary cells `CPU`, `RAM`, `GPU`, and `DISK` use the active cyan
value color `RGB(0, 235, 245)`. The central `TEMP` and `NET` gauge cells are
not rendered in the current widget layout; the separate `UP/DN` network block
remains available for traffic details.

Application appearance settings belong to the `НАСТРОЙКИ` navigation page.
The interface font and accent color are persisted with `QSettings`. The default
accent is `#00EBF5` (`RGB 0, 235, 245`) and is applied to the primary HUD
indicator arcs, network progress arcs, and application navigation/action
buttons. Changing it updates the running UI and is available for the next
launch.

The selected interface font is also passed into the HUD renderer. It controls
all code-rendered HUD text (labels, indicator values, RAM/network readouts) and
all Qt text in the application tabs. Text baked into TECH-A PNG layers remains
unchanged because it is raster artwork rather than a live font.

- secrets are supplied through environment variables;
- generated runtime state is ignored by Git;
- core and optional dependencies are listed separately;
- a local Git baseline and CI syntax check exist;
- backend and desktop frontend are manually launched after each change queue.

All live Qt labels and controls keep a readable foreground color when a TECH-A
font is selected; combo-box popup items use a light background for contrast.

The text color is a separate persisted appearance setting. It defaults to
`#FFFFFF` and is applied to live HUD text and the visible Qt settings UI.

Color selection uses a Jarvis-styled non-native dialog. The selected sidebar
item uses the accent background with dark text for contrast.

Font changes are applied recursively to all existing Qt widgets and to the
custom HUD renderer, so changing the family updates the complete live app.

The HUD also renders live local PC date/time: the top center uses 24-hour
`HH:MM`, while the bottom center uses ordinal English format such as
`25TH OCT`. Both values are refreshed from `datetime.now()` and follow the
computer's local clock and calendar.

The user-selected time/date placement follows the first outer `BG6` ring on
the vertical center axis: time baseline `X=355, Y=61`, date baseline
`X=361, Y=660` (shifted 6 px right for visual alignment).

The clock uses a dedicated larger live-font size (`12.3 pt`); the date keeps the
regular HUD readout size.
