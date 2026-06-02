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

## UX Requirements

> This section is MANDATORY for features involving AI interaction.
> If the feature has NO AI component, replace with:
> "Not applicable — this feature does not involve AI interaction."

### AI Interaction Type
- [ ] Generation — produces new content
- [ ] Suggestion — inline ghost text
- [ ] Analysis — structured feedback/report
- [ ] Extraction — structured data from text
- [ ] Transformation — rewrites existing content
- [ ] Conversation — multi-turn AI session

### Streaming
| Question | Answer |
|----------|--------|
| Backend SSE endpoint exists? | yes / no |
| Frontend uses SSE? | yes / no |
| REST endpoint also needed? | yes / no |

### User Controls
| Control | Required? | i18n key |
|---------|-----------|----------|
| Cancel/Abort | yes / no | `studio.aiActions.stop` |
| Accept | yes / no | `studio.aiActions.accept` |
| Reject | yes / no | `studio.aiActions.reject` |
| Retry | yes / no | `studio.aiActions.retry` |
| Rating | yes / no | `studio.aiActions.rating` |

### Loading States
| Phase | Indicator | Within |
|-------|-----------|--------|
| Initial | [describe] | 200ms |
| Progress | [describe] | continuous |
| Connection lost | Banner + retry | immediate |
| Complete | Accept/Reject buttons | immediate |

### Error Handling
| Scenario | User message (de) | User action |
|----------|-------------------|-------------|
| Context too large | | |
| Timeout | | |
| API error | | |
| Invalid API key | | |
| Rate limited | | |
| No provider | | |
| Connection lost | | |

### Onboarding
| Question | Answer |
|----------|--------|
| Discoverable from | |
| Tooltip needed? | |
| Tour step needed? | |
| First-run guidance? | |

### Accessibility
| Requirement | Implemented? |
|-------------|-------------|
| aria-live for AI output | |
| aria-label on AI buttons | |
| Focus moves to output | |
| Escape cancels | |

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
