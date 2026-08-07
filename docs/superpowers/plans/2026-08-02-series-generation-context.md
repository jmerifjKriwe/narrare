# Series Generation Context — Spec 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` for tracking.

**Goal:** Implement Series Generation Context (Spec 2) — BandSummaryAgent, SeriesHistoryTier, KB-Redirect, auto/manual/lazy band-summary generation, configurable recency-window, full UI.

**Architecture:** New "Series History" context tier (Tier 5) with own token budget. BandSummaryAgent aggregates chapter summaries into full + short band summaries. KB-Redirect: series novels use `find_merged_for_novel()` (Canon+Overlay) instead of per-novel KB. `{{series_history}}` governed prompt variable.

**Spec source:** `docs/superpowers/specs/2026-08-02-series-generation-context-design.md`

## Global Constraints

- Python 3.14+, `from __future__ import annotations` in all new modules
- RULE-02/02a/02b: prompts only in `core/prompts/`; no inline f-string prompts in services
- RULE-03: contracts before implementation
- RULE-04/05/06/07: modularize, module boundaries, one responsibility per file, one-way deps
- RULE-11: graceful degradation (standalone novels → no series history, no crash)
- RULE-14: model change needs migration in same task
- RULE-22: `{{series_history}}` must be registered in prompt-surface-manifest + route_table
- TDD: failing test first, then impl, then green, then commit (ADR-014)
- Pre-commit hooks: NEVER `--no-verify`
- Skill: `building-pydantic-ai-agents` for BandSummaryAgent patterns
- i18n: en/de/fr simultaneously

---

## File Structure

### New Core
- `packages/core/narrare_core/agents/band_summary_agent.py` — BandSummaryAgent
- `packages/core/narrare_core/agents/band_summary_types.py` — BandSummaryDeps, BandSummaryOutput
- `packages/core/narrare_core/context/series_history.py` — SeriesHistoryTier

### New Backend
- `apps/api/narrare/series/band_summary_models.py` — BandSummary SQLAlchemy model
- `apps/api/narrare/series/band_summary_contracts.py` — BandSummaryRepositoryProtocol
- `apps/api/narrare/series/band_summary_repository.py` — DB queries
- `apps/api/narrare/series/band_summary_service.py` — generate, get_or_generate, update_override
- `apps/api/narrare/series/router_band_summary.py` — API endpoints
- `apps/api/narrare/series/tasks.py` — TaskIQ background task for auto-generation

### New Backend (prompt registration)
- Modify `core/prompts/route_table.py` — add `context_mode = "band_summary"` to SUMMARIZE intent
- Modify `core/prompts/prompt-surface-manifest.yaml` — register `band_summary` context_mode
- New template: `core/prompts/_bundled/{category}/en/band_summary/system.md`

### New Migration
- `apps/api/alembic/versions/0038_band_summaries.py`

### New Frontend
- `packages/web/lib/hooks/useBandSummary.ts`
- `packages/web/components/series/BandSummaryCard.tsx`
- `packages/web/components/series/ContextWindowSetting.tsx` (or integrate into SeriesSettings)

### Modified Backend
- `apps/api/narrare/writing/` — KB-Redirect in writing context assembler
- `apps/api/narrare/series/service.py` — auto-trigger on status→completed
- `apps/api/narrare/series/dependencies.py` — DI for band summary service
- `apps/api/narrare/_app/main.py` — wire new router

### Modified Core
- `packages/core/narrare_core/context/` — integrate SeriesHistoryTier into writing assembler
- `packages/core/narrare_core/prompts/` — register `{{series_history}}` variable

---

## Task 1: BandSummary Model + Migration 0038

**Files:** `band_summary_models.py`, Alembic `0038`, test
**Produces:** `BandSummary` SQLAlchemy model; `series_settings.context_window_size` column

- [ ] Write failing test: model table exists with expected columns
- [ ] Implement `BandSummary` model (novel_id UNIQUE FK, full_summary, short_summary, override, generated_at)
- [ ] Write Alembic 0038: create table + add context_window_size to series_settings
- [ ] Run tests + `just check-architecture`
- [ ] Commit: `feat(api/series): add BandSummary model + migration 0038`

---

## Task 2: BandSummaryAgent (Core)

**Files:** `band_summary_types.py`, `band_summary_agent.py`, governed template, test
**Produces:** `BandSummaryAgent` with `BandSummaryOutput(full_summary, short_summary)`

- [ ] Write types: `BandSummaryDeps(chapter_summaries: list[str], novel_title: str, genre: str)`, `BandSummaryOutput(full_summary: str, short_summary: str)`
- [ ] Register `context_mode = "band_summary"` in route_table for `LLMIntent.SUMMARIZE`
- [ ] Create governed template: `core/prompts/_bundled/{lang}/band_summary/system.md` — instructs LLM to produce full + short summary from chapter summaries
- [ ] Register in prompt-surface-manifest.yaml
- [ ] Implement `BandSummaryAgent(NarrareAgent)` — 1 LLM call, structured output
- [ ] Write test (TestModel): verify output structure
- [ ] Run tests + `just check`
- [ ] Commit: `feat(core/agents): add BandSummaryAgent + governed template`

---

## Task 3: BandSummaryRepository + Service (Backend)

**Files:** `band_summary_contracts.py`, `band_summary_repository.py`, `band_summary_service.py`, test
**Produces:** CRUD + generate + lazy + override

- [ ] Write contracts: `BandSummaryRepositoryProtocol` (get, upsert, get_override, set_override, clear_override)
- [ ] Implement repository
- [ ] Implement service: `generate(novel_id)` → fetch chapter summaries → run agent → upsert; `get_or_generate(novel_id)` → lazy; `update_override(novel_id, override)`
- [ ] Write tests (Fake-based per ADR-030)
- [ ] Run tests + check
- [ ] Commit: `feat(api/series): add BandSummaryService + repository`

---

## Task 4: Band Summary API Endpoints + DI

**Files:** `router_band_summary.py`, `dependencies.py` (modify), `main.py` (wire), test
**Produces:** 4 HTTP endpoints

```
POST   /api/v1/series/{id}/novels/{novel_id}/band-summary
GET    /api/v1/series/{id}/novels/{novel_id}/band-summary
PATCH  /api/v1/series/{id}/novels/{novel_id}/band-summary
DELETE /api/v1/series/{id}/novels/{novel_id}/band-summary/override
```

- [ ] Implement router (thin, delegates to service)
- [ ] Add DI factory
- [ ] Wire into app
- [ ] Write router tests (status codes, auth)
- [ ] Commit: `feat(api/series): add Band Summary API endpoints`

---

## Task 5: Auto-Trigger (TaskIQ Background Task)

**Files:** `tasks.py`, `service.py` (modify — enqueue on status→completed)
**Produces:** automatic band summary generation when series is marked completed

- [ ] Create `tasks.py`: `generate_band_summary_task(novel_id)` — calls BandSummaryService.generate
- [ ] Register task in TaskIQ broker
- [ ] Modify SeriesService.update_series: when status transitions to "completed", enqueue task for each novel
- [ ] Write test: verify task enqueued on status change
- [ ] Commit: `feat(api/series): auto-trigger band summary on series completion`

---

## Task 6: SeriesHistoryTier (Core)

**Files:** `series_history.py`, test
**Produces:** Context tier that assembles band summaries + wiki states with recency-window

- [ ] Implement `SeriesHistoryTier.assemble(novel_id, series_id, window_size, token_budget)`:
  1. Fetch novels 1..N-1 by series_position
  2. Last `window_size` bands: full_summary (or override)
  3. Older bands: short_summary
  4. Fetch wiki entity summaries for Band N-1
  5. Format as "Previously in this series:" text block
  6. Truncate to token_budget
- [ ] Handle edge cases: Band 1 (no prior), standalone (series_id=None → empty), missing summaries (lazy trigger or skip)
- [ ] Write tests: recency-window logic, token truncation, override preference, standalone graceful degradation
- [ ] Commit: `feat(core/context): add SeriesHistoryTier with recency-window logic`

---

## Task 7: KB-Redirect + SeriesHistoryTier Integration + Prompt Variable

**Files:** writing context assembler (modify), prompt variable registration
**Produces:** KB-Redirect for series novels + `{{series_history}}` wired into writing pipeline

- [ ] Modify writing context assembler: KB tier uses `find_merged_for_novel()` for series novels
- [ ] Register `{{series_history}}` as SYSTEM_VAR in variable registry
- [ ] Add SeriesHistoryTier to writing pipeline tier structure (Tier 5)
- [ ] Wire SeriesHistoryTier output into `{{series_history}}` variable
- [ ] Update writing prompt templates: include `{{series_history}}` slot (graceful when empty)
- [ ] Regression: standalone generation unchanged (series_id=None → no redirect, no history)
- [ ] Write tests: KB redirect for series vs standalone, tier integration
- [ ] Commit: `feat(core): KB-Redirect + SeriesHistoryTier integration + {{series_history}} variable`

---

## Task 8: Frontend — Hooks + Band Summary Card + Settings Slider

**Files:** `useBandSummary.ts`, `BandSummaryCard.tsx`, Settings modification, tests
**Produces:** UI for band summaries + context window configuration

- [ ] Implement hooks: `useBandSummary`, `useGenerateBandSummary`, `useUpdateBandSummaryOverride`, `useClearBandSummaryOverride`
- [ ] Implement `BandSummaryCard` component (show full/short, regenerate button, override textarea, clear override)
- [ ] Integrate into BändeList (per-band row shows BandSummaryCard)
- [ ] Add Context Window slider to SeriesSettings (1-10, default 3)
- [ ] Write component tests + hook tests
- [ ] Run `pnpm tsc --noEmit` + `pnpm vitest run`
- [ ] Commit: `feat(web/series): add Band Summary card + context window setting`

---

## Task 9: Frontend — i18n (en/de/fr)

**Files:** `studio.json` (3 locales)
**Produces:** all new keys for band summary + context window

- [ ] Add keys: `series.bandSummary.*`, `series.settings.contextWindow.*`
- [ ] Verify i18n parity (en==de==fr)
- [ ] Commit: `feat(web/i18n): add band summary + context window keys`

---

## Task 10: Doc Gate

**Files:** ADR-076, SERIES-002, GLOSSARY, CURRENT_STATE, cross-spec notes
**Produces:** all mandatory documentation

- [ ] Write ADR-076 (mirror ADR-075 structure)
- [ ] Write SERIES-002 feature spec
- [ ] Update GLOSSARY (Band Summary, Series History, Context Window)
- [ ] Update CURRENT_STATE
- [ ] Update cross-spec notes (Spec 2 complete)
- [ ] Commit: `docs(series): Final Doc Gate — ADR-076, SERIES-002`

---

## Execution Order

```
Task 1 (Model + Migration) → Task 2 (Agent) → Task 3 (Service) → Task 4 (API) → Task 5 (Auto-trigger)
                                                                              ↓
Task 6 (SeriesHistoryTier) → Task 7 (Integration + Prompt) → Task 8 (Frontend) → Task 9 (i18n) → Task 10 (Doc Gate)
```

Tasks 1-5 are backend sequential. Tasks 6-7 depend on Tasks 1-2. Tasks 8-9 depend on Tasks 4+7. Task 10 after all.
