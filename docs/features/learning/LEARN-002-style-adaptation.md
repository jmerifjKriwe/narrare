---
id: LEARN-002
title: "Adaptivity Dashboard"
status: in-progress
area: learning
mvp: false

ui_tooltip: "See and control how Narrare adapts to your writing voice."
ui_help_short: |
  View which signals Narrare uses to personalize AI suggestions,
  and adjust how strongly each one influences results.
ui_help_long: |
  ## Adaptivity Dashboard

  Adaptivity is Narrare's way of learning your preferences and respecting
  your characters' voices. The dashboard makes this transparent and adjustable.

  **Active Signals**
  - User preferences (from your accept/reject history)
  - Character voice profiles (from ANAL-008 analysis)
  - Derived style constraints
  - Avoidance patterns

  **Adjustable Weights**
  - Preference influence
  - Voice fidelity priority
  - Style constraints enforcement
  - Avoidance enforcement

  **Per-call transparency**
  Each AI call records which signals influenced the result. Click any
  recent call to see exactly what was used.

  **Note:** Adaptivity uses your existing data — it never runs new long-running
  analyses in the background. To update a character voice, run ANAL-008 again.
ui_available_in: [settings, editor]

service: adaptive/service.py
contract: adaptive/contracts.py#AdaptiveContextServiceProtocol
router: adaptive/router.py
prompt: ""  # adaptivity is not a prompt surface; it injects into other prompts
requires: [LEARN-001, ANAL-008, ASSIST-004]
---

# LEARN-002 — Adaptivity Dashboard

> **Recalibrated 2026-07-19** by [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md).
> The original "Style Adaptation" concept (statistical voice pipeline with
> sentence-length distribution, vocabulary diversity, and few-shot prompting)
> is **no longer pursued**. The new scope is **visibility + steering +
> transparency** of existing adaptive signals. See the Changelog below.

## Changelog

### 2026-07-19 — Recalibrated

- **LEARN-002 recalibrated.** The Style Adaptation spec has been reinterpreted
  as an Adaptivity Dashboard. The previous concept (statistical voice pipeline
  with sentence-length distribution, vocabulary diversity, dialogue ratio,
  few-shot prompting, sentence-pattern analysis, and a separate `StyleProfile`
  data store) is no longer pursued. The new scope is **visualization, control,
  and transparency of existing adaptive signals** (`PreferenceProfile` from
  LEARN-001 + `CharacterVoiceProfile` from ANAL-008), not the construction of a
  new SSOT.
- **Feature-ID `LEARN-002` stays** (recalibration, not superseding — per User
  decision Q-C1 in ADR-069 Decision 13).
- **Status changes** from `planned` to `in-progress` (per ADR-069 Decision 13;
  no new `recalibrated` status value is introduced).
- **Driver:** the original scope overlapped with `ANAL-007` (Author Voice
  Profiling) and duplicated `PreferenceProfile`. The recalibration gives
  LEARN-002 a coherent, implementable purpose.
- **Source:** `docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md`
  §7 + [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md).

---

## What it does

The Adaptivity Dashboard makes Narrare's adaptive behavior **visible,
controllable, and transparent**. It shows which signals (user preferences,
character voices, derived style constraints, avoidance patterns) shape AI
output, lets the user tune how strongly each signal influences results, and
records per-call which signals were active.

The dashboard does NOT itself run AI operations, does NOT compute new voice
profiles, and does NOT store a third "style profile" data source. It is a
**view-and-control surface** over data that other features (LEARN-001,
ANAL-008) produce.

## Why it exists

Narrare already has the infrastructure to adapt to a writer's voice and
preferences (`PreferenceProfile`, `CharacterVoiceProfile`,
`ProjectWritingProfile`, four registered prompt variables). But that
infrastructure is **invisible to the user** and **two of the four variables
are always empty**. Without visibility:

- Users cannot tell whether adaptivity is active.
- Users cannot tune influence weights.
- Users cannot see which signals shaped a specific AI call.
- The pilot consumer (ASSIST-004 Dialogue Coach) needs a control surface.

The Adaptivity Dashboard closes this gap by surfacing what is already
happening and giving the user agency over it.

## How it works (User perspective)

1. Open **Settings → Learning → Adaptivity Dashboard**.
2. See the **Master Toggle** (Adaptivity ON/OFF).
3. See **Active Signals** — which PreferenceProfile entries and which
   CharacterVoiceProfiles are currently being used.
4. See **Weights** — four sliders (Preference influence, Voice fidelity
   priority, Style constraints, Avoidance enforcement) each in [0.0, 1.0].
5. Adjust weights; reset to defaults if needed.
6. See **Recent Adaptive Activity** — a paginated list of recent AI calls
   that consumed adaptive signals, with per-call detail (intent, signals
   used, weights applied).
7. In the editor, the **Adaptive Status Indicator** (toolbar) shows at a
   glance whether adaptivity is ON/PAUSED/NO-DATA; clicking opens the
   dashboard.

## How it works (Technical)

This feature is a thin Backend service over the Core `AdaptiveContext`
abstraction. The Core contract is defined in ADR-069; this section documents
the Backend pieces owned by LEARN-002.

**Backend domain:** `apps/api/narrare/adaptive/`

**Files:**

- `apps/api/narrare/adaptive/__init__.py`
- `apps/api/narrare/adaptive/contracts.py` — `AdaptiveContextServiceProtocol`
- `apps/api/narrare/adaptive/schemas.py` — `AdaptiveContextResponse`,
  `AdaptiveSettingsResponse`, `AdaptiveWeightsInput`,
  `AdaptiveWeightsResponse`, `AdaptiveSourceSummary`
- `apps/api/narrare/adaptive/service.py` — `AdaptiveContextService`
- `apps/api/narrare/adaptive/repository.py` — settings persistence helper
  (or extends `project_ai_settings_repository.py`)
- `apps/api/narrare/adaptive/router.py` — 3 endpoints
- `apps/api/narrare/adaptive/dependencies.py` — DI factories
- `apps/api/narrare/adaptive/adaptive_context_provider.py` —
  `AdaptiveContextProviderImpl` (implements the Core Protocol)

**Endpoints:**

```
GET    /api/v1/adaptive/context
  → 200 AdaptiveContextResponse
  → 401 unauthorized

POST   /api/v1/adaptive/toggle
  Body: { enabled: bool }
  → 200 AdaptiveSettingsResponse
  → 422 validation_error

POST   /api/v1/adaptive/weights
  Body: { preference: float, voice_fidelity: float,
          style_constraints: float, avoidance: float }
  → 200 AdaptiveSettingsResponse (with clamped values)
  → 422 validation_error
```

**Core contract consumed:** `AdaptiveContextProvider` Protocol in
`packages/core/narrare_core/ai_invocation/contracts.py` (defined by
ADR-069 Decision 3). The Backend `AdaptiveContextProviderImpl` composes:

- `PreferenceProvider` (LEARN-001 / ADR-033 / mem0).
- `ProfileProvider` (ADR-040 / `ProjectWritingProfile`).
- Adaptive settings repository (this feature — `ProjectSettings.adaptive_settings` JSONB).
- Derivation logic for `style_constraints_text` + `avoidance_patterns_text`.
- Invocation-evidence snapshot writes (`adaptive_source_summary` +
  `adaptive_weights` columns on `invocation_evidence`, per ADR-069 Decision 11).

**Persistence:** `ProjectSettings.adaptive_settings: JSONB` (per ADR-069
Decision 2). Stores `{enabled: bool, weights: {preference, voice_fidelity,
style_constraints, avoidance}}`.

**Frontend:**

- `packages/web/components/studio/settings/AdaptiveDashboard.tsx`
- `packages/web/components/studio/settings/AdaptiveToggle.tsx`
- `packages/web/components/studio/settings/AdaptiveWeightControls.tsx`
- `packages/web/components/studio/settings/AdaptiveWeightSlider.tsx`
- `packages/web/components/studio/settings/AdaptiveSourceList.tsx`
- `packages/web/components/studio/settings/AdaptiveSnapshotHistory.tsx`
- `packages/web/components/studio/editor/AdaptiveStatusIndicator.tsx`
- `packages/web/hooks/adaptive/useAdaptiveContext.ts` (TanStack Query,
  cache key `['adaptive-context']`)
- `packages/web/lib/api/adaptive.ts` (REST client)

**i18n namespaces (RULE-16):** `settings.adaptive`, `editor.adaptiveIndicator`
(both registered in `request.ts` and present in `packages/i18n/messages/
{en,de,fr}/`).

**Cross-component updates:** TanStack Query cache invalidation
(`queryClient.invalidateQueries({ queryKey: ['adaptive-context'] })` after
mutations). Conform with ADR-043 per ADR-069 Decision 15.

## Constraints & Edge Cases

- **No new SSOT.** LEARN-002 visualizes existing data (`PreferenceProfile`,
  `CharacterVoiceProfile`); it does not create a third "style profile" data
  source.
- **No long-running analysis.** Adaptivity is purely reactive — no
  background "analyze my style" job. To refresh a character voice, the user
  runs ANAL-008.
- **No few-shot prompting engine.** The original spec's example-sentence
  injection is out of scope.
- **No statistics charts.** Sentence-length distribution, vocabulary
  diversity, etc. are out of scope.
- **No CLI commands.** The original spec mentioned `narrare style analyze`
  and `narrare style generate`; both are removed.
- **No separate style-profile export.** `PreferenceProfile` already has an
  export mechanism via LEARN-001.
- **Self-gating.** If the user has no preferences AND no voice profiles,
  the dashboard shows "No signals yet" and the indicator shows "no data".
- **Disabled adaptivity is honoured.** When `AdaptiveSettings.enabled = False`,
  the enricher skips injection; the indicator shows "paused"; AI runs without
  adaptive context (degraded, not broken).
- **Stale voice profiles.** Characters profiled >7 days ago surface with
  `is_fresh=False`; the dashboard shows a ⚠ marker.
- **Malformed settings JSON.** The service loads defaults and logs an error;
  the UI shows a "settings reset to defaults" warning.
- **All weights at 0.0.** Effectively disables adaptivity; UI shows a warning.
- **All weights at 1.0.** Maximises adaptive influence; may approach token
  budgets; UI shows an info note.

## Out of Scope (per ADR-069 §3.3 and the brainstorming §7.6)

- **Author Voice Profiler** — that is `ANAL-007` (stays `planned`).
- **Statistical Voice Pipeline** — sentence-length distribution, vocabulary
  diversity, dialogue ratio, metaphor density. Not pursued.
- **Voice Metrics in Generation** — `voice_metrics` (ADR-057) stay
  checking-path only. Never injected by adaptivity.
- **New Style-Profile Table** — not introduced; `PreferenceProfile` and
  `CharacterVoiceProfile` are the only sources.
- **Auto-Profiling** — adaptivity never triggers new analyses.

## Related Features

- [LEARN-001](LEARN-001-feedback-loop.md) — Source of `PreferenceProfile`
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Source of
  `CharacterVoiceProfile`
- [ASSIST-004](../ai_assist/ASSIST-004-dialogue-coach.md) — Pilot consumer
  of `AdaptiveContext`
- [WRITE-010](../writing/WRITE-010-voice-checker.md) — Voice metrics stay
  on the checking path; LEARN-002 does NOT consume `voice_metrics`
- [ADR-069](../../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md) —
  The architectural decisions that recalibrated this feature

## Status & History

- `project-init` — Added to registry as planned feature (original "Style
  Adaptation" scope).
- `2026-07-19` — **Recalibrated** from statistical voice pipeline to
  Adaptivity Dashboard (ADR-069). Original concept (sentence-length
  distribution, vocabulary diversity, few-shot prompting) is no longer
  pursued. New scope: visibility + steering + transparency of existing
  adaptive signals (`PreferenceProfile` + `CharacterVoiceProfile`).
  Status changed `planned → in-progress`.
