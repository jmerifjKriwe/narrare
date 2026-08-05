---
id: SERIES-002
title: "Series Generation Context"
status: stable
area: series
mvp: false  # post-MVP (Phase 6); Spec 2 of the Series program

ui_tooltip: "Give the AI the story so far when writing the next book in a series."
ui_help_short: |
  When you write a novel that belongs to a series, Narrare automatically gives
  the AI a "Previously in this series" summary of the earlier bands — the
  shared canon world, the most recent bands in full, older bands as a one-line
  recap. You can edit any band's auto-generated summary to correct or steer it.
ui_help_long: |
  Series Generation Context is what makes a series *feel* like a series to the
  AI. Each novel in a series gets a **Band Summary**: an auto-generated recap
  of what happened in that book, plus a one-sentence short version. When you
  generate the next band, Narrare assembles a "Previously in this series" block
  from those summaries — the most recent bands in full, older bands as a brief
  line — and feeds it to the AI alongside the shared canon Knowledge Base.

  You stay in control:
  - **Regenerate** any band's summary on demand.
  - **Override** the auto-generated text with your own (the AI uses your version
    within the recency window).
  - **Clear** an override to return to the generated text.

  The AI also reads the **merged canon Knowledge Base** (shared world rules,
  canonical characters) for series novels — not just that book's local entries.

  **API Endpoints:**
  - `GET /api/v1/series/{id}/novels/{novelId}/band-summary` — read a band summary
  - `POST /api/v1/series/{id}/novels/{novelId}/band-summary` — (re)generate
  - `PATCH /api/v1/series/{id}/novels/{novelId}/band-summary` — set the override
  - `DELETE /api/v1/series/{id}/novels/{novelId}/band-summary/override` — clear override
  - `GET /api/v1/series/{id}/settings` — settings (incl. `context_window_size`)

  **UI Location:** `/series/[id]` workspace → Bände tab → a novel's
  **Band Summary Card** (expandable; shows generated text, regenerate, and the
  override editor).

ui_available_in: [series-workspace]

service: series/band_summary_service.py
contract: series/band_summary_contracts.py#BandSummaryServiceProtocol
router: series/router_band_summary.py
prompt: core/prompts/_bundled/analysis/en/band_summary/system.md
requires: [SERIES-001]  # Spec 2 builds on the Series entity + hybrid KB scope
---

# SERIES-002 — Series Generation Context

## What it does

Give the AI prior-band context when generating a novel that belongs to a
series. Each band gets an auto-generated summary; the most recent bands feed
the AI a full recap, older bands a one-line recap, and the shared canon KB is
merged in. The author can edit (override) any band's summary.

## Why it exists

Spec 1 (SERIES-001) gave Narrare the Series entity and a shared canon
Knowledge Base — but generating book N still saw **no prior-band state**. The
AI had to be re-told where book N−1 ended, which characters had been
introduced, and what the established world rules were. This is the
generation-time consumer of Spec 1's foundation: it closes the
state-at-(N−1) gap so a series reads as one continuous story.

This is Spec 2 of 5 in the Series program. Spec 1 (Foundation) is implemented;
Spec 3 (Voice Hierarchy), Spec 4 (Cross-Novel Drift), and Spec 5 (Export)
remain downstream.

## How it works (User perspective)

1. Open a novel that belongs to a series (the Bände tab in the Series
   workspace).
2. Each novel shows an expandable **Band Summary Card**.
3. If no summary exists yet, click **Generate band summary**.
4. The card shows the auto-generated recap + the date it was generated.
5. Click **Regenerate** to re-run the AI summary.
6. To correct or steer it, write your own text in the **Override** box and
   **Save Override** — the AI uses your version. Click **Clear Override** to
   revert.
7. When you generate the next band, the AI automatically receives the
   "Previously in this series" block (recent bands in full, older bands brief)
   plus the shared canon KB.

## How it works (Technical)

- **BandSummary** — a 1:1 row to `Novel` (`novel_id` PK + unique FK
  `ON DELETE CASCADE`): `full_summary`, `short_summary`, optional `override`,
  `generated_at`. Produced by `BandSummaryAgent` (one LLM call, governed
  Mode-1 template) from the band's chapter summaries.
- **SeriesHistoryTier** (pure Core) — assembles the `Previously in this
  series:` block. Recency-window: the last `context_window_size` bands
  (default 3) contribute `override or full_summary`; older bands contribute
  `short_summary` only. Emits newest-first; under token-budget pressure
  (default 512) the oldest entries are truncated then dropped ("sacrifice
  older first").
- **SeriesHistoryProvider** (Backend) — pre-fetches `BandSummaryData` (prior
  bands' summaries + positions + titles), calls the tier, returns the string
  injected into the `{{series_history}}` governed prompt variable.
- **KB-Redirect** — `resolve_kb_fetch_mode()`: series novels read the merged
  Canon+Overlay KB (`find_merged_for_novel`); standalones keep the per-novel
  query.
- **Triple-Trigger generation** — (1) manual POST (the Regenerate button),
  (2) auto on series→`completed` (best-effort TaskIQ enqueue per novel),
  (3) lazy `get_or_generate()` so the tier never blocks on a missing row.
- **Override precedence** — within the recency window, `override` replaces the
  generated full summary (empty-string override falls back to `full`); outside
  the window the override is ignored.
- **Graceful degradation (RULE-11)** — standalone novel, band 1, missing
  summary, empty window, or tiny budget all yield an empty `{{series_history}}`
  block; generation proceeds unchanged.

### Backend (implemented)

- `apps/api/narrare/series/band_summary_models.py` — `BandSummary` ORM.
- `apps/api/narrare/series/band_summary_contracts.py` —
  `BandSummaryRepositoryProtocol`, `BandSummaryServiceProtocol` (RULE-03).
- `apps/api/narrare/series/band_summary_repository.py`,
  `band_summary_service.py` (generate / get_or_generate / update_override),
  `band_summary_auto_trigger.py` (`enqueue_band_summaries`),
  `router_band_summary.py`, `tasks.py`, `dependencies.py`.
- `apps/api/narrare/series/series_history_provider.py` — Backend→Core bridge
  + `resolve_kb_fetch_mode` (KB-Redirect).
- `apps/api/narrare/series/service.py` — `update_series` enqueues band-summary
  generation on the →`completed` transition.
- `apps/api/alembic/versions/0038_band_summaries.py` — atomic `upgrade()` +
  `downgrade()` (RULE-14): `band_summaries` table +
  `series_settings.context_window_size` (default 3).

### Core (implemented)

- `packages/core/narrare_core/context/series_history.py` — `BandSummaryData`
  (frozen dataclass) + `SeriesHistoryTier` (recency-window assembly + budget).
  Pure; no I/O, no `apps/` imports.
- `packages/core/narrare_core/agents/band_summary_agent.py` +
  `agents/band_summary_types.py` — the agent + `BandSummaryDeps` /
  `BandSummaryOutput`.
- `packages/core/narrare_core/prompts/{variable_registry,route_table}.py` —
  `series_history` registered as a governed SYSTEM_VAR.
- `packages/core/narrare_core/writing/{models,pipeline,_stages,context_assembler}.py`
  — `series_history` threaded through `WritingContext` → `WritingPipeline` →
  `{{series_history}}`.

### Frontend (implemented)

- `BandSummaryCard` (expandable: title, override-active badge, generated-at,
  full text, regenerate) + `BandOverrideEditor` (textarea + save/clear).
- TanStack hooks: `useBandSummary`, `useGenerateBandSummary`,
  `useUpdateBandSummaryOverride`, `useClearBandSummaryOverride`.
- i18n: `series.bandSummary.*` (en/de/fr parity).

## Constraints & Edge Cases

- **Standalone novels** see no Band Summary Card and receive an empty
  `{{series_history}}` (graceful, not an error).
- **Band 1** (no prior bands) yields an empty history block.
- **Missing summary row** — skipped, not crashed (RULE-11); the lazy trigger
  can generate on demand.
- **Override is window-scoped** — it curates the *full* record, so it is
  ignored for bands outside the recency window (which use the short summary).
- **`context_window_size` tunability** — the column exists and the provider
  reads it (default 3), but the settings PATCH/GET API surface and the
  user-facing slider to change it are **open work** (tracked below). The
  feature is correct at the default until then.
- **Token estimate** — the tier uses a conservative chars/4 heuristic (no
  `tiktoken` in Core); the writing pipeline's assembler-level budget is
  authoritative.

## Open Work (not blocking stability)

- **Context Window slider** — expose `context_window_size` on
  `SeriesSettingsUpdateRequest` / `SeriesSettingsResponse` (backend, ~2 lines
  each), add the `context_window_size` field to the frontend
  `SeriesSettings` / `SeriesSettingsUpdate` types, add a
  `useUpdateSeriesSettings` hook, and render a 1–10 slider in the Series
  Settings form. i18n keys (`series.settings.contextWindow.*`) already exist
  in en/de/fr. See ADR-077 Review Trigger.

## Related Features

- SERIES-001 (Series Foundation) — Spec 1; this feature consumes its hybrid
  KB scope (`find_merged_for_novel`) and `SeriesSettings`.
- INFRA-003 (Context Assembly) — `{{series_history}}` is a governed context
  variable.
- ADR-077 (Series Generation Context) — full architectural decision.

## Status & History

- **2026-08-02:** Feature spec created as part of Series Generation Context
  (Spec 2 of the Series program); implemented across Core → Backend →
  Frontend against ADR-077 (✅ Implemented). Band summaries, recency-window
  history tier, KB-Redirect, `{{series_history}}` variable, and the
  Triple-Trigger generation all landed. The context-window *slider* (UI to
  tune `context_window_size`) remains open work — the setting works at its
  default of 3.
