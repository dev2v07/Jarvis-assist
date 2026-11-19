# Jarvis Phase 4.1 UI Recovery

Date: 2026-11-16

## Scope

This checkpoint reopens the previous PASS claims for Settings and the pinned-chat sidebar. The test used the normal launcher from `C:\projects\Jarvis` and the same desktop process that imports `frontend/jarvis_ui.py`.

## Launch verification

The command is valid:

```powershell
cd C:\projects\Jarvis
python frontend\launch_jarvis.py
```

On the test host `python` resolved to `C:\Python314\python.exe` (Python 3.14.2, PySide6 6.10.2). The launcher diagnostic confirmed the working directory and reached `before-ui-import`. One earlier attempt was rejected by an existing `Jarvis Assist/jarvis.lock`; there was no live desktop window at that point. This can make a correct command appear to do nothing.

## Settings reproduction

The opt-in trace showed the real menu path in the main process:

1. `menu.row_changed.begin`, `row=3`.
2. `ensure_full_ui.begin` and `ensure_full_ui.end`.
3. `pages.setCurrentIndex(2)` completed.
4. `menu.row_changed.end`, `result=settings`, `pages_index=2`.

The observed transition took about 0.4 seconds while `apply_styles()` ran. No worker wait, synchronous provider dialog request, or deadlock occurred on this run. The earlier PASS therefore was too broad: it proved one live path, but not all user launch states. The updated handler now also calls `ensure_full_ui()` when Settings is selected directly from the main menu, so the page cannot remain under compact widget mode.

## Pinned-chat reproduction

The trace recorded the pinned list geometry before data arrived, after data arrived, after `showEvent`, and after widget-mode restoration. It remained stable at `x=31, y=238, width=240, height=125` for the normal `1280x850` shell. The list receives an explicit layout activation and `doItemsLayout()` after chat loading, `showEvent`, widget-mode changes, and resize events.

The trace also exposed why a later activation can appear to fix the menu: the application starts with `startup_widget_mode=True`, hides the normal chrome through a queued mode transition, and Windows may issue another resize/activation pass for the frameless window. This is an ordering/visibility path, not a second chat menu or backend.

## Changes

- `frontend/jarvis_ui.py`: Settings menu selection restores the normal shell; sidebar layout and item layout are reactivated at the points where visibility, data, and native geometry change; opt-in `JARVIS_UI_TRACE` diagnostics record the relevant stages without affecting normal behavior.
- No backend, API contract, database, business logic, account, knowledge, or voice architecture was changed.

## Verification

- `py_compile` for `frontend/jarvis_ui.py` and `frontend/launch_jarvis.py`: PASS.
- Frontend tests: 20/20 PASS.
- `git diff --check`: PASS.
- Real launcher/UI process: PASS for import path, interpreter, Settings page index transition, and pinned-list geometry trace.
- Visual screenshot acceptance: BLOCKED in this environment because native-window capture timed out; accessibility exposed only the custom top-level pane. Manual owner verification is still required for pixel-level placement and the full AI navigation sequence.

## Remaining limits

The primary backend PID 1636 was left running because it is a known process on port 8000 and the task forbids stopping an existing process without a safe handoff. The prior broad bug-registry PASS is superseded by this narrower evidence; it must not be read as proof of manual visual acceptance.
