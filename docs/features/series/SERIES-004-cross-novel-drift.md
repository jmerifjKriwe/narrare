---
id: SERIES-004
title: "Series Cross-Novel Drift"
status: stable
area: series
mvp: false  # post-MVP (Phase 6); Spec 4 of the Series program

ui_tooltip: "Check a band against the series canon and voice for contradictions or drift."
ui_help_short: |
  When you write a novel in a series, Narrare can check it against the series'
  shared canon (fixed world rules) and the series voice (the prose style shared
  across all bands). It flags canon contradictions and narrator drift so each
  band still feels like part of the same series.
ui_help_long: |
  Series Cross-Novel Drift is what keeps a series *coherent* as it grows. Each
  band you add is checked against two series-level references:

  - **Canon contradictions** — the series has a shared **Canon KB** (magic
    systems, world rules, canonical character bios — the fixed facts every band
    must respect). This check compares a band's chapter prose against the Canon
    and flags anything that contradicts it ("the canon says magic requires a
    spoken incantation, but this chapter has a mage casting silently"). Each
    conflict names the canon statement, the contradicting excerpt, and a
    severity (error / warning).
  - **Series voice drift** — the series has a shared **Series Voice** (the prose
    style that makes every band sound like part of the same series). This check
    measures the current band's narrator against the series voice baseline and
    reports how far it has drifted, chapter by chapter.

  The check is **per-band** (it evaluates the band you are working on against
  the series references — not a full-series batch scan). An empty result is
  normal and good: no contradictions, no drift.

  This is a **read-only** check — it reports; it does not rewrite. Canon
  contradictions are factual errors you should fix; voice drift may be
  intentional (an experimental band). You stay in control.

  **API Endpoints:**
  - `POST /api/v1/series/{id}/consistency/check` — canon-contradiction check
    (body: `{novel_id}`; returns a list of conflicts)
  - `POST /api/v1/series/{id}/voice-drift/check` — series-scope voice drift
    (body: `{novel_id}`; returns the aggregate drift result)
  - `GET /api/v1/series/{id}/consistency/{novel_id}` — *(deferred)* results
    retrieval (persistence is a follow-up)

  **UI Location:** `/series/[id]` workspace → **Bände-Tab** → per-band
  "Check Series Consistency" affordance + results panel
  (`SeriesDriftPanel` → canon conflicts + voice-drift summary).

ui_available_in: [series-workspace]

service: series/series_consistency_service.py
contract: series/series_consistency_contracts.py#SeriesConsistencyServiceProtocol
router: series/router_consistency.py
prompt: core/prompts/_bundled/analysis/en/series_consistency/system.md
requires: [SERIES-001, SERIES-003, ANAL-009]  # Canon KB from Spec 1; series voice from Spec 3; voice-drift pipeline from ANAL-009 Phase 2B
---

# SERIES-004 — Series Cross-Novel Drift

## What it does

Detect two kinds of cross-novel drift when writing a novel in a series: (1)
**canon contradictions** — the band's prose contradicts the series' shared Canon
KB; (2) **series voice drift** — the band's narrator has drifted from the series
voice baseline. Per-band, read-only, on-demand.

## Why it exists

Spec 1 (SERIES-001) gave Narrare the Series-Canon KB — the cross-novel
fixed-facts layer. Spec 3 (SERIES-003) gave the series a shared foundational
voice. But once a series has both a shared canon and a shared voice, a new
question arises with every new band: *does this book still belong?*

A band can fail to belong in two ways:
- **Factually** — it contradicts the canon (a mage casts silently though the
  canon says magic requires speech). This is almost always an error.
- **Stylistically** — it drifts from the series voice (the series is spare and
  literary; this band has become verbose and colloquial). This may be
  intentional (an experimental book) or accidental.

Without a cross-novel check, these problems are caught only at reader-complaint
time. This feature is the cross-novel complement of CONS-001 (which checks
*within* one novel) and ANAL-009 (which checks narrator drift *within* one
novel).

This is Spec 4 of 5 in the Series program. Specs 1–3 are implemented.
Spec 5 (Export) was retired 2026-08-14 as YAGNI (PO decision); the Series
program is complete with Specs 1–4.

## How it works (User perspective)

1. Open a series workspace and go to the **Bände-Tab**.
2. For the band you are working on, click **Check Series Consistency**.
3. Narrare compares the band's chapter prose against the series Canon and the
   series voice.
4. The results panel shows:
   - **Canon conflicts** — each with the canon statement, the contradicting
     excerpt, an explanation, and a severity (error / warning).
   - **Voice drift** — how far the band's narrator has drifted from the series
     voice, chapter by chapter, with a classification.
5. An empty result means no contradictions and no notable drift — that is
   normal and good.
6. The check is **read-only** — it reports; you decide what to fix. Canon
   contradictions are factual errors; voice drift may be intentional.

## How it works (Technical)

- **Canon-Contradiction — new `SeriesConsistencyAgent`.** One LLM call per
  check. Input: the series **Canon KB** entries (read via
  `KBRepository.find_canon_for_series`) + the current band's chapter prose.
  Output: a list of `CanonConflict` (`canon_statement`, `chapter_text_excerpt`,
  `explanation`, `severity ∈ {error, warning}`). An empty list is valid (no
  contradictions). Mirrors the `BandSummaryAgent` 1-call Output-Function +
  ADR-035 validator pattern. Governed Mode-1 template
  `packages/core/narrare_core/prompts/_bundled/analysis/en/series_consistency/system.md`.
- **Series Voice Drift — reuses `AuthorVoiceDriftAgent`.** No new drift agent.
  The new `SeriesVoiceDriftService` computes the band's per-chapter narrator
  metrics (reusing `compute_author_voice_per_chapter`), loads the series voice
  (`SeriesSettings.author_voice` via `SeriesRepository`), and runs the existing
  `analyse_author_voice_drift` with the **series** metrics as the trend
  baseline. Returns the aggregate `AuthorVoiceDriftResponse`. The series voice
  is treated as **one signal** (a trend baseline), not a fixed template — per
  ADR-078's Review Trigger.
- **Read-scope — current-band-vs-series.** Each check evaluates the current
  band against the series references. Full-series batch scan is deferred (YAGNI).
- **Persistence — stateless (v1).** The v1 check runs the agent and returns the
  result; it persists nothing. A results repository + the
  `GET …/consistency/{novel_id}` retrieval endpoint are deferred.

### Core (implemented)

- `packages/core/narrare_core/agents/series_consistency_agent.py` —
  `SeriesConsistencyAgent` (NarrareAgent subclass; 1-call Output-Function +
  ADR-035 validator).
- `packages/core/narrare_core/agents/series_consistency_types.py` —
  `CanonConflict`, `SeriesConsistencyDeps`, `SeriesConsistencyOutput`.
- `packages/core/narrare_core/prompts/_bundled/analysis/en/series_consistency/system.md` —
  governed Mode-1 template.

### Backend (implemented)

- `apps/api/narrare/series/series_consistency_{contracts,service,schemas,prompt,runtime_content}.py` —
  canon-contradiction vertical (RULE-03/04/06).
- `apps/api/narrare/series/router_consistency.py` —
  `POST /api/v1/series/{id}/consistency/check`.
- `apps/api/narrare/series/series_voice_drift_{contracts,service,schemas}.py` —
  series-scope voice drift (reuses ANAL-009 Phase 2B pipeline).
- `apps/api/narrare/series/router_voice_drift.py` —
  `POST /api/v1/series/{id}/voice-drift/check`.
- Ownership verified internally (anti-enumeration; mirrors `SeriesService`).

### Frontend (implemented)

- Bände-Tab "Check Series Consistency" affordance per band (band selector +
  two checks: canon consistency + voice drift) + results panel
  (`SeriesDriftPanel` → `SeriesConflictList` + `SeriesDriftSummary`),
  integrated in the Bände-Tab (no separate tab).
- TanStack hooks (`useSeriesDrift`) + TS types (RULE-17 parity).

### i18n (implemented)

- `series.drift.*` namespace in `packages/i18n/messages/{en,de,fr}/studio.json`
  (en/de/fr parity) — consolidates
  the canon-consistency and voice-drift copy under one namespace (not the
  originally-predicted `consistency` / `voiceDrift` split).

## Constraints & Edge Cases

- **Standalone novels** see no check (the canon check is series-scoped — no
  series → no Canon; the voice-drift endpoint is series-scoped). Their novel-
  level drift (`POST /analysis/author-voice-drift/{novel_id}`) and per-novel
  consistency (CONS-001) are unchanged.
- **Empty Canon / empty chapters** → graceful no-op: the canon check returns an
  empty conflicts list without an LLM call (RULE-11).
- **Missing series voice / voice with no metrics** → graceful `no_profile`
  result: the voice-drift check skips without an LLM call (RULE-11).
- **Severity model** — `error` (a hard canon contradiction) or `warning` (a
  possible contradiction). There is no "info" tier because every Canon conflict
  is actionable.
- **Read-only.** The check reports; it does not rewrite. Voice drift may be
  intentional; canon contradictions are errors you should fix.
- **Stateless v1.** Each check re-runs the agent (no persistence). A results
  repository + retrieval endpoint are a follow-up.
- **JSON, not SSE.** Both endpoints return JSON (matching the design doc's
  `POST …/check` shape). An SSE variant is possible later.
- **Metrics never reach generation.** The series-voice drift reuses
  `author_metric_distances`, which is comparison-only (ADR-055/057 boundary).

## Related Features

- SERIES-001 (Series Foundation) — Spec 1; provides the Series-Canon KB this
  feature reads.
- SERIES-003 (Series Voice Hierarchy) — Spec 3; provides the
  `SeriesSettings.author_voice` baseline this feature's voice drift uses.
- ANAL-009 (Voice Drift Detection) — the per-novel author-voice drift pipeline
  this feature reuses for the series-scope drift.
- CONS-001 (Consistency Checker) — the per-novel consistency checker; this
  feature's canon-contradiction check is the cross-novel complement.
- ADR-079 (Series Cross-Novel Drift) — full architectural decision.

## Status & History

- **2026-08-06:** Feature spec created as part of Series Cross-Novel Drift
  (Spec 4 of the Series program). Implemented against ADR-079 (✅ Implemented)
  — all five slices shipped (Core Task 1: `SeriesConsistencyAgent`; Backend
  Tasks 2–3: `SeriesConsistencyService` + `SeriesVoiceDriftService` + APIs;
  Frontend Task 4: `SeriesDriftPanel` → `SeriesConflictList` +
  `SeriesDriftSummary`; i18n Task 5: the `series.drift.*` namespace, en/de/fr).
  Frontend Task 4 + i18n Task 5 landed in commit `ede62081`; merged to `main`
  via PR #145 (squash `c007b559`). **Stateless v1** — Slice 6 (persistence:
  results repository + `GET …/consistency/{novel_id}` retrieval) is deferred
  out-of-v1. Closes ADR-078's Spec-4 Review-Trigger item (series voice read as
  one signal via the repository contract). Status → `stable`. The Series
  program Spec 1–4 is complete; Spec 5 (Export) was retired 2026-08-14 as
  YAGNI (PO decision).
