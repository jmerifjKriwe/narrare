---
id: WRITE-008
title: "Multi-Draft Generation"
status: planned
area: writing
mvp: false

ui_tooltip: "Generate 2-5 alternative versions of any passage with labeled differences."
ui_help_short: |
  Can't decide how to write a scene? Generate multiple versions at once and
  compare. Each draft is labeled with its focus and strengths/weaknesses.
  Combine elements from different versions or pick your favorite.
ui_help_long: |
  ## Multi-Draft Generation

  Generate 2-5 alternative versions of a passage simultaneously, then compare
  and choose the best approach.

  **How it works:**

  1. Select a passage or describe a scene
  2. Click "Multi-Draft" in toolbar
  3. Choose:
     - Number of drafts (2-5)
     - Variation focus (tone, style, approach)
     - Or specify different variations: "dramatic, quiet, humorous"
  4. AI generates all drafts in parallel
  5. Compare versions side-by-side:
     - Each draft labeled with its focus
     - Strengths and weaknesses listed
     - Word count for each
  6. Choose what to do:
     - Accept one draft as-is
     - Combine elements from multiple drafts
     - Use as inspiration for your own version

  **Variation types:**

  **By tone** 🎭
  - Dramatic vs subdued
  - Tense vs relaxed
  - Humorous vs serious
  - Hopeful vs bleak

  **By style** ✍️
  - Detailed vs sparse
  - Internal vs external focus
  - Action vs dialogue
  - Fast vs slow pacing

  **By approach** 🎯
  - Direct vs subtle
  - Surprise vs foreshadowing
  - Character vs plot focus
  - Beginning vs middle vs ending in media res

  **Comparative overview:**
  - Side-by-side view of all drafts
  - Highlight differences between versions
  - Rank by quality, emotional impact, pacing
  - See which draft best achieves your goal

  **Best practices:**
  - Start with 3 drafts (manageable comparison)
  - Use for key scenes, not every passage
  - Combine elements — don't feel bound to one draft
  - Trust your instincts over AI's rankings

  Multi-draft is perfect when you're unsure which direction to take or want
  to explore possibilities before committing.

  Available in Editor → "Multi-Draft" or via CLI:
  `narrare writing multi-draft --chapter <id> --count 3 --variations "dramatic,quiet,humorous"`
ui_available_in: [editor, cli]

service: writing/multi_draft_service.py
contract: writing/contracts.py#MultiDraftProtocol
router: writing/router.py
prompt: core/prompts/_bundled/writing/en/multi_draft
requires: [INFRA-001, INFRA-002, KB-001]
---

# WRITE-008 — Multi-Draft Generation

## What it does

Generates 2-5 alternative versions of a passage with specified variations.
Each draft is labeled with its focus, strengths, and weaknesses. Provides
comparative tools for side-by-side evaluation and element combination.

## Why it exists

Writers face endless choices in how to write a scene. Single-pass generation
locks in one approach. Multi-draft lets writers explore possibilities, compare
options, and combine the best elements from each version.

## How it works (User perspective)

1. Select passage or describe scene (for new content)
2. Click "Multi-Draft" in toolbar
3. Configure:
   - Number of drafts: 2, 3, 4, or 5
   - Variation type: tone, style, or custom
   - Specific variations (optional): "dramatic, quiet, mysterious"
4. AI generates all drafts (15-60 seconds)
5. Review results:
   - Each draft in its own panel
   - Labels show focus and intent
   - Strengths/weaknesses listed
   - Word counts displayed
6. Compare views:
   - Side-by-side mode
   - Differences highlighted
   - Rank by quality/emotion/pacing
7. Choose action:
   - Accept one draft
   - Combine selected drafts
   - Use as inspiration only

Drafts are saved to a buffer. Accept one to replace selection, or open in
editor for manual combination.

## How it works (Technical)

**Entry point:** `writing/router.py` → `POST /api/v1/writing/multi-draft`
**Service:** `MultiDraftService.generate()` in `writing/multi_draft_service.py`
**Contract:** `MultiDraftProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.WRITE` (parallel calls)

**Request:**
```python
class MultiDraftRequest:
    base_text: str | None  # selection to rewrite, or None for new
    chapter_id: UUID
    count: int  # 2-5
    variations: list[str] | None  # ["dramatic", "quiet", ...]
    mode: "tone" | "style" | "approach" | "custom"
```

**Generation:**
- Parallel LLM calls (one per draft)
- Each call gets unique variation instruction
- Shared context (KB, recent chapters)
- Drafts generated independently (no cross-contamination)

**Response:**
```python
class DraftResult:
    id: UUID
    text: str
    variation: str  # what this draft focused on
    strengths: list[str]
    weaknesses: list[str]
    word_count: int
    quality_score: float  # 0-1, self-assessed
```

**Comparative analysis:**
- Optional second pass analyzes all drafts together
- Identifies unique elements in each draft
- Suggests best draft for different goals
- Highlights differences between versions

## Constraints & Edge Cases

- Maximum 5 drafts per generation (token/cost limits)
- Minimum 2 drafts (comparison requires at least 2)
- Very long selections (>3000 words) slow generation
- Quality varies across drafts — not all will be good
- Comparison requires LLM call (adds time and cost)
- Custom variations may be misinterpreted

## Related Features

- [WRITE-002](WRITE-002-new-chapter.md) — Single-draft generation
- [WRITE-004](WRITE-004-rewrite.md) — Single-variation rewrite
- [WRITE-006](WRITE-006-co-author.md) — Iterative improvement
- [ANAL-010](../analysis/ANAL-010-literary-suite.md) — Draft analysis

## Status & History

- `project-init` — Added to registry as planned feature
