---
id: WRITE-012
title: "Chapter Summary"
status: planned
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

service: packages/core/writing/summary_service.py
contract: packages/core/writing/contracts.py#SummaryService
router: apps/api/routers/writing/summary.py
prompt: core/prompts/_bundled/writing/en/summary/system.md
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

**Entry point:** `apps/api/routers/writing/summary.py` → `POST /api/v1/chapters/{id}/summarize`
**Service:** `SummaryService.summarize_chapter()` in `packages/core/writing/summary_service.py`
**Contract:** `SummaryServiceProtocol` in `packages/core/writing/contracts.py`
**LLM Intent:** `LLMIntent.SUMMARIZE_CHAPTER`
**Prompt:** `core/prompts/_bundled/writing/en/summary/system.md`
**Streaming:** no

Chapter summary reads the chapter's full content and updates the `summary` field in its frontmatter.

## Constraints & Edge Cases

- Generated summaries typically run 2-4 sentences and focus on plot-relevant information.
- Short chapters receive proportionally shorter summaries.
- Manual summaries are overwritten if automatic generation is triggered.

## Related Features

- [WRITE-002](../writing/WRITE-002-new-chapter.md) — The chapter system where summaries are stored in frontmatter
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Uses chapter summaries as history context for AI writing features
- [CONS-001](../consistency/CONS-001-checker.md) — Uses summaries to understand cross-chapter context during checks

## Status & History

- `2026-05-19` — Added to registry
