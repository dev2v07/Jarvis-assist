# Jarvis — Decisions

Technical decisions with their rationale. Add one entry per decision; do not
rewrite history. Detailed design records stay in `docs/architecture/` and
`docs/`.

## Format

```
## YYYY-MM-DD — short title
Status: proposed | accepted | superseded by <entry>
Context: ...
Decision: ...
Consequences: ...
```

## 2026-11-17 — DeepSeek Harness AI-IDE integration
Status: accepted

Context: development needs semantic code intelligence, LSP diagnostics,
documentation lookup and durable project memory available to agents without
mixing project state.

Decision:
- Serena runs as the semantic-code backend with one isolated `stdio` MCP server
  per project (`--project-from-cwd`), never one shared HTTP server.
- The Python language backend is Pyright 1.1.414, launched by Serena through
  `uvx --from pyright==1.1.414 pyright-langserver --stdio`; the repo's
  `pyrightconfig.json` drives analysis.
- Project memory lives in this repository as `AGENTS.md` (auto-loaded by DSH),
  `ARCHITECTURE.md`, `DECISIONS.md`, `TASKS.md`, `HANDOFF.md`, plus Serena
  memories under `.serena/memories/`.
- Detailed historical handoff content remains in `docs/HANDOFF.md` and is not
  duplicated into the root `HANDOFF.md`.

Consequences: agents get symbol search, references, diagnostics and memory
without sharing state between projects. Adding another project means adding
another Serena MCP entry in the DSH profile, not reusing this instance.
