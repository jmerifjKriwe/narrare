---
id: INFRA-005
title: "Memory Layer (Rejection Learning)"
status: planned
area: infra
mvp: false

ui_tooltip: "AI learns from your feedback to improve suggestions over time."
ui_help_short: |
  Narrare learns from your writing choices. When you accept, reject, or modify
  AI suggestions, the system remembers your preferences and adapts future
  suggestions to match your style and taste.
ui_help_long: |
  ## Memory Layer & Rejection Learning

  Narrare's Memory Layer enables the AI to learn from your feedback over time.
  The more you write with Narrare, the better it understands your preferences.

  **How feedback works:**

  **Accept** ✓
  You used the suggestion exactly as provided.
  → AI learns: "This style/approach works for this user"

  **Reject** ✗
  You dismissed the suggestion.
  → AI learns: "Avoid this pattern for this user"

  **Modify** ✎
  You used the suggestion but made changes.
  → AI learns: "This was close, but needed adjustment"

  **What the AI tracks:**

  **Style Preferences**
  - Sentence structure (short vs long, complex vs simple)
  - Descriptive density (sparse vs rich description)
  - Dialogue patterns (realistic vs stylized)
  - Metaphor usage frequency

  **Content Preferences**
  - Themes and genres you prefer
  - Character types you write well
  - Plot patterns you enjoy
  - Pacing tendencies

  **Structure Preferences**
  - Scene length preferences
  - Chapter organization patterns
  - Transition styles
  - Exposition vs action balance

  **How it affects suggestions:**
  Future AI operations include your preference profile as context.
  Accepted patterns appear more often; rejected patterns appear less.
  The AI gradually adapts to your unique voice.

  **Reset and control:**
  - View your preference profile in Settings
  - Reset preferences when changing creative direction
  - Disable learning entirely if preferred
  - Export preferences for backup/analysis

  Learning happens automatically. Your data stays private — preferences are
  stored locally, never shared with any service.
ui_available_in: [settings]

service: core/memory/service.py
contract: ~
router: ~
prompt: ~
requires: [INFRA-001]
---

# INFRA-005 — Memory Layer (Rejection Learning)

## What it does

Persistent preference learning system that tracks user feedback on AI suggestions
(accept/reject/modify) and builds a preference profile. Future AI operations
include this profile as context to better match user's style and taste.

## Why it exists

One-size-fits-all AI suggestions frustrate writers. What works for literary
fiction fails for thriller writers. What one author loves, another hates.
The Memory Layer enables Narrare to adapt to each writer's unique voice and
preferences over time.

## How it works (User perspective)

1. You interact with AI suggestions (accept, reject, or modify)
2. Narrare records your choice in the background
3. Preference profile updated with pattern analysis
4. Future suggestions influenced by your profile
5. Over time, suggestions match your style better

Most users don't need to think about it — it just gets better. Power users can:
- View preference profile in Settings
- See what patterns the AI has learned
- Reset when changing creative direction
- Disable if they don't want learning

## How it works (Technical)

**Entry point:** `core/memory/service.py`
**Primary class:** `MemoryService` (mem0 integration)
**Storage**: PostgreSQL + local cache
**Key operations**: `record_feedback()`, `get_preferences()`, `reset()`

**Feedback collection:**
```python
await memory.record_feedback(
    suggestion_id=uuid,
    action="accept",  # | "reject" | "modify"
    context={
        "intent": LLMIntent.WRITE,
        "chapter_id": uuid,
        "suggestion_text": str,
        "modification": str | None,  # if modified
    }
)
```

**Pattern extraction:**
- Style features extracted from suggestions
- User's modifications analyzed for delta
- Patterns clustered: positive (do more) vs negative (avoid)
- Confidence scores track pattern strength

**Preference profile structure:**
```python
{
    "style": {
        "sentence_length": "medium",  # short/medium/long
        "description_density": 0.7,  # 0-1
        "dialogue_ratio": 0.3,  # 0-1
        # ... more features
    },
    "content": {
        "preferred_themes": ["redemption", "mystery"],
        "avoided_tropes": ["love_triangle", "chosen_one"],
        # ... more
    },
    "structure": {
        "avg_scene_length": 2500,  # words
        "pacing_preference": "balanced",  # slow/balanced/fast
        # ... more
    }
}
```

**Integration with prompts:**
- Preferences injected as prompt variables
- Example: `{{user_style偏好}}` in system prompt
- Weight: 10-20% of context budget (secondary to content)

## Constraints & Edge Cases

- Requires minimum 20 feedback events before patterns emerge
- Cold start: No adaptation until data accumulated
- Conflicting signals: Accept/reject of similar patterns both recorded
- Reset required for major creative direction changes
- Learning can be disabled (fallback to default behavior)
- Privacy: All data stored locally, never transmitted

## Related Features

- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — User-facing feedback collection
- [LEARN-002](../learning/LEARN-002-style-adaptation.md) — Style profile application
- [WRITE-006](../writing/WRITE-006-co-author.md) — Co-author benefits from learning
- [INFRA-002](INFRA-002-prompt-system.md) — Prompts consume preference variables

## Status & History

- `project-init` — Added to registry as planned feature
