# Phase 1C Targeted Test Report

## Scope

Tests use temporary stores and fixtures. No real account, email, server, upload or production-history mutation is used.

Covered checks:

- separate Account store survives reopen;
- device/account/mapping/outbox persistence;
- duplicate operation id replay safety;
- retry and sent outbox states;
- unavailable auth provider never reports fake login success;
- Windows DPAPI ciphertext test when running on Windows;
- Phase 1B Local Mode, read-only SQLite adapter, inventory/preview and mapper tests;
- targeted existing ChatStore, AppServer, contracts and runtime regression tests;
- Python compilation of Account UI and modified frontend module.

Executed targeted command:

`python -m unittest backend.tests.test_account_foundation backend.tests.test_account_persistent backend.tests.test_chat_store backend.tests.test_app_server backend.tests.test_core_contracts backend.tests.test_runtime_service`

Result: **22 tests passed**. Python compilation of the Account package and modified frontend modules passed. An offscreen Qt smoke check also passed for Account Panel, login, registration, email verification and password reset construction, stable device identity across coordinator restarts, `LOCAL_ONLY`, and honest unavailable auth.

Full runtime, migrations, real auth, email, network calls and full-suite execution are intentionally outside scope. A post-test SHA-256 read of the production SQLite was not possible because the file was held by an existing process; no test or new component opens it for write.

