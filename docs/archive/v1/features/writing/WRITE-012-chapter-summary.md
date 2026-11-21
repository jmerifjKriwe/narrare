---
id: WRITE-012
title: "Chapter Summary"
status: implemented
area: writing
mvp: false

ui_tooltip: "Generate or view a concise summary of the chapter."
ui_help_short: |
  Automatically generate or manually trigger AI-powered chapter summaries.
  Chapter Summary produces concise summaries of your chapters and stores them in the chapter frontmatter.
ui_help_long: |
  Long novels contain hundreds of chapters and hundreds of thousands of words. Remembering exactly what happened in Chapter 14 when you are writing Chapter 42 is a challenge. Chapter summaries solve this problem by providing a condensed record of each chapter's key events, character developments, and plot advances.
  Narrare can generate summaries automatically when you save a chapter, or you can trigger them manually whenever you want.
ui_available_in: ["editor", "cli", "mcp", "api"]

service: packages/core/narrare_core/agents/summary_agent.py (ChapterSummaryAgent)
contract: apps/api/narrare/writing/summary_contracts.py
router: apps/api/narrare/writing/summary_router.py
prompt: packages/core/narrare_core/prompts/_bundled/analysis/en/summarize/system.md
requires: []
---

# [WRITE-012] — Chapter Summary

## What it does

Automatically generate or manually trigger AI-powered chapter summaries. Chapter Summary produces concise summaries of your chapters and stores them in the chapter frontmatter, powering Context Assembly, consistency checks, and rapid review.

## Why it exists

Remembering exactly what happened in early chapters when writing later ones is a challenge. Chapter summaries provide a condensed record of key events, character developments, and plot advances, removing the friction of having to re-read your own work.

## How it works (User perspective)

1. The writer opens a chapter or enables `AUTO_SUMMARIZE_ENABLED`.
2. Narrare reads the full chapter text and identifies key events, character changes, and plot advances.
3. The AI condenses the events into a concise 2-4 sentence summary.
4. The writer can view the summary in the chapter's frontmatter or edit it manually.

## How it works (Technical)

**Entry point:** `POST /api/v1/planning/summary/chapters/{chapter_id}?novel_id={novel_id}` in `apps/api/narrare/writing/summary_router.py`
**Service/Agent:** `ChapterSummaryAgent` in `packages/core/narrare_core/agents/summary_agent.py` (used directly) + `SummaryService` in `apps/api/narrare/writing/summary_service.py` (API orchestration)
**Contract:** `SummaryServiceProtocol` in `apps/api/narrare/writing/summary_contracts.py`
**LLM Intent:** `LLMIntent.SUMMARIZE` (category: `PLANNING`, mode: `summarize`)
**Prompt:** `packages/core/narrare_core/prompts/_bundled/analysis/en/summarize/system.md`
**Output type:** `SummaryOutput(summary, key_points, word_count, metadata)` in `packages/core/narrare_core/agents/summary_types.py`
**Streaming:** no

The `ChapterSummaryAgent` is a `NarrareAgent` subclass that calls the LLM via the gateway. The API `SummaryService` wraps the agent, handles DB persistence (writes to `chapters.summary`), and handles error scenarios.

**WritingGraph integration:** A `generate_summary` step runs after `finalize` in the WritingGraph (`packages/core/narrare_core/agents/writing_graph.py`). It calls `ChapterSummaryAgent` with the final draft content and stores the result in `ctx.state.summary`, setting status to `WritingStatus.SUMMARIZED`. This means every AI-written chapter gets a summary automatically.

### Storyboard integration

Chapter summaries feed into two storyboard features:

1. **Enhanced sync status:** `StructuralSyncChecker` (in `packages/core/narrare_core/planning/sync.py`) uses `has_summary AND has_content` as a stronger signal for COMPLETED status (Rule 3b), replacing the previous word-count-only heuristic.

2. **AI-powered structure remap:** `AIRemapService` (in `packages/core/narrare_core/planning/remap.py`) analyzes chapter summaries to suggest narrative stage assignments. When ≥50% of chapters have summaries, the remap uses content-aware stage suggestions instead of position-ratio heuristics. Confidence is calculated based on summary coverage ratio.

## Constraints & Edge Cases

- Generated summaries typically run 2-4 sentences and focus on plot-relevant information.
- Short chapters receive proportionally shorter summaries.
- Manual summaries are overwritten if automatic generation is triggered.
- Summary generation adds LLM cost per chapter (configurable via model routing for cheaper models).
- AI remap falls back to position-ratio heuristics when <50% of chapters have summaries.
- The WritingGraph summary step is non-blocking — runs after finalize, does not block the drafting loop.
- Empty chapters produce empty summaries (no LLM call is made).

## Related Features

- [WRITE-002](../writing/WRITE-002-new-chapter.md) — The chapter system where summaries are stored in frontmatter
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Uses chapter summaries as history context for AI writing features
- [CONS-001](../consistency/CONS-001-checker.md) — Uses summaries to understand cross-chapter context during checks
- [PLAN-005](../planning/PLAN-005-storyboard.md) — Consumes summaries for enhanced sync status + AI-powered structure remap
- [PLAN-003](../planning/PLAN-003-structure.md) — Structure adapters used by AI remap for stage classification

## Status & History

- `2026-05-19` — Added to registry
- `2026-05-21` — Implemented: ChapterSummaryAgent, SummaryService + REST endpoint, WritingGraph summary step, storyboard AI integration
