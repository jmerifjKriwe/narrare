# Series Cross-Novel Drift — Spec 4 Design

> **Status:** Draft
> **Date:** 2026-08-02
> **Predecessor:** Specs 1-3
> **Successor ADR:** ADR-079 (to be created)

## 1. Context

Spec 4 extends ANAL-009 (Voice Drift) and CONS-001 (Consistency) to series scope. Detects: voice drift from series base + canon contradictions in new bands.

## 2. Design Decisions

| # | Decision | Choice |
|---|----------|--------|
| D1 | What to detect | Voice Drift + Canon-Contradiction (Option B) |
| D2 | Read-scope | Current-band-vs-series-reference (not full-series scan) |
| D3 | Presentation | Integrated in Bände-Tab (no separate tab) |

## 3. Architecture

### Voice Drift (Series-Scope Extension)
- Extends `author_voice_drift` (ANAL-009 Phase 2B)
- Reference: `SeriesSettings.author_voice` metrics (from Spec 3) instead of novel-only baseline
- Reuses: `voice_metric_distances`, `AuthorVoiceDriftAgent`
- If novel has series voice: drift against series base + novel baseline (dual reference)

### Canon-Contradiction (New)
- `SeriesConsistencyAgent` (new Core agent)
- Input: Series-Canon KB entries + chapter text of Band N
- Output: list of conflicts (chapter text contradicts canon)
- Governed template: `analysis/en/series_consistency/system.md`
- 1 LLM call per check
- `SeriesConsistencyService` orchestrates

### API Endpoints
```
POST /api/v1/series/{id}/consistency/check           ← Canon contradictions
POST /api/v1/series/{id}/voice-drift/check            ← Series-scope voice drift
GET  /api/v1/series/{id}/consistency/{novel_id}       ← Results for specific band
```

### Frontend
- "Check Series Consistency" button per band in Bände-Tab
- Results panel: conflicts + drift warnings
- Uses existing analysis panel patterns

## 4. YAGNI
- Character Arc Drift → later
- Full-series batch scan → later
- Automated scheduled checks → later

## 5. Doc Gate
- ADR-079, SERIES-004, GLOSSARY (Series Drift, Canon Contradiction), CURRENT_STATE
