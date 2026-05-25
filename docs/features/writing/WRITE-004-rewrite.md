---
id: WRITE-004
title: "AI: Rewrite Selection"
status: stable
area: writing
mvp: false

ui_tooltip: "Rewrite selected text with different style, tone, or focus."
ui_help_short: |
  Select any passage and choose how to rewrite it. Change the tone, shift the
  focus, vary the sentence structure, or match a character's voice. Great for
  revision and polishing specific scenes.
ui_help_long: |
  ## AI: Rewrite Selection

  Transform any passage with AI-powered rewriting. Change how something is
  written without changing what happens.

  **Rewrite modes:**

  **Change Tone** 🎭
  - Make it more dramatic or more subdued
  - Add humor or remove it
  - Increase tension or add calm
  - Shift from formal to casual

  **Vary Style** ✍️
  - Simplify or elaborate
  - More sensory details or more action
  - Change sentence structure
  - Adjust pacing

  **Match Voice** 🗣️
  - Rewrite in character's voice
  - Match POV character's personality
  - Use character's speech patterns

  **Fix Issues** 🔧
  - Show, don't tell
  - Remove redundancies
  - Strengthen weak verbs
  - Fix awkward phrasing

  **How it works:**
  1. Select the text you want to rewrite
  2. Click "Rewrite" or right-click → "Rewrite selection"
  3. Choose rewrite mode and specific options
  4. AI generates 1-3 alternatives
  5. Preview each version
  6. Replace your selection, or insert as new

  **Use cases:**
  - "This scene feels flat, make it more dramatic"
  - "Rewrite this dialogue in Elena's voice"
  - "Show this, don't tell it"
  - "Simplify this paragraph"

  Rewriting preserves the essential meaning — it changes the delivery, not the
  content. Always review to ensure your intent is preserved.
ui_available_in: [editor]

service: writing/rewrite_service.py
contract: writing/contracts_rewrite.py#RewriteServiceProtocol
router: writing/router_rewrite.py
prompt: core/prompts/_bundled/writing/en/rewrite_selection
requires: [INFRA-001, INFRA-002, KB-001]
---

# WRITE-004 — AI: Rewrite Selection

## What it does

Rewrites selected text with specified style, tone, or voice changes. Generates
1-3 alternative versions for user review and selection. Preserves semantic
meaning while transforming delivery.

## Why it exists

First drafts are rarely final. Writers need to revise — shift tone, strengthen
voice, show instead of tell. Manual rewriting is slow and mentally draining.
AI rewriting accelerates revision while preserving author control.

## How it works (User perspective)

1. Select any passage in your chapter (sentence to several paragraphs)
2. Right-click and select "Rewrite" or click "Rewrite" in toolbar
3. Choose mode:
   - **Tone**: dramatic, quiet, humorous, tense, etc.
   - **Style**: simpler, more descriptive, more active, etc.
   - **Voice**: specific character's voice
   - **Fix**: show-don't-tell, remove redundancy, etc.
4. AI generates 1-3 alternatives
5. Preview each version side-by-side with original
6. Click to replace your selection, or insert as new

You can also provide custom instructions: "Make this more ominous" or "Focus
on Elena's internal reaction."

## How it works (Technical)

**Entry point:** `writing/router.py` → `POST /api/v1/writing/rewrite`
**Service:** `DraftService.rewrite()` in `writing/draft_service.py`
**Contract:** `DraftServiceProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.REWRITE`

**Rewrite request:**
```python
class RewriteRequest:
    selection_text: str
    chapter_id: UUID
    mode: RewriteMode  # tone, style, voice, fix, custom
    options: dict[str, str]  # mode-specific settings
    character_id: UUID | None  # for voice mode
    count: int = 1  # number of alternatives
```

**Context for rewriting:**
- Selection text (what to rewrite)
- Surrounding context (200 tokens before/after)
- Chapter frontmatter (POV, location)
- Character profile (if voice mode)
- Story context (recent events)

**Rewrite strategies:**
- **Tone shift**: Adjust emotional language, pacing, word choice
- **Style change**: Sentence structure, descriptive density, active/passive
- **Voice matching**: Use character's speech patterns from KB
- **Show don't tell**: Convert statements to scenes
- **Simplify**: Shorten sentences, remove complexity

**Output format:**
- Each rewrite labeled with focus
- Diff view shows changes from original
- One-click replace or insert

## Constraints & Edge Cases

- Selection minimum 50 words, maximum 2000 words
- Voice mode requires character to exist in KB
- May change meaning if instructions are ambiguous
- Rewriting very long selections may lose coherence
- Show-don't-tell may invent details not in original
- Custom instructions require LLM to interpret correctly

## Related Features

- [WRITE-006](WRITE-006-co-author.md) — Interactive rewriting
- [WRITE-008](WRITE-008-multi-draft.md) — Multiple variations
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Voice analysis
- [KB-001](../kb/KB-001-entity-management.md) — Character voice profiles

## Technical Implementation

**SSE-direct endpoint:** `POST /api/v1/writing/chapters/{chapter_id}/rewrite` — same endpoint starts and streams. No two-step start/stream; the endpoint returns an SSE stream immediately.

**Service:** `RewriteService` in `writing/rewrite_service.py` (separate from DraftService per RULE-04). Orchestrates prompt composition, LLM call via Gateway, and streaming response.

**Token budget (`_REWRITE_PERCENTAGES`):** 40/15/25/10/10 — 40% immediate context (selection + surrounding text), 15% recent chapters, 25% KB referenced entities, 10% KB suggested entities, 10% pinned KB entries.

**Structured output format:** Uses `<alternative>` XML tags to delimit each rewrite alternative within the streamed response. The frontend `AlternativeParser` (client-side state machine parser) incrementally parses SSE chunks, extracting individual alternatives as they stream in without waiting for the full response.

**Frontend integration:**
- Reuses existing `BubbleMenu` + `AISuggestion` modal with extensions for rewrite-specific UI (mode selector, alternative preview)
- `RewriteModeSelector` component — tone/style/voice/fix/custom mode picker with sub-options
- `InlineDiff` component — uses `diff-match-patch` for inline diff highlighting between original selection and proposed alternative
- `replaceSelectionWithAIContent()` — atomic selection replacement function that swaps the editor selection with the chosen alternative content in a single transaction, preserving undo history

**Voice mode:** Uses `_voice_profiles.py` from existing KB infrastructure (character_voice_profiles from KBEntity metadata) — same voice extraction pipeline shared with WRITE-003 extend and WRITE-002 draft.

## Status & History

- `project-init` — Added to registry as planned feature
- `cr-01-audit` — Dedicated rewrite prompt template created with CoT, negative examples, and scratchpad pattern
- `2026-05-25` — Implementation: RewriteService, SSE-direct endpoint, AlternativeParser, RewriteModeSelector, InlineDiff, replaceSelectionWithAIContent()
