# Series Cross-Novel Drift — Spec 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement series-scope voice drift + canon-contradiction detection.

**Spec source:** `docs/superpowers/specs/2026-08-02-series-cross-novel-drift-design.md`

## Global Constraints
- Python 3.14+, `from __future__ import annotations`
- RULE-01b/02/03/04/05/06/07/11/14/22 as usual
- TDD, NEVER `--no-verify`, i18n en/de/fr
- **Regression:** standalone ANAL-009/CONS-001 tests must stay green

---

## Task 1: SeriesConsistencyAgent (Core)

- Types: `SeriesConsistencyDeps`, `SeriesConsistencyOutput` (conflicts list)
- Agent: `SeriesConsistencyAgent(NarrareAgent)` — LLM compares chapter text vs canon entries
- Governed template: `analysis/en/series_consistency/system.md`
- Route table: `LLMIntent.ANALYSE` + `context_mode = "series_consistency"`
- Tests (TestModel)
- Commit: `feat(core/agents): add SeriesConsistencyAgent`

## Task 2: SeriesConsistencyService + API (Backend)

- Contracts, repository (store/retrieve results), service (orchestrate agent)
- API: `POST /api/v1/series/{id}/consistency/check`, `GET /api/v1/series/{id}/consistency/{novel_id}`
- DI factory, wire router
- Tests (Fake-based)
- Commit: `feat(api/series): add SeriesConsistencyService + API endpoints`

## Task 3: Voice Drift Series-Scope Extension

- Extend `AuthorVoiceDriftService` / `AuthorVoiceDriftAgent` to use series voice as additional reference
- When novel has series voice: compute drift against series base (not just novel baseline)
- API: `POST /api/v1/series/{id}/voice-drift/check`
- **Regression:** standalone drift unchanged when no series voice
- Tests + voice-lane regression
- Commit: `feat(api/analysis): extend voice drift with series-scope reference`

## Task 4: Frontend — Consistency Panel

- Hooks: `useSeriesConsistency`, `useSeriesVoiceDrift`
- Component: series consistency results panel (conflicts + drift warnings)
- "Check" button in Bände-Tab per band
- Component tests
- Commit: `feat(web/series): add series consistency + drift panel`

## Task 5: i18n + Doc Gate

- i18n keys for consistency/drift UI (en/de/fr)
- ADR-079, SERIES-004, GLOSSARY, CURRENT_STATE
- Commit: `docs(series): Spec 4 Doc Gate — ADR-079, SERIES-004`

---

## Execution Order

Task 1 → Task 2 → Task 3 → Task 4 → Task 5
