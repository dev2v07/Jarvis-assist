# Jarvis Assist roadmap

This roadmap describes the state found during the 2026-11-13 release audit.
“Готово” means verified by source inspection or automated tests; it does not
claim a test that was not run.

## 1. Готово

| Задача | Состояние | Приоритет | Сложность |
|---|---|---:|---:|
| FastAPI backend and local API | Реализовано; syntax and backend tests pass | High | Medium |
| PySide6 desktop HUD and settings | Реализовано; source reviewed | High | High |
| Planner/executor/critic agent chain | Реализовано в backend | High | High |
| Voice model registry | Jarvis and temporary Silero/Kesha profile are separated | High | Medium |
| Optional camera/device capability API | Implemented with capability reporting | Medium | Medium |
| CI syntax and unit-test workflow | Present in `.github/workflows/jarvis-check.yml` | Medium | Low |

## 2. Частично готово

| Задача | Что осталось | Приоритет | Сложность | Зависимости |
|---|---|---:|---:|---|
| One-command Windows launch | Source launcher added; packaged launcher still needs build verification | Critical | Medium | PyInstaller/Qt packaging |
| Windows installer | Inno Setup recipe is prepared; compiler and installed-app test remain | Critical | Medium | Inno Setup, PyInstaller |
| Windows autostart | HKCU implementation added; reboot verification remains | High | Low | Installed build |
| Kesha/Silero voice | Adapter exists; real checkpoint/inference depends on local model and Torch | High | Medium | `ru_v3.pt`, compatible Torch |
| Own Jarvis voice | Training is active outside the public release | High | High | Clean final checkpoint and inference validation |
| Device integrations | Camera/OpenCV available; MediaPipe, printer, CAD and LAN are optional | Medium | High | Optional dependencies/hardware |

## 3. Не реализовано

- Signed installer and code-signing certificate — Critical / Medium.
- Automated installed-app smoke tests and uninstall/reboot test — Critical / Medium.
- Release upload with a GitHub Release asset — High / Low after authentication.
- Public social-preview screenshots from a verified installed build — Medium / Low.

## 4. Известные проблемы

- The repository has a large pre-existing dirty working tree; release staging
  must be allowlisted rather than blindly committing every local artifact.
- Ollama, API providers and optional voice checkpoints are local dependencies;
  the application must report their absence instead of bundling secrets/models.
- The current CORS policy is permissive for a localhost application and should
  be restricted if the backend is ever exposed beyond loopback.
- Long-running GPT-SoVITS training is not a release runtime and is intentionally
  excluded from the installer and Git repository.

## 5. Следующие обновления

1. Build and test the frozen desktop distribution and Inno Setup installer
   (Critical, Medium; depends on packaging tools).
2. Capture verified runtime screenshots and add them to `docs/images/`
   (High, Low; depends on a successful launch).
3. Restrict release staging to source/docs/config examples and push only after
   GitHub authentication is confirmed (Critical, Medium).
4. Finish and independently validate the trained Jarvis voice before adding it
   to a release (High, High; depends on the active training pipeline).

## Readiness assessment

Architecture: promising modular split, but two launch paths and optional
dependencies still need release consolidation. Stability: automated backend
checks are green; full GUI, installer, audio and reboot checks remain open.
Security: secrets are excluded by policy, but a final staged-tree secret scan
is mandatory. Distribution readiness: pre-release only until the packaged app
and installed/uninstalled lifecycle are verified.
