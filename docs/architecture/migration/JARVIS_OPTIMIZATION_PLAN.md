# Jarvis — prioritized optimization plan

This is a plan only. No implementation was performed by the audit.

## P0 — before release or wider exposure

| Priority | Work | Complexity | Risk | Dependencies | Expected result | Resource/cost impact |
|---|---|---:|---:|---|---|---|
| P0.1 | Close CORS/control boundary and require explicit confirmation for system actions | M | High | `main.py`, `computer_control.py`, UI error/confirmation model | Lower local-network and destructive-action risk | Prevents costly/unsafe accidental execution |
| P0.2 | Run current-source manual UI/voice acceptance | M | Medium | controlled backend, microphone, speaker, screenshots | Converts unknown runtime gates into evidence | Finds hangs and duplicate requests before release |
| P0.3 | Close SQLite/resource warnings | S | Low | knowledge tests and stores | Clean test/runtime lifecycle | Reduces leaks and long-session instability |
| P0.4 | Define account deployment boundary | M | High | `account/`, `account_server/`, PostgreSQL test env | No ambiguous local-vs-server auth behavior | Avoids support and security failures |

## P1 — architecture and stability

| Priority | Work | Complexity | Risk | Dependent components | Expected result |
|---|---|---:|---:|---|---|
| P1.1 | Split `backend/main.py` into routers, lifecycle/composition, and domain boundaries | L | High | all routes/services | Smaller testable units and safer startup |
| P1.2 | Introduce one typed frontend API client | M | Medium | `jarvis_ui.py`, composer, settings, voice | Centralized timeouts, errors, retries and endpoint contracts |
| P1.3 | Formalize one voice state machine | M | High | VoiceRuntime, session manager, TTSQueue, UI | No widget/chat microphone conflicts; explicit stop/restart semantics |
| P1.4 | Add turn/request/provider telemetry | M | Medium | runtime registry, LLM adapters, voice | Exact AI request count, latency, retries and cost attribution |
| P1.5 | Make knowledge ownership/version/alias rules explicit | M | Medium | all knowledge catalogs and index services | Detect collisions and stale WAV/text pairings |

## P2 — performance and cost

1. Keep exact conversational and verified local answers ahead of planner/LLM; this is already present in `/chat` and `VoiceRuntime`, so preserve it and measure hit rate.
2. **Implemented for voice route (2026-11-15):** automatic Ollama warmup on microphone start was removed; voice turns make one model attempt. Keep telemetry/counting as a follow-up for text and non-voice routes.
3. Prefer local models for bounded classification, routing, catalog search and short acknowledgement tasks; reserve cloud providers for tasks requiring their quality or external capability.
4. Keep `limit=12` chat context and bounded runtime event journal, but instrument truncation and retry behavior before changing limits.
5. Do not mass-generate WAV or run load tests until the catalog/audio version contract is defined.
6. Exclude environments, `external`, model checkpoints and generated audio from release bundles through allowlists rather than ad-hoc exclusions.

## P3 — deferred improvements

- split UI pages from the 6k-line `jarvis_ui.py`;
- replace absolute HUD positioning outside the fixed canonical canvas with a tested layout policy;
- add screenshot/visual regression tests for the HUD;
- add live account boundary tests against an isolated PostgreSQL service;
- add explicit integration adapters for browser/Figma/plugins only when their permission and confirmation model is defined;
- add structured backup/restore verification rather than only backup route smoke tests.

## Five required lists

### 1. Critical errors blocking normal Jarvis work

- Current-source UI/voice runtime has no fresh manual acceptance evidence.
- System-control calls include direct shutdown/reboot paths without a demonstrated unified confirmation boundary.
- Account server and desktop account flow are not proven as one deployed system.
- CORS is wildcard on a backend that includes control-capable routes.

### 2. UI/UX errors affecting use

- Hard-coded endpoint calls duplicate timeout/error policy.
- Screenshot acceptance and resize/fullscreen behavior are not currently evidenced on this checkout.
- Integration menu can expose actions that are only stubs/connection points.
- Long-lived UI/backend state can diverge unless cancellation and stale polling are tested.

### 3. Architectural duplicates/conflicts

- Multiple knowledge roots and indexes.
- Conversational WAV resolver, offline knowledge resolver and Knowledge 3.0 aggregation.
- Voice STT/VAD/TTS legacy/current paths.
- Local account adapters and separate account server.
- Direct UI/agent/ service-level Windows process control.

### 4. AI and cost optimization

- Measure and gate warmup requests.
- Keep local deterministic answers out of LLM path.
- Route classification/search/short responses to Ollama where quality is sufficient.
- Add per-turn provider/retry/token/latency budget records.
- Avoid planner activation for plain upload acknowledgement and exact local knowledge.

### 5. Improvements that can wait

- Full UI module split.
- Visual redesign or new geometry.
- Additional domain catalogs.
- Broad load testing.
- New cloud integrations.

## Recommended order

```mermaid
flowchart LR
    A[Boundary and confirmation security] --> B[Current-source UI/voice acceptance]
    B --> C[Close resource/test warnings]
    C --> D[Typed API client and main.py split]
    D --> E[Voice state machine and telemetry]
    E --> F[Knowledge ownership/version contract]
    F --> G[Cost and packaging optimization]
    G --> H[Deferred UI/integration improvements]
```
