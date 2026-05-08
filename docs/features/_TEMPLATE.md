---
id: AREA-NNN
title: "Feature Name"
status: planned
area: writing
mvp: false

ui_tooltip: "One sentence. What does clicking this do?"
ui_help_short: |
  2-3 sentences. What does this feature do for the writer?
  Focus on the outcome, not the mechanism.
ui_help_long: |
  Full explanation for writers who want to understand the feature deeply.
  Can include when to use it, when not to, tips for best results.
  Markdown supported. Keep it friendly and non-technical.
ui_available_in: []

service: path/to/service.py
contract: path/to/contracts.py#ProtocolName
router: path/to/router.py
prompt: core/prompts/_bundled/area/en/feature/system.md
requires: []
---

# [AREA-NNN] — Feature Name

## What it does

[1-3 sentences. Precise. Non-technical. This is what appears in the UI help panel
as the short description. Writers should immediately understand what this does.]

## Why it exists

[Connect to the problem from PROJECT_VISION.md. What specific friction does this remove?
What does a writer feel before and after having this feature?]

## How it works (User perspective)

[Step-by-step from the user's point of view.]

1. The writer does X
2. Narrare does Y in the background
3. The writer sees Z
4. The writer can then do A, B, or C

## How it works (Technical)

**Entry point:** `router/path.py` → `POST /api/v1/...`
**Service:** `ServiceName.method()` in `path/service.py`
**Contract:** `ServiceProtocol` in `path/contracts.py`
**LLM Intent:** `LLMIntent.XXX`
**Prompt:** `core/prompts/_bundled/area/en/feature/system.md`
**Context assembled by:** `core/context/assembler.py` with tiers: [list tiers]
**Streaming:** yes/no

[Any additional technical detail that the Implementation Agent needs.]

## Constraints & Edge Cases

- What the feature cannot do
- Failure modes and how they're handled
- Rate limits or size limits
- What happens when the KB is empty
- What happens when the AI provider is unavailable

## Related Features

- [AREA-NNN](../area/AREA-NNN.md) — how they interact
- [AREA-NNN](../area/AREA-NNN.md) — dependency relationship

## Status & History

- `YYYY-MM-DD` — Added to registry
- `YYYY-MM-DD` — [any significant changes]
