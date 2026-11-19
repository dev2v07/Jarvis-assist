# Jarvis — Handoff

Session-to-session context transfer. Newest entry first. This file is the short
operational handoff; the long-form historical record stays in `docs/HANDOFF.md`
(and `docs/HANDOFF_ASSIST.md`, `docs/HANDOFF_BIBLE.md`).

## Entry template

```
## YYYY-MM-DD — <short summary>
State: <what works now>
Changed: <files/areas touched>
Next: <the single most useful next step>
Risks: <what can break, what is unverified>
```

## 2026-11-17 — AI-IDE tooling and project memory
State:
- Serena (2.1.0) is available to DeepSeek Harness as `serena-jarvis`, active
  project `Jarvis`, language server status `ready`.
- Python LSP is Pyright 1.1.414 through Serena's LSP backend; repo
  `pyrightconfig.json` is used (`include`: backend, frontend, core).
- Project memory files created: `ARCHITECTURE.md`, `DECISIONS.md`, `TASKS.md`,
  `HANDOFF.md`; `AGENTS.md` and `docs/HANDOFF.md` were left unchanged.
- Serena memory index: `project_memory`.

Next:
- Pick the top item from `TASKS.md` and confirm the Pyright baseline is clean.

Risks:
- `.serena/cache/python/` symbol caches are local state; delete them if symbols
  appear stale.
- The Pyright version is pinned by Serena's `pyright_version` setting (1.1.414);
  a Pyright upgrade must be done through that setting.
