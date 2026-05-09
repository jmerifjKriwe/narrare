---
id: WRITE-009
title: "Writer's Unblock Tools"
status: planned
area: writing
mvp: false

ui_tooltip: "Get unstuck with AI-generated continuation suggestions in different tones."
ui_help_short: |
  Stuck on what to write next? Writer's Unblock analyzes your last paragraphs
  and generates 3 different continuations with varying tones. Choose one to
  continue, or use them as inspiration for your own direction.
ui_help_long: |
  ## Writer's Unblock Tools

  When you're stuck, Writer's Unblock provides multiple paths forward.

  **How it works:**

  1. Place your cursor where you're stuck
  2. Click "Unblock" in toolbar
  3. AI analyzes your last 500-1000 tokens:
     - What's happening in the scene
     - Where the scene could go
     - What feels stuck or unclear
  4. Three continuations appear, each with different tone:
     - **Dramatic**: Raises stakes, intensifies emotions
     - **Quiet**: Focuses on reflection, sensory details
     - **Surprising**: Introduces unexpected twist
  5. Each continuation labeled with confidence score
  6. Choose one to:
     - Accept and continue writing
     - Use as inspiration for your own direction
     - Dismiss and try again

  **Custom tones:**

  Don't like the default options? Specify your own:
  - "tense, humorous, mysterious"
  - "romantic, action-packed, ominous"
  - Any three tones you want to explore

  **Confidence scores:**

  Each suggestion shows how confident the AI is that this continuation fits:
  - 🟢 High confidence (80-100%): Very likely direction
  - 🟡 Medium confidence (50-79%): Possible but risky
  - 🔵 Low confidence (<50%): Experimental direction

  Low confidence isn't bad — it means the suggestion is unexpected or
  creative. Sometimes the best path is the surprising one.

  **When to use:**
  - Scene feels stuck or stagnant
  - Don't know what happens next
  - Want to explore different directions
  - Scene isn't working and unsure why

  **How to use suggestions:**
  - Accept one as-is and continue
  - Take the idea but write it your way
  - Combine elements from multiple suggestions
  - Use as springboard for your own direction

  Writer's Unblock is about possibilities, not prescriptions. The AI suggests
  — you decide.

  Available in Editor → "Unblock" or via CLI:
  `narrare writing unblock --chapter <id> --tones "tense,humorous,mysterious"`
ui_available_in: [editor, cli]

service: writing/unblock_service.py
contract: writing/contracts.py#UnblockProtocol
router: writing/router.py
prompt: core/prompts/_bundled/writing/en/unblock
requires: [INFRA-001, INFRA-002, INFRA-003]
---

# WRITE-009 — Writer's Unblock Tools

## What it does

Analyzes recent text and generates 3 alternative continuations with different
tones/intentions. Each suggestion includes confidence score and rationale.
Designed to break writer's block by offering multiple paths forward.

## Why it exists

Writer's block often means not seeing options. The writer knows what needs to
happen but can't find the path. Unblock shows multiple possibilities, sparking
ideas and getting words flowing again.

## How it works (User perspective)

1. Place cursor where you're stuck (or end of chapter)
2. Click "Unblock" in toolbar
3. AI analyzes your last paragraph(s)
4. Three suggestions appear with:
   - Tone label (Dramatic, Quiet, Surprising, or custom)
   - Confidence score percentage
   - 100-300 words of continuation
5. For each suggestion:
   - Read the continuation
   - See AI's reasoning for this direction
   - Click "Accept" to add to chapter
   - Or click "Regenerate" for new options

Default tones: Dramatic (raise stakes), Quiet (reflection), Surprising (twist).
Custom tones available via advanced options.

## How it works (Technical)

**Entry point:** `writing/router.py` → `POST /api/v1/writing/unblock/{chapter_id}`
**Service:** `UnblockService.suggest()` in `writing/unblock_service.py`
**Contract:** `UnblockProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.SUGGEST`

**Analysis phase:**
- Extract last 500-1000 tokens before cursor
- Identify scene state: characters present, location, tension level
- Detect block type: don't know what happens, don't know how to write it, scene feels wrong
- Generate tone-appropriate continuations

**Suggestion generation:**
- Three parallel LLM calls (one per tone)
- Each call gets scene analysis + tone instruction
- Continuation limited to 100-300 words
- Self-assessment: model estimates confidence score

**Response format:**
```python
class UnblockSuggestion:
    tone: str  # "dramatic", "quiet", "surprising", etc.
    continuation: str
    confidence: float  # 0-1
    reasoning: str  # why this direction makes sense
    word_count: int
```

**Tone definitions:**
- **Dramatic**: Increase conflict, raise stakes, intensify emotions
- **Quiet**: Focus on internal state, sensory details, reflection
- **Surprising**: Introduce unexpected element, shift direction
- **Tense**: Build anticipation, impending threat
- **Humorous**: Lighten mood, introduce comedy
- **Custom**: User-specified tone

## Constraints & Edge Cases

- Minimum 100 words of existing text for analysis
- Maximum 3 suggestions per call (UI limit)
- Confidence scores are self-assessed (may be inaccurate)
- Suggestions may contradict plot intentions
- Very short recent text = poor analysis quality
- LLM availability required

## Related Features

- [WRITE-003](WRITE-003-extend.md) — Direct continuation
- [WRITE-008](WRITE-008-multi-draft.md) — Multiple full drafts
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot guidance
- [PLAN-002](../planning/PLAN-002-gap-analysis.md) — Gap analysis

## Status & History

- `project-init` — Added to registry as planned feature
