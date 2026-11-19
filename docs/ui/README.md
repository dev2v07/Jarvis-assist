# UI

- [Audits](audits/)

UI source remains in `frontend/`; this section contains documentation only.

## Settings shell (2026-11-17)

`frontend/jarvis_ui.py` owns the single Settings navigation and the shared
`settingsCard` Glass surface. All Settings pages live in one scroll area and
`CurrentPageStack`; only the current page contributes height-for-width, so a
hidden tall page cannot force a scrollbar on a short page. AI Providers uses
the same content layout and expands its panel to the available card size.
The windowed/fullscreen transition restores one saved normal geometry, while
the Sidebar layouts the pinned and recent chat lists without competing fixed
fullscreen heights. The normal UI uses `backend/main.py` through the launcher.

See the current evidence and remaining gates in
[`JARVIS_RUNTIME_BUG_REGISTRY.md`](../runtime/bug_registry/JARVIS_RUNTIME_BUG_REGISTRY.md)
and [`HANDOFF_ASSIST.md`](../HANDOFF_ASSIST.md). Manual acceptance on UI PID
2248 covered AI size, no extra AI scroll, and navigation clicks after returning
from fullscreen; it did not cover every control or resolution.

The General page keeps `accent_color` separate from `glass_tint`. Glass/Blur
updates the main container background, and its palette changes only the Glass
tint. Quick links resolve their target by the actual Settings navigation label.
The authenticated email from the existing AccountCoordinator is copied to the
empty local `profile_email` key so Account and My Profile show the same verified
identity.

The capabilities page uses the same dark Glass vocabulary as General: eight
backend-reported capabilities are actionable cards in a responsive two-column
grid. Settings action buttons share the transparent cyan-outline style used by
AI `ПРОВЕРИТЬ` / `ПОЛУЧИТЬ МОДЕЛИ`; provider and device operations continue to
run through the existing bounded `NetworkOperationWorker`.

Provider saves are partial contracts. The UI sends only the edited profile and
the backend excludes unset Pydantic fields before persistence. FreeLLMAPI uses
`AUTO` when no explicit model exists; it must never inherit the Ollama model.
The current runtime verification is recorded as backend integration evidence,
while final visual acceptance of the new cards/buttons/email remains owner-led.

## Unified interaction checkpoint (2026-11-17)

Settings pages use one layout contract: compact top-aligned content followed by
a bottom action row. Account, IRON, Weather, Commands, Data, Chat, Voice and History use
the same transparent cyan-outline action language as AI; General remains a
purpose-built live appearance page. The Commands list owns the remaining height
above its two actions rather than leaving an unused gap.

Capabilities use 128 px cards: title and status remain adjacent at the top,
while the reserved lower area can receive a future icon. The two explicit
device actions are bounded to 220×38 with a 12 px gap. History rows use the
same root-owned dark Glass surface as Settings cards and keep a 6 px gap.

Chat readiness is a model state, not an activity animation. Once the selected
model is confirmed, the dot beside the model stays blue for normal and local
responses; only errors turn it red. The WebEngine chat uses an opaque
`#121212` styled host/palette with a one-device-pixel right safety inset. Its
scrollbar track and corner are also opaque; leaving either the host edge or
track transparent exposed the wallpaper as a one-pixel seam at fractional
Windows DPI. This was owner-accepted in the live app.

Voice Mode has one lifecycle owned by `JarvisUI`. Windowed mode uses bounded
Orb/ring geometry; fullscreen preserves the accepted large composition.
Navigation to another main page or chat hides the overlay immediately and asks
the existing main backend to stop the voice session asynchronously. No second
voice controller or backend was introduced.
