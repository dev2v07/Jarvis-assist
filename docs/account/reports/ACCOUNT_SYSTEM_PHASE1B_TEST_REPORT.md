# Jarvis Account System — Phase 1B test report

Дата: 2026-11-14

## 1. Account Foundation tests

Command:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest backend.tests.test_account_foundation -v
```

Result: **5 tests passed**.

Covered:

- UUIDv7 helper format/version;
- explicit `LOCAL_ONLY` context with no identity;
- rejection of fake account transition;
- read-only SQLite fixture and unchanged bytes;
- correct conversation/message/attachment/reaction/pin counts;
- orphan message and missing attachment classification;
- no absolute database path in preview/manifest;
- no duplicate manifest source IDs.

## 2. Targeted regression checks

Command:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest backend.tests.test_chat_store backend.tests.test_app_server backend.tests.test_core_contracts backend.tests.test_runtime_service -v
```

Result: **13 tests passed**.

These checks covered current ChatStore behavior, local app-server lifecycle, core contracts and runtime event/provider behavior. They used existing test fixtures/temp databases and did not start Jarvis or touch the production SQLite file.

## 3. Explicitly not run

No full suite, server, launcher, Ollama, voice runtime, migration, dependency installation, cloud service, email, database write test or production-data test was run. Phase 1B does not claim live account/auth/sync behavior.
