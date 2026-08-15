---
id: SERIES-003
title: "Series Voice Hierarchy"
status: stable
area: series
mvp: false  # post-MVP (Phase 6); Spec 3 of the Series program

ui_tooltip: "Give every novel in a series a shared foundational voice, with per-novel nuances."
ui_help_short: |
  When you write a novel in a series, Narrare can use a shared "series voice" as
  the foundation and layer this novel's own voice on top. Profile the series
  voice from any one band, override it by hand, or turn it off for a single
  experimental novel.
ui_help_long: |
  Series Voice Hierarchy is what makes a series *sound* like a series to the AI.
  Each series can have one **Series Voice** — a profile of the prose style shared
  across all its books. When you generate a novel that belongs to the series,
  Narrare uses the series voice as the **foundation** and adds this novel's own
  voice on top as **nuances** ("Series voice is X. Additionally, this novel has Y.").

  You stay in control:
  - **Profile from a band** — pick any novel in the series and let the AI profile
    its voice as the series voice (one click; reuses the existing author-voice
    analyzer).
  - **Override** — write your own voice profile by hand if you want to correct or
    steer the generated one.
  - **Clear** the override to start fresh.
  - **Per-novel opt-out** — if one band should *not* inherit the series voice
    (an experimental book, a stylistic detour), turn "Use series voice as base"
    off in that novel's settings. The novel then uses only its own voice.

  The shared series voice and the novel voice are combined in one coherent
  block for the AI — there is no second "series voice" prompt; Narrare extends
  the existing author-voice instruction.

  **API Endpoints:**
  - `POST /api/v1/series/{id}/voice/profile` — profile a band → store as series voice (body: `{novel_id}`)
  - `GET /api/v1/series/{id}/voice` — read the series voice (may be null)
  - `PATCH /api/v1/series/{id}/voice` — manual voice-profile override
  - `DELETE /api/v1/series/{id}/voice/override` — clear the override
  - `PATCH /api/v1/novels/{novel_id}/settings` — extended to accept `use_series_voice`

  **UI Location:** `/series/[id]` workspace → **Voice tab** (profile display +
  profile-from-band + override editor); **Novel Settings** → "Use series voice
  as base" toggle (self-hides for standalone novels).

ui_available_in: [series-workspace, novel-settings]

service: series/series_voice_service.py
contract: series/series_voice_contracts.py#SeriesVoiceServiceProtocol
router: series/router_voice.py
requires: [SERIES-001, ANAL-007]  # Spec 3 populates Spec 1's empty SeriesSettings.author_voice via the ANAL-007 AuthorVoiceAgent
---

# SERIES-003 — Series Voice Hierarchy

## What it does

Give a series a shared foundational voice and let each novel layer its own voice
on top. Profile the series voice from any one band (or override it by hand), and
let any novel opt out of the series voice entirely.

## Why it exists

Spec 1 (SERIES-001) gave Narrare the Series entity and an empty
`SeriesSettings.author_voice` column — a forward-compat hook. Spec 2
(SERIES-002) gave the AI prior-band *story* context. But a series also has a
*voice*: the prose style that makes book N feel like part of the same series.
Without a series voice, every band's generation leaned only on that novel's own
profile, and the shared "sound" of the series had to be re-established (or was
lost) each time.

This is the voice-resolution consumer of Spec 1's foundation. It closes the
Voice-Teil of ADR-074's Review Trigger (storage was closed by ADR-075 in Spec 1;
the resolution model — Delta + opt-out — is closed here).

This is Spec 3 of 5 in the Series program. Spec 1 (Foundation) and Spec 2
(Generation Context) are implemented; Spec 4 (Cross-Novel Drift) and Spec 5
(Export) remain downstream.

## How it works (User perspective)

1. Open a series workspace and go to the **Voice tab**.
2. If no series voice exists, the tab shows an empty state.
3. Click **Profile from band…**, pick a novel in the series, and confirm. The AI
   profiles that band's prose and stores it as the series voice.
4. The voice profile is displayed (descriptive fields only — formality,
   vocabulary level, etc.; metrics are never shown, they are for drift
   comparison only).
5. To correct or steer it, edit the **Override** JSON and **Save Override**.
   Click **Clear Override** to reset.
6. When you generate any novel in the series, the AI automatically uses the
   series voice as the foundation, with that novel's own voice as nuances.
7. For one novel that should *not* inherit the series voice: open that novel's
   **Settings**, turn off **"Use series voice as base"**. The novel then uses
   only its own voice.

## How it works (Technical)

- **Resolution model — Delta.** The series voice is the foundation; the novel
  voice is additive. The pure Core renderer
  `render_author_voice_delta()` composes the existing descriptive-only renderer
  once per profile and emits:
  - Series + Novel voice → `"Series voice:\n{series}\n\nNovel nuances:\n{novel}"`
  - Series only (no novel voice) → `"Series voice:\n{series}"`
  - Standalone / opt-out / no series voice → novel-only render (byte-identical
    to the legacy renderer)
  - No profiles → `""` (graceful degradation)
- **Source — auto-profile from one band + manual override.**
  `SeriesVoiceService.profile_from_novel()` runs the existing `AuthorVoiceAgent`
  pipeline (the same governed Mode-1 template + hybrid metrics as ANAL-007) over
  one selected band's full chapter prose and stores the assembled
  `AuthorVoiceProfile` as `SeriesSettings.author_voice`. **No new agent.**
- **Opt-out — `ProjectSettings.use_series_voice: bool = True`.** A NOT NULL
  column (migration `0039`, `server_default=true` so existing rows backfill).
  Default True = every series novel inherits the series voice as base; False =
  the novel ignores the series voice.
- **Prompt surface — extend `{{author_voice}}`.** No new prompt variable. The
  `AuthorVoiceConsumer.assemble()` reads series membership + opt-out + both
  profiles, delegates to the pure Delta renderer, returns the composed string.
- **Descriptive/metric boundary preserved** (ADR-055/057) — the Delta renderer
  composes the descriptive-only renderer; `voice_metrics`/`author_metrics` from
  either profile never reach generation.

### Backend (implemented)

- `apps/api/narrare/series/series_voice_contracts.py` —
  `SeriesVoiceServiceProtocol` (RULE-03).
- `apps/api/narrare/series/series_voice_service.py` — `SeriesVoiceService`
  (`profile_from_novel` / `get` / `update_override` / `clear_override`).
  Ownership verified internally (anti-enumeration; mirrors `SeriesService`).
- `apps/api/narrare/series/series_voice_schemas.py` — request/response DTOs
  (split from `apps/api/narrare/series/schemas.py` for RULE-04).
- `apps/api/narrare/series/router_voice.py` — 4 endpoints (thin router).
- `apps/api/narrare/series/dependencies_voice.py` — DI factory.
- `apps/api/narrare/settings/models.py` — `use_series_voice` column.
- `apps/api/narrare/settings/schemas.py` — opt-out on the settings PATCH/GET.
- `apps/api/alembic/versions/0039_series_voice.py` — atomic upgrade + downgrade
  (RULE-14).

### Core (implemented)

- `packages/core/narrare_core/profiles/author_voice.py` —
  `render_author_voice_delta()` (pure; no I/O; byte-identical to legacy for
  standalone).
- `packages/core/narrare_core/profiles/author_voice_consumer.py` —
  `AuthorVoiceConsumer.assemble()` extended to read series voice + opt-out and
  delegate to the Delta renderer.

### Frontend (implemented)

- `packages/web/app/series/[id]/voice/page.tsx` — Voice tab activated
  (placeholder removed).
- `SeriesVoicePanel` + `SeriesVoiceProfileView` (read-only descriptive display)
  + `SeriesVoiceOverrideEditor` (JSON-textarea + local validation).
- `SeriesVoiceOptOutCard` — per-novel opt-out toggle (self-hides for
  standalones); wired into `NovelDetailsTab`.
- TanStack hooks: `useSeriesVoice`, `useProfileSeriesVoice`,
  `useUpdateSeriesVoiceOverride`, `useClearSeriesVoiceOverride`.
- i18n: `series.voice.*` + `novel.settings.useSeriesVoice.*` (en/de/fr parity).

## Constraints & Edge Cases

- **Standalone novels** see no Voice tab effect and no opt-out card; their
  `{{author_voice}}` is byte-identical to the legacy renderer (graceful, not an
  error — RULE-11).
- **Opt-out is binding.** When `use_series_voice=False`, the series voice is
  skipped entirely — the novel uses only its own profile.
- **No new agent / no new prompt variable.** The profiling reuses
  `AuthorVoiceAgent`; the generation surface extends `{{author_voice}}`.
- **`POST …/voice/profile` is synchronous** (one blocking LLM call), rate-limited
  via `AI_ANALYSIS_LIMITER` — matches the band-summary precedent. A progressive
  SSE variant is possible later (the pipeline is stream-capable).
- **Provenance ambiguity.** Auto-profile and manual override share the single
  `SeriesSettings.author_voice` column, so the frontend status badge
  (`autoProfiled` vs `overrideActive`) is optimistic on reload — any non-null
  voice reads as `autoProfiled` until a PATCH transiently flips it. A persisted
  provenance flag is a future schema change (documented in `SeriesVoicePanel`).
- **Metrics are never rendered.** The Voice tab displays descriptive fields
  only; `voice_metrics`/`author_metrics` are loose-typed on the TS side and used
  only for future drift comparison (ADR-074 boundary).
- **Series voice drift across bands** is not handled here — it is Spec 4
  (Cross-Novel Drift). The author can re-profile from any band at any time.

## Related Features

- SERIES-001 (Series Foundation) — Spec 1; this feature populates its empty
  `SeriesSettings.author_voice` column.
- SERIES-002 (Series Generation Context) — Spec 2; the voice tier sits alongside
  the series-history tier at generation time.
- ANAL-007 (Author Voice Profiling) — the `AuthorVoiceAgent` this feature reuses.
- ADR-074 (Author Voice Storage) — Review Trigger Voice-Teil closed by this feature.
- ADR-078 (Series Voice Hierarchy) — full architectural decision.

## Status & History

- **2026-08-05:** Feature spec created as part of Series Voice Hierarchy (Spec 3
  of the Series program); implemented across Core → Backend → Frontend against
  ADR-078 (✅ Implemented). Delta-model renderer, auto-profile-from-band service,
  per-novel opt-out, `{{author_voice}}` extension, Voice tab, and i18n all landed.
  Closes ADR-074 Review Trigger Voice-Teil (FULLY CLOSED) + ADR-075 Spec-3 item.
  Coordinator commit pending.
