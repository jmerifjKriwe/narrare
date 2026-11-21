---
id: WRITE-013
title: "Writing Workflows"
status: planned
area: writing
mvp: false

ui_tooltip: "High-level overview of AI-assisted writing processes."
ui_help_short: |
  Transform your ideas into high-quality prose through iterative AI-human collaboration.
  Follow a structured framework from idea to final draft.
ui_help_long: |
  Narrare doesn't just "generate" a novel—it provides a structured framework for authors to refine their vision from a single spark into a complete, consistent story.
  Workflows cover outline drafting, progressive drafting, context proposal generation, and iterative feedback loops like Co-Authoring and Voice Checking.
ui_available_in: ["editor", "docs"]

service: ""
contract: ""
router: ""
prompt: ""
requires: []
---

# [WRITE-013] — Writing Workflows

## What it does

Defines and documents the holistic creative process within Narrare, outlining how an author transitions from a spark of an idea to an outline, drafts scenes, and iteratively collaborates with AI tools to polish their novel.

## Why it exists

Users need a mental model of how to effectively use Narrare. A collection of features is not a writing process. Writing Workflows bridges the gap, showing how tools like Context Assembly, Co-Author Mode, and Voice Checking interlock to support the natural creative lifecycle.

## How it works (User perspective)

1. **Idea to Outline**: The writer jots a rough concept, uses AI planning tools to expand it, and breaks it into chapters.
2. **Drafting Chapters**: The AI proposes context when a chapter is opened. The writer progressively drafts using "Continue" or "Draft from Outline".
3. **Feedback Loop**: The writer uses Multi-Draft generation to compare variations, Co-Author mode to brainstorm specifics, and Voice Checker to ensure consistency, teaching the AI their style via rejection learning.

## How it works (Technical)

**Entry point:** N/A - Architectural/Workflow Concept
**Service:** Composition of multiple `packages/core/writing/*` services.
**Streaming:** yes (various points in the workflow)

This represents the orchestrating logic that ties disparate writing tools together.

## Constraints & Edge Cases

- Workflows are highly subjective; writers may deviate entirely.

## Related Features

- [WRITE-006](../writing/WRITE-006-co-author.md) — Co-Author mode
- [WRITE-008](../writing/WRITE-008-multi-draft.md) — Multi-Draft Generation
- [ANAL-011](../analysis/ANAL-011-plot-analysis.md) — Plot Analysis

## Status & History

- `2026-05-19` — Added to registry
