# Jarvis — Tasks

Current and future work. Keep this list short and current; completed items move
to the handoff or changelog rather than staying here.

## In progress

- None recorded at creation of this file.

## Next

- [ ] Verify Pyright diagnostics stay clean on `backend/` after the LSP backend
      switch (run a full `pyright` pass and record the baseline).
- [ ] Record the current symbol-cache state of `.serena/cache/python/` in the
      handoff when it changes materially.

## Backlog

- [ ] Decide whether `docs/HANDOFF.md` should be split by milestone; it is the
      largest single document in the repo.
- [ ] Keep `AGENTS.md` and `ARCHITECTURE.md` consistent when boundaries change.

## Conventions

- New technical decisions go to `DECISIONS.md` with a date and status.
- Session context handoff goes to `HANDOFF.md` (newest entry first).
- Long-form history is appended to `docs/HANDOFF.md`, not to the root file.
