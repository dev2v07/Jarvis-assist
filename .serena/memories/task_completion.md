# Jarvis completion checks

- For ordinary Python changes: run python -m compileall -q backend frontend core.
- Run backend tests with PYTHONPATH=backend and python -m unittest discover -s backend/tests -p test_*.py -v.
- Include frontend contract tests when frontend code changes; use the same unittest discovery approach for frontend/tests if needed.
- For API/runtime changes, inspect the targeted endpoint/service tests and perform only bounded local smoke checks; do not claim live microphone, TTS playback, Qt visual acceptance or provider availability from static/unit checks.
- For packaging changes, run the project packaging script only after confirming required build tools and preserve build outputs separately from source.
- Before handoff, inspect git diff --check and git status --short --branch; distinguish pre-existing user changes from task changes.
- For release claims, separately verify installed EXE launch, uninstall, reboot/autostart cleanup and live device/provider behavior; README identifies these as release gates.
