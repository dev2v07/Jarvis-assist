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

- secrets are supplied through environment variables;
- generated runtime state is ignored by Git;
- core and optional dependencies are listed separately;
- a local Git baseline and CI syntax check exist;
- backend and desktop frontend are manually launched after each change queue.
