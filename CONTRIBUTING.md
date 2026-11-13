# Contributing to Jarvis Assist

## Development setup

Use Python 3.11 or newer on Windows. Install the core dependencies first:

```powershell
python -m pip install -r backend/requirements-core.txt
python -m pip install -r backend/requirements-optional.txt
```

Keep local secrets in `backend/dev.env` or `backend/config/.env`; neither is
part of the repository. Do not add voice datasets, checkpoints, virtual
environments or generated logs to Git.

## Checks

```powershell
python -m compileall -q backend frontend core
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -p "test_*.py" -v
```

For changes affecting the desktop client, also run
`python frontend/launch_jarvis.py` and verify the visible behavior manually.

## Change boundaries

Keep the backend API, desktop client and voice adapters separated. Do not
replace a working voice engine or modify the active training run as part of an
unrelated UI change. Update `CHANGELOG.md` and the active handoff journal when
a change affects runtime behavior.
