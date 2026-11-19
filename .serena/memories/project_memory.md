# Jarvis — project memory index

Durable documents for restoring context in a new session. Read this memory first,
then open only the files needed.

## Documents

- `AGENTS.md` — agent working instructions for C:\projects\Jarvis (auto-loaded by
  DeepSeek Harness; do not overwrite).
- `ARCHITECTURE.md` — concise architecture index; points at detailed docs.
- `DECISIONS.md` — dated technical decisions with rationale and status.
- `TASKS.md` — current and future work.
- `HANDOFF.md` — short session-to-session handoff (newest entry first).
- `docs/HANDOFF.md` — long-form historical handoff (very large; read in slices).
- `docs/DOCUMENTATION_REGISTER.md` — register of project documentation.
- `docs/architecture/` — audits, target design, dependency maps, migration.

## Environment facts

- Serena project name: `Jarvis`; project data in `C:\projects\Jarvis\.serena`.
- Python LSP: Pyright 1.1.414 via Serena's LSP backend; config is the repo-root
  `pyrightconfig.json` (include backend, frontend, core).
- Symbol caches live in `.serena/cache/python/`; clear them if symbols go stale.

## Rules

- Do not overwrite `AGENTS.md` or `docs/HANDOFF.md`; append history instead.
- Record new technical decisions in `DECISIONS.md` before implementing them.
- Keep this file an index: no large duplicated content.
