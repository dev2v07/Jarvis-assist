# Runtime

- [Audits](audits/)
- [Diagnostics](diagnostics/)
- [Bug registry](bug_registry/)

Runtime reports distinguish observed behavior from blocked live acceptance scenarios.

## Regression checks

Для независимой проверки backend без импорта Knowledge/Bible из корня проекта используйте PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'backend')
backend\jarvis_env\Scripts\python.exe -m unittest -v `
  backend.tests.test_account_foundation `
  backend.tests.test_account_persistent `
  backend.tests.test_action_executor `
  backend.tests.test_agent_lifecycle `
  backend.tests.test_conversation_resolver `
  backend.tests.test_cors_policy `
  backend.tests.test_launcher_contract `
  backend.tests.test_provider_adapters `
  backend.tests.test_storage_registry `
  backend.tests.test_stt_route_selection `
  backend.tests.test_tts_routing `
  backend.tests.test_voice_runtime_isolated `
  backend.tests.test_voice_runtime_lifecycle `
  backend.tests.test_voice_status_fresh_turn
```

Эта команда проверяет runtime, voice, launcher, storage и account-контракты, но намеренно не запускает Knowledge-тесты и не читает WAV из Bible. Проверка model-acknowledgement WAV вынесена из этого набора до отдельного решения владельца о возобновлении работ с Bible.
