# JARVIS — актуальный runtime bug registry Jarvis

Status: CURRENT  
Last Updated: 2026-11-16
Replaces: none

Дата: 2026-11-15. Этот реестр содержит только runtime findings текущей фазы. Статические проблемы из общего аудита не дублируются без нового runtime evidence.

| ID | Priority | Status | Component | Symptom | Reproduction | Root cause / evidence | Impact |
|---|---|---|---|---|---|---|---|
| RT-001 | P1 | RESOLVED_BY_TEST | source frontend launch | старый прямой запуск не использовал проектный UI-контракт | unified launcher/import smoke | проектный venv содержит PySide6; штатный launcher и import smoke проходят | прямой legacy command не является поддерживаемым entrypoint |
| RT-002 | P2 | CONFIRMED | QtWebEngine/display | GLES3 errors и fallback GLES2 | start UI with `C:\Python314\python.exe` | `Failed to create GLES3 context`, `ContextResult::kFatalFailure` | возможны rendering/capture regressions |
| RT-003 | P2 | CONFIRMED | visual acceptance | screenshot не получен | two live `get_window_state(...include_screenshot=true)` calls | `FrameArrived/window capture timed out` | HUD geometry and visual state cannot be accepted |
| RT-004 | P2 | RESOLVED_BY_TEST | conversational library | sleep/context phrases previously missed local intent | ConversationResolver regression tests and isolated voice path | local resolver handles initial sleep question, contextual follow-up and user-tired response | no current defect reproduced |
| RT-005 | P1 | PASS / BASELINE | VoiceRuntime/STT | live Minifuse speech baseline | user-supervised short phrase through the selected route | `хочешь спать` was recognized through `vosk-silero`, routed to ConversationResolver, answered and persisted in isolated chat; no raw audio retained | broader multi-turn/unknown-question acceptance remains separate |
| RT-006 | P1 | PASS | Fish/TTS | Fish voice and playback | штатный `voice_engine.tts.speak(..., model_id="fish_jarvis")` plus owner confirmation | valid Fish RIFF WAV; playback completed; device released; owner confirmed audible result; no XTTS fallback | none for this acceptance path |
| RT-007 | P3 | RESOLVED_BY_TEST | knowledge integrity | readiness previously overstated partial audio | `/knowledge/integrity` and regression test | `PARTIAL` is returned with `ok=false`, `ready=false`; paths now point to canonical Bible | status contract is honest |
| RT-008 | P2 | MITIGATED | runtime environment | historical backend/UI interpreter mismatch | launcher diagnostics and project venv smoke | supported launcher uses project Python 3.11; stale external listeners remain outside task lifecycle | old listener requires planned restart window |
| RT-009 | P1 | PASS / ISOLATED | chat flow | dynamic response/history path required current acceptance evidence | `POST /chat` on task-owned `127.0.0.1:18083` with temporary SQLite and `chat_id=phase4-ollama-test` | `planner → executor → critic → chat`; exactly user + assistant rows; `qwen3:8b` selected; 2491 ms | production chat remains untouched; live voice-to-Ollama path is tracked separately |

## Evidence locations

- Frontend first-launch stderr: `%TEMP%\jarvis-phase2\frontend.stderr.log`.
- Frontend Python 3.14 stderr: `%TEMP%\jarvis-phase2\frontend314.stderr.log`.
- Live API: `127.0.0.1:8000`.
- Exact call-chain and status details: [JARVIS_RUNTIME_ACCEPTANCE_REPORT.md](../../testing/acceptance/JARVIS_RUNTIME_ACCEPTANCE_REPORT.md).

## Scope classification

- `CONFIRMED`: directly observed in the current runtime or returned by a current API.
- `LIKELY`: strong architectural/runtime inference but not isolated by a dedicated reproducer.
- `BLOCKED`: test would violate the no-data-change/no-side-effect boundary.
- `NOT_REPRODUCED`: intentionally not executed or no failure observed.

## Phase 3 disposition — 2026-11-15

| ID | Status after Phase 3 | Evidence |
|---|---|---|
| RT-001 | RESOLVED_BY_TEST | Project venv contains PySide6 6.10.2; frontend import succeeds; unified launcher documented. |
| RT-004 | RESOLVED_BY_TEST | ConversationResolver tests cover initial sleep question, contextual follow-up and user-tired response. |
| RT-007 | RESOLVED_BY_TEST | Integrity test and live service call return `status=PARTIAL` for partial audio groups. |
| RT-008 | MITIGATED | UI dependencies are installed in the project venv; an already-running UI/backend was not replaced. |
| RT-010 | RESOLVED_BY_TEST | ChatStore connection context now commits/rolls back and closes; isolated temp SQLite test passes with `-W error::ResourceWarning`. |
| RT-011 | RESOLVED_BY_TEST | Windows power actions require explicit confirmation and use argument lists; no real power command executed. |
| RT-002/RT-003 | OPEN | GLES3/capture limitations remain environment/runtime acceptance blockers. |
| RT-005 | PARTIAL | Minifuse/VAD/STT evidence exists; complete live conversational acceptance still needs a controlled user phrase. |
| RT-006 | PASS | Fish inference, technical playback and owner-confirmed audible result pass. |

Phase 3 regression command completed with **56/56 PASS**.

## Phase 3.1 live runtime disposition — 2026-11-15

| ID | Status | Priority | Evidence |
|---|---|---|---|
| RT31-001 | CONFIRMED | P2 | Existing listener `/knowledge/integrity` still returns legacy `ok=true` without Phase 3 `status`; partial audio counts remain visible. |
| RT31-002 | CONFIRMED | P2 | Launcher invoked from project venv produced UI child owned by system Python 3.11. |
| RT31-003 | CONFIRMED | P2 | Real HUD screenshot capture timed out again. |
| RT31-004 | CONFIRMED | P2 | QtWebEngine GLES3 virtualization fallback reproduced in launcher stderr. |
| RT31-005 | CONFIRMED | P1 | Fish `fish_jarvis` is available by configuration but `ready=false`, `inference_verified=false`. |
| RT31-006 | BLOCKED | P1 | Human speech → STT and audible TTS playback were not accepted in this controlled run. |
| RT31-007 | PASS | — | Real Minifuse input produced 74 callbacks/75,776 bytes; isolated VoiceRuntime entered Silero VAD and stopped cleanly. |

Detailed evidence is in [JARVIS_PHASE3_1_LIVE_RUNTIME_ACCEPTANCE.md](../../testing/acceptance/JARVIS_PHASE3_1_LIVE_RUNTIME_ACCEPTANCE.md).

## Phase 3.2 disposition — 2026-11-15

| ID | Status | Priority | Evidence |
|---|---|---|---|
| RT32-001 | RESOLVED_BY_TEST | P2 | `JARVIS_API_PORT` and `JARVIS_STATE_DB_PATH` now isolate backend port and SQLite; 18081 returned current `integrity.status=PARTIAL`. |
| RT32-002 | RESOLVED_BY_TEST | P2 | UI endpoints use configurable `API_ROOT`; default remains 8000. |
| RT32-003 | RESOLVED_BY_TEST | P3 | Launcher diagnostic confirms venv `sys.executable`/`sys.prefix`; Windows child image observation is venv redirector behavior. |
| RT32-004 | PASS / BASELINE | P1 | Minifuse/VAD/STT real phrase baseline passed; full multi-turn and Ollama voice acceptance remains separate. |
| RT32-005 | PARTIAL | P1 | Fish inference and technical playback pass; physical hearing confirmation remains manual. |
| RT32-006 | OPEN | P2 | HUD screenshot capture still times out; GLES3 fallback remains. |
| RT32-007 | BLOCKED | P2 | UI-to-isolated-backend repeat was blocked by terminal launch policy; source binding changes compile and backend isolation is verified separately. |

Detailed Phase 3.2 evidence: [JARVIS_PHASE3_2_STABILIZATION_REPORT.md](../../testing/acceptance/JARVIS_PHASE3_2_STABILIZATION_REPORT.md).

## Architecture audit — 2026-11-15

### ARCH-001 — duplicate knowledge service graph in normal backend

- Status: **FIXED / VERIFIED**
- Severity: P2 architectural duplication
- Cause: `backend/main.py` and `VoiceRuntime.__init__` each constructed their own `LocalResponseService` and `KnowledgeSearchService` over the same physical sources.
- Change: `VoiceRuntime` accepts the composition-root service; direct construction keeps a test fallback.
- Evidence: targeted `py_compile`; backend suite `56/56 OK` with `ResourceWarning` treated as errors.
- Data impact: none. No database, WAV, knowledge root, configuration or secret changed.

### ARCH-002 — multiple physical knowledge roots

- Status: **CONFIRMED / MIGRATION REQUIRED**
- Impact: `offline_knowledge`, `knowledge3` and `voice_responses` can look like competing libraries even though the current `KnowledgeSearchService` is the logical facade.
- Decision: do not move/delete data. Define a canonical Bible catalog/adapters layer first; see `JARVIS_TARGET_ARCHITECTURE.md` and `JARVIS_MIGRATION_PLAN.md`.

### ARCH-003 — Vosk and faster-whisper/Silero coexist

- Status: **CONFIRMED / NOT A BUG BY ITSELF**
- Cause: faster-whisper + Silero are the preferred live path; Vosk is an explicit VoiceRuntime fallback and a separate UI dictation adapter.
- Decision: keep temporarily. A common STT adapter and live comparative acceptance are required before deprecation.

### ARCH-004 — Account local/cloud split

- Status: **CONFIRMED / INTENTIONAL BOUNDARY**
- Cause: local account/device/session metadata is stored separately from cloud PostgreSQL account/auth state.
- Decision: unify logical contracts and sync semantics; do not merge or delete `account_state.sqlite3` or PostgreSQL.

## Phase 4 implementation disposition — 2026-11-15

### PH4-VOICE-001 — duplicate acknowledgement before command WAV

- Status: **FIXED / VERIFIED**
- Priority: P2
- Symptom: a command could first match the local `ack` class and then execute the same `ResponseRouter` command, causing two playback paths.
- Root cause: `VoiceRuntime._handle_transcript()` called `LocalResponseService.match(..., {"ack"})` before routing the request.
- Change: command routing is now the single decision point; command feedback uses the existing command WAV/action path.
- Test: `test_command_route_does_not_play_ack_before_command_wav` plus full suite.

### PH4-VOICE-002 — transcript deduplication was not chat-scoped

- Status: **FIXED / VERIFIED**
- Priority: P1 data-integrity risk
- Symptom: the same spoken text in a second active chat could be skipped because deduplication remembered only the text.
- Root cause: `_last_persisted_transcript` was a plain string rather than `(chat_id, text)`.
- Change: deduplication key is now chat-scoped; identical text in different chats is persisted independently.
- Test: `test_same_transcript_is_persisted_when_chat_id_changes`.

### PH4-VOICE-003 — voice state map updated

- Status: **DOCUMENTED / VERIFIED BY TESTS**
- The project map now records the single command route and chat-scoped persistence. No new production module, database or physical Knowledge root was introduced.

### PH4-KNOWLEDGE-001 — integrity `ok` overstated partial readiness

- Status: **FIXED / VERIFIED**
- Priority: P2
- Cause: `KnowledgeIndexService.integrity()` used `ok` as a structural-error flag, while callers interpreted it as full readiness.
- Change: `ok` and `ready` are now true only for aggregate `status=READY`; `PARTIAL` remains HTTP 200 but is explicitly not ready. The returned offline root now points to the actual directory.
- Evidence: fresh isolated backend on `127.0.0.1:18081` returned `ok=false`, `ready=false`, `status=PARTIAL`; integrity regression test passes.

### PH4-KNOWLEDGE-002 — physical knowledge roots lacked one canonical registry

- Status: **MITIGATED / VERIFIED (logical cutover)**
- Priority: P1 architectural
- Change: added read-only `data/Bible/index/catalog.json` as the canonical source registry and switched `KnowledgeSearchService` path resolution to it. Existing roots and WAV files remain untouched until a separately verified physical cutover.
- Evidence: 14 Knowledge tests and fresh `/knowledge/answer` smoke test pass.
- Remaining: physical relocation/deduplication of 5,782 WAV and source files requires a staged copy/verification/cutover window.

### PH4-RUNTIME-001 — launcher could kill an incompatible listener

- Status: **FIXED / VERIFIED BY STATIC CHECK**
- Priority: P1 safety/runtime
- Cause: `frontend/launch_jarvis.py` used `taskkill /PID /T /F` when port 8000 answered with an older API contract.
- Change: launcher now reports the occupying PID and exits without stopping it; an explicitly isolated test port remains supported through `JARVIS_API_PORT`.
- Verification: launcher compiles; no `taskkill` call remains in the source path.

### PH4-RUNTIME-002 — backend shutdown did not deterministically release agent tasks

- Status: **FIXED / VERIFIED**
- Priority: P2 runtime stability
- Cause: `main.py` started agents without a shutdown hook; `Agent` did not cancel its optional lifecycle task or clear task ownership.
- Change: added FastAPI shutdown cleanup for voice runtime and agents; `Agent.stop()` now cancels and clears both main and lifecycle tasks.
- Evidence: `test_stop_cancels_main_and_lifecycle_tasks` and `py_compile` pass.

Full regression suite after this change: **60/60 PASS** with `ResourceWarning` treated as errors.

### PH4-ACCOUNT-001 — Account Server dependencies missing from project venv

- Status: **FIXED / VERIFIED (imports and unit tests)**
- Priority: P2 account/runtime
- Cause: `SQLAlchemy`, `cryptography` and the native Argon2 binding required by the declared Account Server requirements were absent from the common Python 3.11 environment.
- Change: installed the exact declared versions where pinned and recorded the missing runtime dependencies in `backend/account_server/requirements.txt`.
- Evidence: Account Server suite imports and runs: **10 tests, 3 PASS, 7 SKIPPED** only because isolated PostgreSQL/local Account API is not configured; local Account tests **9/9 PASS**.

### PH4-ACCOUNT-002 — Account Server PostgreSQL resources were not deterministically disposed

- Status: **FIXED / VERIFIED**
- Priority: P2
- Cause: the SQLAlchemy engine created by `build_session_factory()` had no explicit application shutdown disposal, and test-created factories could retain pooled psycopg connections.
- Change: the factory now retains its engine, `create_app()` disposes it on FastAPI shutdown, and isolated test fixtures dispose their own factories.
- Evidence: isolated PostgreSQL Account Server suite **10/10 PASS** with `-W error::ResourceWarning`; no ignored connection warnings remain.

### PH4-ACCOUNT-003 — `email.py` shadowed Python's standard library package during Alembic execution

- Status: **FIXED / VERIFIED**
- Priority: P2
- Cause: invoking Alembic from `backend/account_server/` put the local `email.py` ahead of the standard library, breaking `email.utils` imports.
- Change: renamed the project module to `email_provider.py`, updated all imports/tests, and made Alembic's `env.py` add the backend package root independently of the current directory.
- Evidence: isolated PostgreSQL Alembic `upgrade head` succeeds when run from `backend/account_server/`; `py_compile` passes.

### PH4-KNOWLEDGE-003 — physical Bible cutover used separate legacy roots at runtime

- Status: **FIXED / VERIFIED (runtime cutover)**
- Priority: P1 architectural
- Cause: the canonical catalog existed, but active services still resolved several catalogs and response/audio paths directly from `data/offline_knowledge`, `data/knowledge3` and `data/voice_responses`.
- Change: staged a copy-only migration into `data/Bible/materials` and `data/Bible/audio`; generated `physical_manifest.json`; rewrote 4,221 copied JSON references; switched `KnowledgeSearchService`, `KnowledgeIndexService`, `LocalResponseService`, `OfflineKnowledgeService` and specialized knowledge services to canonical paths.
- Evidence: 5,833 source files mapped to 5,832 canonical files, 0 broken/hash-mismatched targets; `/integrity` reports canonical Bible roots with `status=PARTIAL` due real audio readiness, not path errors; full backend suite **60/60 PASS**.
- Rollback: originals remain in place and are not deleted; offline/voice and Knowledge 3 generator/index/validation tools use Bible. Read-only WAV audit and historical helper scripts retain legacy aliases for analysis/rollback only.

### PH4-STORAGE-001 — storage ownership was implicit and migration safety gate was missing

- Status: **MITIGATED / VERIFIED**
- Priority: P2 architecture/data safety
- Symptom: local databases had separate owners, but no single code-level registry or repeatable backup/rollback gate described that boundary.
- Root cause: paths were distributed across config, AccountCoordinator, ChatStore and audit scripts.
- Change: added `backend/services/storage_registry.py` and exported `STORAGE_PATHS`; added `backend/scripts/storage_migration_harness.py` using read-only SQLite Online Backup API, integrity checks, physical snapshots and logical dump hashes for idempotence.
- Evidence: all four discovered SQLite stores copied and verified on isolated targets; storage tests **2/2 PASS**; full backend suite **62/62 PASS** with `ResourceWarning` as errors.
- Decision: no physical DB merge was performed; the four stores remain bounded contexts pending a separate fixture-based logical migration design.

### PH4-VOICE-004 — Fish Jarvis default/inference state was previously unverified

- Status: **VERIFIED / CLOSED**
- Priority: P1 voice acceptance
- Evidence: `fish_jarvis` is the default selected profile; one controlled Fish Audio inference returned a valid WAV (163884 bytes, 44.1 kHz), and technical playback completed on Minifuse output device 4.
- Runtime status after inference: `ready=true`, `inference_verified=true`.
- Guard: `test_fish_profile_does_not_fallback_to_local_xtts` confirms that the Fish profile does not silently route to local XTTS.
- Limitation: subjective human hearing confirmation remains a user-observation step.

### PH4-VOICE-005 — STOP left a conversation control sentinel queued

- Status: **FIXED / VERIFIED**
- Priority: P2 runtime stability
- Symptom: after a real isolated `/voice/stop`, `conversation_worker=false` but `conversation_queue_size=1`.
- Root cause: the worker could exit after observing `_stop` while its sentinel remained in the bounded queue.
- Change: `VoiceRuntime.stop()` now drains control items after the worker join; subsequent starts cannot inherit stale queue state.
- Evidence: isolated lifecycle regression passes; full backend suite **64/64 PASS**. Live isolated API probe entered `слушаю (Silero VAD)` on Minifuse and stopped cleanly.

### PH4-UI-001 — local file-based UI polling was rejected by CORS

- Status: **FIXED / VERIFIED**
- Priority: P1 UI/runtime integration
- Symptom: live QWebEngine console reported `fetch ... /api/messages ... origin 'file://' ... blocked by CORS policy`.
- Root cause: FastAPI CORS allow-list covered HTTP localhost origins but not the explicit local file origin used by the desktop chat asset.
- Change: added exact `file://` to the allow-list; wildcard origins remain disallowed.
- Evidence: isolated backend preflight for `Origin: file://` returned HTTP 200 with `Access-Control-Allow-Origin: file://` and `GET, POST, OPTIONS`; regression test added.
- Related environment warning: QtWebEngine also logged GLES3 virtualization fallback; this remains separately classified and was not bypassed with insecure Chromium flags.

### PH4-VOICE-006 — faster-whisper route aborts the backend through native OpenMP conflict

- Status: **CONFIRMED / ROUTE MITIGATED**
- Priority: P1 voice runtime
- Symptom: the live Silero + faster-whisper route entered recognition and then the backend disappeared before producing a transcript.
- Root cause: an isolated faster-whisper probe terminated with `OMP: Error #15` because `libiomp5md.dll` and `libomp140.x86_64.dll` were initialized in the same process. This is a native runtime abort, not a recoverable Python exception.
- Change: the default live route is now `vosk-silero`: Silero VAD segments speech and Vosk transcribes each utterance. faster-whisper remains opt-in through `JARVIS_STT_ENGINE` for a separately isolated compatibility test.
- Evidence: `test_stt_route_selection.py` passes; live Minifuse test produced transcript `хочешь спать` and a contextual response without the OpenMP abort.
- Remaining: faster-whisper is not accepted as the production route until its native runtime isolation is proven.

### PH4-VOICE-007 — conversational Knowledge answer could bypass the selected Fish voice

- Status: **FIXED / VERIFIED BY REGRESSION TEST**
- Priority: P1 voice consistency
- Symptom: when a Knowledge result contained a linked legacy `audio_path`, a conversational answer could play that WAV instead of the selected `fish_jarvis` TTS provider.
- Root cause: conversational response handling treated linked Knowledge audio like a deterministic command acknowledgement.
- Change: conversational Knowledge answers now always enter the selected TTS queue (Fish for `fish_jarvis`); linked WAV metadata remains available for audit. Deterministic command WAVs remain a separate explicit route.
- Evidence: `test_voice_knowledge_tts.py` verifies that a linked Knowledge WAV cannot replace the selected TTS path; direct Fish inference had already produced a valid WAV and technical playback completed.

### PH4-UI-002 — HUD response field showed the previous turn while the current turn was pending

- Status: **FIXED / VERIFIED BY REGRESSION TEST**
- Priority: P2 UI/runtime observability
- Symptom: the HUD displayed the new recognized transcript together with the previous answer, which made it look as if the current request had received the old response.
- Root cause: `VoiceRuntime` stored only one `last_response` value and did not clear it when a new transcript entered the queue. The UI correctly polled `/voice/status`, but had no distinct pending-turn value to display.
- Change: a new transcript clears `last_response` and `last_error` before queueing; the UI now maps `conversation request:` failures to a bounded model-error label.
- Evidence: `test_voice_status_fresh_turn.py`; full backend suite **69/69 PASS**.

### PH4-LLM-001 — Ollama voice fallback could exceed the request timeout and trigger an unrelated WAV

- Status: **CONFIRMED / FAILURE PATH CORRECTED; PROVIDER BLOCKER REMAINS**
- Priority: P1 voice conversation
- Symptom: the spoken transcript was persisted, but `qwen3:8b` did not return within the configured 45-second request timeout. The old exception path played an unrelated “flight simulation” WAV.
- Root cause: the Ollama request timed out while the active local model/runtime was unavailable or still loading; the voice exception handler treated the failure as TTS and emitted a canned command audio response.
- Change: failed conversational model requests now leave no stale or unrelated response and expose a bounded `conversation request: <error-type>` diagnostic. The UI shows “Не удалось получить ответ от модели”.
- Evidence: live UI/backend run: transcript `объясни квантовая запутанность простыми словами` was saved to the isolated chat; backend logged `ollama request failed: ReadTimeout`; no valid assistant answer was produced.
- New evidence: after the competing runtime released Ollama, a direct `qwen3:8b` request returned HTTP 200 in 15.67 s cold (about 15.16 s model load), and a second warm request returned HTTP 200 in 0.46 s. This confirms a cold-start latency component, while the full microphone-to-Fish-ack-to-model live turn remains unaccepted.
- Live startup evidence after the numeric `keep_alive` fix: backend logged `Ollama warmup: ready qwen3:8b`, an isolated unknown-question route returned HTTP 200 in 2.98 s, and `ollama ps` reported `Forever`.
- Remaining external condition: an end-to-end free-question response through the live UI/voice path still needs a controlled runtime acceptance run; the prior live run itself ended in `ReadTimeout`.

### PH4-VOICE-008 — model-wait acknowledgement WAV set was initially blocked

- Status: **FIXED / VERIFIED**
- Priority: P2 voice UX
- Requirement: when a request bypasses Bible and enters Ollama, play one short Fish acknowledgement chosen from seven variants before the model response.
- Change: added canonical acknowledgement catalog, non-overwriting resumable Fish generator, and runtime selection without a second network request. Local Bible answers do not trigger the acknowledgement.
- Evidence: `test_model_acknowledgements.py` passes; all seven canonical files now exist under `data/Bible/audio/voice_responses/model_ack/` and `soundfile` validates them as mono 44100 Hz WAV, 1.25–1.90 seconds.
- Historical blocker: the first controlled run failed intermittently with `SSLEOFError`/provider runtime errors. Safe resumable retries completed the missing files without overwriting existing WAVs.
- Safety: no fallback voice or fabricated WAV was used; Fish Audio generated every file.

### PH4-LLM-002 — voice route warmed and retried Ollama concurrently with the user turn

- Status: **FIXED / VERIFIED BY REGRESSION SUITE**
- Priority: P2 latency
- Cause: the first voice start launched a background Ollama warmup, while the first user request could start independently; voice requests also inherited the general retry count.
- Change: automatic voice-start warmup was removed; voice model turns use one Ollama attempt and a shorter spoken budget (`num_predict=48`, stories remain 96).
- Expected result: no duplicate model work before the first answer and no repeated 45-second waits for the same failed voice turn.
- Evidence: full backend suite **71/71 PASS**, py_compile PASS, and direct Ollama timing after release: 15.67 s cold / 0.46 s warm for short `qwen3:8b` requests. The live microphone-to-model route still requires a separate acceptance run.

### PH4-UI-003 — «Устройства и возможности» открывались поверх прозрачного widget-режима

- Status: **FIXED / VERIFIED**
- Priority: P2 UI/runtime integration
- Symptom: переход из компактного HUD открывал страницу устройств без восстановления обычного интерфейса; прозрачный widget-слой оставался видимым.
- Root cause: кнопка вызывала `open_settings_section(12)` напрямую, а общий переход `ensure_full_ui()` не выполнялся.
- Change: `open_settings_section()` теперь идемпотентно выводит окно из `widget_mode` перед выбором раздела.
- Evidence: isolated Qt smoke test confirmed `widget_mode=False`, `pages.currentIndex()==3` and `settings_nav.currentRow()==12`; owner manually accepted the fix in the live UI.

### PH4-UI-004 — fullscreen/window transition could retain compact widget presentation

- Status: **FIXED / VERIFIED**
- Priority: P2 UI/runtime state
- Symptom: fullscreen/window state and the compact presentation could become inconsistent after a mode transition.
- Root cause: the toggle relied on a separate `_fullscreen_mode` flag and did not force an application-shell transition from widget mode.
- Change: the toggle now uses `isFullScreen()`, preserves normal geometry, exits widget mode before fullscreen, and synchronizes the flag/tooltip on `WindowStateChange`.
- Evidence: isolated Qt smoke test passed `widget → fullscreen → window`; owner manually accepted the fix in the live UI.

### PH4-UI-005 — lower HUD cell clicks could be swallowed by decorative layers in widget mode

- Status: **FIXED / VERIFIED BY SMOKE; MANUAL ACCEPTANCE PENDING**
- Priority: P2 UI interaction
- Symptom: clicks near the lower icon, especially outside the glyph, were intermittently ignored in transparent widget mode.
- Root cause: the event could be delivered to a decorative HUD child; the previous fallback covered only a limited release radius.
- Change: application-level press routing now maps the full rectangular cell to the nearest lower panel and consumes the matching release to avoid duplicate actions. Real buttons and START/TECH-A children are excluded.
- Evidence: Qt smoke test clicked outside the native button rectangle and received the `OUT` action (`WIDGET_EDGE_CELL_CLICK=PASS`). A physical mouse check on the live desktop is still required before closing the manual acceptance gap.

### PH4-UI-006 — lower HUD hitbox still required precise aiming after fallback routing

- Status: **FIXED / VERIFIED BY SMOKE; MANUAL ACCEPTANCE PENDING**
- Priority: P2 UI interaction
- Symptom: the first fallback improved widget-mode clicking, but the owner still had to aim too precisely at some lower icons.
- Root cause: the native cell remained `68x56`, and overlapping child widgets could win by z-order before the nearest-cell fallback.
- Change: lower cells are now `84x68` with preserved visual centers (`anchor offsets 22/18`); ordinary widget-mode press routing resolves the nearest cell before lower-button child z-order. START and TECH-A controls remain excluded; calibration drag mode is preserved.
- Evidence: isolated Qt smoke test clicked at `45x35` from the icon center, outside the old `68x56` rectangle, and received `OUT`; runtime geometry reported `84x68`. Manual physical verification of the newly restarted UI remains open.

### PH4-LLM-003 — warm qwen3:8b text route acceptance

- Status: **VERIFIED / TEXT PATH ONLY**
- Priority: P2 latency/runtime acceptance
- Scope: isolated text chat path; this does not close the separate human speech/STT/TTS playback acceptance gap.
- Evidence: one unknown-question request on task-owned `127.0.0.1:18083` completed in `2.491 s`; isolated history contained exactly one new `user,assistant` pair; runtime events reached `turn.completed`; `/runtime/providers` selected `ollama`/`qwen3:8b`; `ollama ps` reported `qwen3:8b` with `Forever` keep-alive. A direct warm adapter probe with `think=false` completed in `571 ms`.
- New evidence: isolated `VoiceRuntime` turn with synthetic transcript reached `route=ollama`, stored exactly `user + assistant` under one test `chat_id`, and generated a real Fish RIFF artifact for the assistant response. Timing: Knowledge 407.7 ms, Ollama/model 1768.7 ms, response ready 1782.5 ms.
- Remaining: run the same provider through the real microphone → STT path and confirm audible playback of this exact unknown-question response; synthetic transcript is not a substitute for human speech.

### PH4-UI-007 — calibrated top HUD labels could resolve by z-order in overlap zones

- Status: **FIXED / VERIFIED BY SMOKE; MANUAL VISUAL CHECK PENDING**
- Priority: P2 UI interaction
- Symptom: after manual label calibration, neighboring top-panel hitboxes overlapped; a click in the shared area could activate whichever button was highest in Qt z-order.
- Root cause: global routing covered lower cells, while top-panel clicks were left to overlapping child hitboxes.
- Change: ordinary widget-mode routing now includes top panels and chooses the nearest calibrated center. Coordinates, angles and font sizes remain unchanged; drag calibration is preserved.
- Evidence: isolated Qt smoke test clicked in the `CHAT/AGENTS` overlap zone and resolved to nearest `CHAT` (`TOP_OVERLAP_ROUTE=PASS`).

### PH4-VOICE-009 — live voice latency source was not observable

- Status: **DIAGNOSTIC INSTRUMENTATION ADDED / LIVE TIMING ACCEPTANCE PENDING**
- Priority: P1 voice UX
- Symptom: a local-library answer such as `что нового` was perceived as slow, while the source of the delay could not be separated between VAD/STT, Knowledge resolution and Fish playback.
- Evidence: isolated live history recorded `что нового` → `Нового пока ничего. Какие-то обновления в работе, но всё в порядке.`; the turn did not use Ollama. The last session ended with `enabled=false`, `listening=false`, queue `0`, and no active session. The selected profile remained `fish_jarvis`; the final Fish request reported a transient `SSLEOFError`.
- Change: `VoiceRuntime.status()` now exposes bounded `last_turn_metrics` for route, Knowledge lookup, model/ACK and TTS queue timings; no audio or sensitive content is stored.
- Change: production `vosk-silero` endpoint silence threshold reduced from 24 to 16 blocks (~768 ms → ~512 ms) to reduce post-speech latency; faster-whisper diagnostic threshold was not changed.
- Remaining: repeat one live local-answer turn and one live unknown-question turn with the UI visible, then record separate VAD/STT, Knowledge/Ollama and Fish timing. Standard Fish playback has since been confirmed audible by the owner; the exact unknown-question voice turn remains unaccepted.
- New evidence: a fresh isolated backend on `127.0.0.1:18082` with the updated source passed `/health`; warmed `qwen3:8b` handled an unknown text question in 2683 ms with one response. This validates the updated text provider path only; no claim is made for live voice or audible playback.

- Status: **FIXED / REGRESSION VERIFIED; LIVE INFERENCE PASS**
- Priority: P1 voice status integrity
- Cause: `VoiceModelManager` retained an earlier successful `_fish_verified` flag when a later Fish request failed with `SSLEOFError`.
- Change: failed Fish inference now clears the profile's verified flag. The selected profile stays `fish_jarvis`; no XTTS fallback is activated.
- Expected result: `ready` and `inference_verified` reflect the latest verified state rather than stale historical success.
- Evidence: targeted `test_tts_routing.py` verifies the failed-inference reset while preserving selected `fish_jarvis`; full suite passes 73/73 with `-W error::ResourceWarning`.
- Additional evidence: TCP/443 and HTTPS GET to `api.fish.audio` succeed, while POST `/v1/tts` fails at TLS handshake with `SSLEOFError` in the current environment. Fish request timeout is now bounded by `JARVIS_FISH_TTS_TIMEOUT` (default 20 seconds, clamped 5–90); no alternate voice is used.

### PH4-UI-008 — fullscreen captured the desktop surface instead of embedding as a normal window

- Status: **FIXED IN SOURCE / LIVE UI PENDING**
- Priority: P2 UI usability
- Cause: the toggle and `--fullscreen` launch path used Qt `showFullScreen()`, which creates a borderless exclusive-looking surface and interferes with opening the Windows Start menu.
- Change: both paths now use `showMaximized()`; state detection accepts maximized windows and preserves the normal geometry for restore.
- Remaining: restart the isolated UI and manually verify Start menu/taskbar interaction.

### PH4-UI-009 — fullscreen sidebar showed only three recent chats

- Status: **FIXED IN SOURCE / LIVE UI PENDING**
- Priority: P3 UI layout
- Change: maximized mode now uses a 320 px recent-chat list and loads up to eight recent sessions; normal mode remains limited to three.

### PH4-UI-010 — Tandem Marketing footer text was clipped

- Status: **FIXED IN SOURCE / LIVE UI PENDING**
- Priority: P3 UI layout
- Change: footer label now wraps and receives 280 px width/34 px height in maximized mode, while retaining the existing link and text.

### Phase 4 current verification snapshot — 2026-11-15

- Backend regression suite: **73/73 PASS**.
- Qt sidebar smoke: **PASS** for 8-row fullscreen layout dimensions and normal-mode restoration.
- UI live acceptance of Start menu/taskbar, visible eight recent chats and untruncated footer: **PENDING**, because the currently running UI was not forcibly terminated or replaced.

Owner decision: manual UI interaction and subjective audible-playback confirmation may be skipped for this completion pass. These scenarios remain **SKIPPED/NOT TESTED**, never PASS. Technical voice acceptance remains open where it requires a new Fish inference or a live voice → Ollama route.

### PH4-VOICE-010 — Fish readiness remained true after failed current inference

- Status: **FIXED / REGRESSION VERIFIED**
- Priority: P1 voice status integrity
- Cause: a previous successful `_fish_verified` flag survived a later Fish `SSLEOFError`.
- Change: failed Fish inference clears the profile verification flag while keeping `fish_jarvis` selected and never activating XTTS.
- Evidence: targeted Fish routing suite 2/2 PASS; full backend suite 73/73 PASS with `-W error::ResourceWarning`.

### PH4-KNOW-005 — mutable Knowledge state still wrote into legacy roots

- Status: **FIXED / REGRESSION VERIFIED**
- Priority: P1 Knowledge consolidation
- Symptom: source materials were served from Bible, but rotation/progress/session/snapshot state still pointed to `data/voice_responses` or `data/knowledge3`.
- Change: mutable state now uses `data/Bible/index/runtime`; old files are read-only fallback sources and are not overwritten.
- Evidence: `test_bible_runtime_paths.py` PASS for local response, variant state, voice sessions, programming progress and DAW snapshots.
- Full evidence: backend regression suite **75/75 PASS** with `-W error::ResourceWarning`.

### PH4-KNOW-006 — Bible still exposed three physical source roots

- Status: **FIXED / PHYSICAL CONSOLIDATION VERIFIED**
- Priority: P1 Knowledge consolidation
- Cause: the first migration was intentionally `copy-only`, preserving `offline_knowledge`, `knowledge3` and `voice_responses` plus their Bible source mirrors for rollback.
- Change: added the single human-facing `data/Bible/index/library_catalog.json` (727 records), domain views under `data/Bible/knowledge/`, a Russian `data/Bible/README.md`, and the reversible `backend/knowledge/apply_bible_physical_consolidation.py` migration gate.
- Evidence: SHA-256 verification of 5,833 canonical files PASS; dry-run plan PASS; `test_bible_physical_consolidation.py` PASS; full backend suite **76/76 PASS** with `-W error::ResourceWarning`.
- Evidence update: the three top-level legacy roots are now archived at `data/archive/bible_legacy_sources_20261115`; active backend canonical mirrors remain under `data/Bible/materials` and `data/Bible/audio` until a controlled restart.
- Evidence update: the six Bible mirror moves were applied; active `Bible/materials` was removed, active materials now live under `Bible/sources`, audio under `Bible/audio/library` and `Bible/audio/responses`, and the old roots remain only in `data/archive/bible_legacy_sources_20261115`.
- Verification: manifest status `PHYSICALLY_CONSOLIDATED`, 5,833 source files / 5,832 unique canonical files, planned moves 0, fresh backend read-only smoke PASS, full suite **76/76 PASS**.

### PH4-KNOW-007 — archive-era directory aliases could fall back to removed roots

- Status: **FIXED / REGRESSION VERIFIED**
- Cause: empty directories such as `coding_projects` have no file records in the physical manifest; after archiving the source roots, exact file mappings alone were insufficient.
- Change: cached Bible resolver now handles manifest file mappings and active `materials`/`sources` directory aliases, including empty directories; manifest statuses with records remain active.
- Evidence: direct resolver/integrity smoke PASS; full backend suite **76/76 PASS** with `-W error::ResourceWarning`.

### PH4-KNOW-008 — human Bible catalog did not cover the full API catalog

- Status: **FIXED / REGRESSION VERIFIED**
- Cause: the first human-facing generator listed only 727 parent records while `KnowledgeSearchService.catalog()` exposed 7,250 records through the API.
- Change: `backend/knowledge/build_bible_catalog.py` now builds `data/Bible/index/library_catalog.json` and `data/Bible/knowledge/*` directly from the unified `KnowledgeSearchService.catalog()` result.
- Evidence: `library_catalog.json` contains `record_count=7250`; domain views are generated from the same record list; `test_knowledge_variations.py` 14/14 PASS; physical Bible smoke and full suite remain green.

### PH4-KNOW-009 — Bible user navigation exposed provenance namespaces as parallel libraries

- Status: **FIXED / REORGANIZED WITH ROLLBACK**
- Cause: after physical consolidation, `knowledge3`, `offline_knowledge` and `voice_responses` remained visible under the active Bible tree, so users had to navigate technical source namespaces instead of one library.
- Change: created the single user-facing `data/Bible/library/` view with `CPU`, `Computer`, `Audio`, `Music`, `Responses`, `Literature` and `Psychology`; moved provenance and technical audio under `data/Bible/.internal`; archived previous generated views and metadata backup under `data/archive/bible_reorganization_20261115`.
- Evidence: central catalog and API both expose 7,250 records; CPU view has 52 records, Computer 384, Responses 246; old logical aliases resolve to `.internal`; no source/WAV deletion was performed.

### PH4-VOICE-010 — Fish status hid the profile-specific inference error

- Status: **FIXED / REGRESSION VERIFIED**
- Cause: `VoiceModelManager.status()` preferred the generic “API key found” message and could expose the entire internal error map instead of the error for the selected Fish profile.
- Change: status now reports the selected profile's exact error, keeps `ready=false` and `inference_verified=false` until successful inference, and never routes Fish failures to XTTS.
- Evidence: `test_tts_routing.py` **4/4 PASS**; live read-only status reports `fish_jarvis`, `available=true`, `ready=false`, `inference_verified=false`.
- Live evidence update: real short inference through `fish_jarvis` returned a valid RIFF WAV (200748 bytes); current process reported `ready=true` and `inference_verified=true`.
- Live playback evidence: Fish WAV decoded as mono 44.1 kHz; playback started and completed; `sd.stop` executed and device release was confirmed; owner confirmed audible result through the штатный route.

### PH4-UI-011 — sidebar assistant switch was a visual stub

- Status: **FIXED / REGRESSION VERIFIED**
- Priority: P2
- Symptom: the «Ассистент» switch did not control Jarvis; it showed a message that the switch was inactive and was forced back to `ON`.
- Root cause: `frontend/jarvis_ui.py` connected the switch to `_assistant_toggle_stub()`, while `_set_assistant_ui()` always checked it.
- Change: the switch now calls the existing `_toggle_voice_runtime()` START/STOP path, and `_set_assistant_ui()` reflects the actual runtime state.
- Evidence: `frontend/tests/test_assistant_toggle_contract.py` plus existing voice-input tests: **8/8 PASS**, including AST-verified state guard/dispatch and single configurable API-root checks; `py_compile` for UI and test: **PASS**. Live click acceptance remains a separate manual UI gate.

### PH4-VOICE-011 — active widget session discarded commands after Vosk wake-word drift

- Status: **FIXED / LIVE REGRESSION VERIFIED**
- Priority: P1 voice interaction
- Symptom: during live Minifuse testing, the user said `Jarvis`, but Vosk returned `обвес`; the exact wake-word gate rejected the transcript before Command Router. A later retry produced `джарвис` and only the greeting WAV.
- Root cause: `_extract_command()` required a matching wake-word for `source="widget"`, even though START had already explicitly activated the voice session.
- Change: active `chat`/`widget` sessions now pass their normalized transcript directly to the existing response/command router. Passive wake-word handling remains unchanged.
- Evidence: `backend.tests.test_voice_runtime_isolated` **5/5 PASS**; live restart confirmed `vosk-silero`, active widget session, and `fish_jarvis` selected/verified. Live commands `открой Яндекс Музыку` and related command phrases reached `command` and played their prepared WAVs. A later correction restores the instant `Да сэр.wav` path for an isolated wake-word while retaining the active-session bypass for substantive phrases.

### PH4-VOICE-012 — transient Fish Audio TLS failure during live playback

- Status: **EXTERNAL TRANSIENT / RECOVERED BY RETRY**
- Priority: P1 voice output
- Symptom: live Ollama response was generated, but Fish Audio returned `SSLEOFError`; UI reported `ошибка озвучки` and no alternate voice was used.
- Root cause: transient HTTPS/TLS provider failure; no evidence of invalid profile or credentials.
- Safety behavior: selected profile remains `fish_jarvis`; failed inference clears verification and does not silently route to XTTS.
- Evidence: direct retry through project Python 3.11 generated a valid non-empty WAV (**159788 bytes**, **1994.2 ms**). A further audible live confirmation remains a manual step.

### PH4-VOICE-013 — accepted small-talk WAV fast path was missing from active runtime

- Status: **FIXED / REGRESSION VERIFIED**
- Priority: P1 voice latency
- Symptom: «как дела?» was routed through Knowledge/Fish instead of the previously accepted instant local WAV path.
- Root cause: `SMALLTALK_WAVS`/`_smalltalk_wav_for()` had been removed from the active `VoiceRuntime` while the existing cache remained on disk.
- Change: restored the fast path in the single runtime; only semantically matching “как дела/как поживаешь/ты как” phrases use the three existing cached WAVs. “Что нового?” is intentionally excluded to avoid a wrong canned answer.
- Evidence: `test_voice_runtime_isolated` **6/6 PASS**; live transcript `как дела` produced `wav:smalltalk_how_2.wav`; no WAV was created or overwritten.

### PH4-VOICE-014 — VAD clipped beginnings of short wake-word segments

- Status: **FIXED IN SOURCE / LIVE RETEST PENDING**
- Priority: P1 STT accuracy
- Cause: Silero positive detection began capture after the first audio frames had already been discarded.
- Change: Vosk/Silero route retains a bounded ~192 ms pre-roll before speech onset.
- Evidence: STT route contract test PASS; live six-repeat wake-word test eventually produced `джарвис` and `Да сэр.wav`, but immediate single-attempt acceptance remains open.

### PH4-VOICE-015 — «Что нового» использовало ответ «как дела»

- Status: **FIXED / REGRESSION VERIFIED**
- Priority: P1 voice semantics
- Symptom: на вопрос `что нового` Jarvis отвечал одной из фраз карточки `как дела`, включая «У меня всё в порядке».
- Root cause: в текущем вручную редактируемом источнике `mood_010` готовые ответы совпадают с `mood_002`; это ошибка содержимого каталога, а не STT.
- Change: исходная Bible не изменялась. `KnowledgeSearchService` блокирует только точные формы запроса о новом и не отдаёт ошибочную instant-карточку. `VoiceRuntime` использует отдельный маршрут из десяти Fish WAV `news_01.wav`–`news_10.wav` и не обращается к Ollama.
- Evidence: Fish Audio generation `10/10 READY`; `test_voice_runtime_isolated` **8/8 PASS**; `test_knowledge_variations` **15/15 PASS**. Готовые WAV не перезаписывались.

### PH4-VOICE-016 — wake-word иногда не давал `Да сэр` или запускал лишний greeting route

- Status: **FIXED IN SOURCE / LIVE RETEST REQUIRED**
- Priority: P1 voice interaction
- Symptom: после `Jarvis` не было немедленной реакции либо проигрывался другой greeting WAV.
- Root cause: короткие варианты `wake-word + greeting/filler` (`джарвис привет`, `джарвис эй`) в active chat/widget session проходили как содержательная реплика из-за bypass.
- Change: такие варианты теперь считаются только активацией и используют существующий `Да сэр.wav`; содержательные фразы по-прежнему проходят в Command Router/Conversation Resolver.
- Evidence: `test_voice_runtime_isolated` **8/8 PASS**. Одиночное физическое распознавание wake-word всё ещё требует live retest.

### PH4-VOICE-017 — «ты хороший» уходил в нерелевантный ответ модели

- Status: **FIXED IN SOURCE / LIVE RETEST REQUIRED**
- Priority: P1 voice semantics
- Root cause: у короткого вопроса не было отдельного правила ConversationResolver; при неточном STT результат попадал в общий Ollama prompt.
- Change: добавлено детерминированное локальное правило `jarvis_good_assistant` с одним коротким ответом. Оно не вызывает Ollama и использует выбранный Fish TTS для озвучивания.
- Evidence: `test_conversation_resolver` **5/5 PASS**. Для полностью подтверждённого live результата нужна точная STT-транскрипция фразы.

### PH4-VOICE-018 — голосовая погода не использовала OpenWeather

- Status: **FIXED IN SOURCE / API SMOKE PASS**
- Priority: P1 functional correctness
- Root cause: `computer_control.open_weather()` только открывала Yandex Weather; голосовой маршрут не вызывал тот же OpenWeather API, что UI.
- Change: голосовая команда `weather` теперь получает город и ключ из существующей runtime-конфигурации, вызывает OpenWeather `/data/2.5/weather`, формирует фактический отчёт и озвучивает его через выбранный Fish-путь. Секреты не выводятся.
- Evidence: изолированный weather unit test **2/2 PASS**; реальный read-only OpenWeather smoke вернул HTTP 200 для настроенного города. Live произнесённая команда и слышимый ответ требуют отдельной ручной проверки.

### PH4-VOICE-019 — контекст голосового диалога не восстанавливался по `chat_id`

- Status: **FIXED IN SOURCE / REGRESSION VERIFIED; LIVE RETEST REQUIRED**
- Priority: P1 voice semantics
- Symptom: после перезапуска voice-сессии или смены чата уточняющий вопрос выполнялся без предыдущих реплик либо мог наследовать контекст другого чата.
- Root cause: `VoiceRuntime` хранил ограниченную историю только в памяти процесса; при смене `chat_id` список очищался, но история из `ChatStore` не загружалась.
- Change: история теперь привязывается к активному `chat_id`, восстанавливается из последних сообщений `ChatStore` при старте/переключении voice-сессии и изолируется между чатами. В prompt Ollama добавлено требование отвечать на уточнения в рамках предыдущей темы.
- Evidence: изолированные тесты восстановления и отсутствия утечки контекста; voice runtime suite **10/10 PASS**. Реальный разговор с физическим микрофоном после исправления ещё не повторён.

### PH4-UI-006 — активный чат не имел отдельного визуального состояния

- Status: **FIXED IN SOURCE / REGRESSION VERIFIED; LIVE UI RETEST REQUIRED**
- Symptom: после выбора чата в списке не было устойчивого акцентного выделения, поэтому активный чат было трудно отличить от остальных.
- Change: `ChatItemWidget` получил состояние `active`; текущий `current_chat_id` синхронизирует закреплённые и недавние карточки, акцентную рамку, фон и цвет/жирность названия. Состояние обновляется при загрузке списка, выборе чата, открытии истории и создании нового чата.
- Evidence: frontend contract suite **10/10 PASS**, `py_compile` PASS. Живая визуальная проверка ожидает перезапуска UI.

### PH4-UI-007 — диалог подтверждения удаления чата был прозрачным

- Status: **FIXED IN SOURCE / REGRESSION VERIFIED; LIVE UI RETEST REQUIRED**
- Symptom: при удалении чата фон списка и рабочего стола просвечивал через окно подтверждения.
- Root cause: modal `QDialog` наследовал `WA_TranslucentBackground=True`, тогда как stylesheet задавал только полупрозрачную glass-поверхность.
- Change: confirmation dialog теперь использует непрозрачный фон `#12151c`, явный border, `WA_TranslucentBackground=False` и `setAutoFillBackground(True)`. Логика подтверждения и API удаления не менялись.
- Evidence: frontend contract suite **11/11 PASS**, `py_compile` PASS. Визуальная проверка после перезапуска UI ещё нужна.

### PH4-UI-008 — синхронный перебор камер задерживал старт UI

- Status: **FIXED IN SOURCE / REGRESSION VERIFIED; LIVE START RETEST REQUIRED**
- Symptom: при построении настроек UI последовательно открывал до шести индексов DirectShow, из-за чего старт задерживался и в stderr появлялись повторяющиеся ошибки `VideoCapture`.
- Root cause: hardware discovery выполнялся в критическом пути построения окна, хотя фактический захват нужен только по запросу.
- Change: стартовые настройки показывают сохранённый индекс камеры без открытия устройств. Проверка доступности остаётся в on-demand capability/snapshot пути.
- Evidence: frontend contract suite **12/12 PASS**, `py_compile` PASS. Повторный запуск UI на обновлённом коде ещё требуется.

### PH4-VOICE-020 — уточнение «почему ты не спишь» уходило в Ollama

- Status: **FIXED IN SOURCE / REGRESSION VERIFIED; LIVE VOICE RETEST REQUIRED**
- Symptom: после правильного ответа на «ты хочешь спать?» уточнение «почему ты не спишь?» получало шаблонный ответ модели и теряло тему.
- Root cause: `ConversationResolver` обрабатывал начальный вопрос и часть follow-up, но не имел отдельного правила объяснения причины.
- Change: добавлен детерминированный контекстный ответ `sleep_followup_explanation`; Ollama не вызывается для этой короткой связки.
- Evidence: `test_conversation_resolver` **6/6 PASS**; `py_compile` PASS. Реальный голосовой повтор после перезапуска требует ручной фразы.

### PH4-VOICE-021 — модельный маршрут не имел явного якоря последней темы

- Status: **FIXED IN SOURCE / REGRESSION VERIFIED; LIVE MULTI-TURN RETEST REQUIRED**
- Symptom: для уточняющих вопросов вне специальных локальных правил модель могла начать новый общий ответ вместо продолжения темы.
- Root cause: история передавалась как сообщения, но prompt не выделял последнюю пользовательскую тему и не требовал сначала связать текущую реплику с ней.
- Change: перед модельным ответом VoiceRuntime формирует bounded context anchor из последней пользовательской реплики и добавляет общую инструкцию продолжать тему для любых follow-up, а не только для сна.
- Дополнение: если данных недостаточно, модель получает инструкцию задать один короткий уточняющий вопрос по текущей теме вместо догадки или смены темы.
- Evidence: `test_voice_knowledge_tts` **2/2 PASS**; `py_compile` PASS. Реальный voice → STT → Ollama multi-turn retest ещё требуется.
