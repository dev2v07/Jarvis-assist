# Jarvis conventions and invariants

- Composition-root pattern: backend/main.py constructs shared stores/services/agents and wires FastAPI routes; avoid creating parallel service graphs in request handlers or runtime components.
- Service boundaries are explicit classes in backend/services; preserve logical facades, especially KnowledgeSearchService for all knowledge/audio roots.
- Provider selection is adapter-based and configuration-driven; unavailable optional providers should return explicit status/errors rather than silently claiming readiness.
- Capability boundaries are confirmation-first/read-only where possible: DAW/project, filesystem, device and backup actions must not be inferred as successful without explicit execution evidence.
- Voice routing is layered: command intent first, then deterministic conversation/knowledge/local response, then dynamic LLM fallback; do not add a competing orchestrator.
- Runtime state is persisted through bounded stores; do not merge SQLite files or physical knowledge roots without an entity/path audit.
- Windows-specific paths, autostart and process ownership are user-scoped; avoid administrator assumptions and destructive process/file operations.
- Tests are Python unittest discovery tests under backend/tests plus frontend contract tests; many runtime/device/audio behaviors need live acceptance beyond automated tests.
- Keep source, generated local audio, models, datasets and user data conceptually separate; local WAV/model payloads are not automatically source artifacts.
