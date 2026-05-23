---
id: WRITE-007
title: "Inline AI Suggestions"
status: planned
area: writing
mvp: false

ui_tooltip: "AI autocomplete suggestions appear as you type."
ui_help_short: |
  As you write, gray text appears showing AI's suggested continuation. Press Tab
  to accept the suggestion, or keep typing to ignore it. Like autocomplete,
  but for entire phrases and sentences.
ui_help_long: |
  ## Inline AI Suggestions

  Narrare suggests what you might write next, right in the flow of writing.
  Suggestions appear as ghost text — press Tab to accept, or keep typing to
  ignore.

  **How it works:**

  1. Start typing in your chapter
  2. After a few words, gray text appears: AI's suggestion
  3. Keep typing to ignore (suggestion updates)
  4. Press Tab to accept suggestion
  5. Suggested text becomes real text
  6. Continue writing from there

  **What makes good suggestions:**

  **Completes your sentence**
  - "The door creaked open, revealing" → "a tall figure in the doorway"
  - "Elena's heart" → "raced as she realized the truth"

  **Matches your style**
  - Analyzes your writing patterns
  - Mimics your sentence structure
  - Uses your vocabulary preferences

  **Knows your story**
  - Character names from Knowledge Base
  - Location details
  - Recent story context

  **Controls:**

  - **Enable/disable** in Settings or with keyboard shortcut
  - **Adjust aggressiveness** (suggest after 3/5/10 words)
  - **Accept with** Tab, Enter, or custom keybinding
  - **Dismiss** by continuing to type

  **Best practices:**
  - Use when you're stuck on phrasing
  - Don't over-rely — keep your voice
  - Good for completing routine sentences
  - Less useful for creative, unique passages

  Suggestions update continuously as you type. The more you write, the better
  it knows your style — but it's never perfect. Trust your instincts over the
  suggestion.

  Note: Requires internet connection for AI inference.
ui_available_in: [editor]

service: writing/draft_service.py
contract: writing/contracts.py#DraftServiceProtocol
router: writing/router.py
prompt: core/prompts/_bundled/writing/en/inline_suggest
requires: [INFRA-001, INFRA-002, INFRA-003]
---

# WRITE-007 — Inline AI Suggestions

## What it does

Real-time autocomplete suggestions that appear as ghost text while typing.
Analyzes recent text, chapter context, and Knowledge Base to predict likely
continuations. User accepts with Tab or ignores by continuing to type.

## Why it exists

Writers sometimes struggle with phrasing. They know what they want to say but
not how to say it. Inline suggestions offer completions without breaking flow —
like GitHub Copilot, but for prose.

## How it works (User perspective)

1. Begin typing in your chapter
2. After 3-5 words, gray text appears (AI's suggestion)
3. Either:
   - Press Tab to accept the suggestion
   - Keep typing to ignore it
4. If you ignore, suggestion updates based on new text
5. Continue writing

Suggestions are contextual — they know your characters, your story, and your
writing style.

## How it works (Technical)

**Entry point:** `writing/router.py` → `WebSocket /api/v1/writing/suggest/{chapter_id}`
**Service:** `DraftService.suggest_inline()` in `writing/draft_service.py`
**Contract:** `DraftServiceProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.SUGGEST`
**Protocol:** WebSocket for low-latency streaming

**Triggering:**
- Suggestions requested after N words (configurable, default 5)
- Debounced 300ms after last keystroke
- Not triggered if user is actively typing (prevents distraction)

**Context for suggestions:**
- Last 200 tokens of user's text
- Chapter frontmatter (POV, location)
- Recent chapters (last 1 for continuity)
- KB entries (if entities mentioned)

**Suggestion generation:**
- Model predicts next 10-20 tokens
- Streaming generates suggestion progressively
- Suggestion truncated at sentence end
- Maximum 3 sentences per suggestion

**Frontend behavior:**
- Ghost text rendered in editor
- Disappears if user types a character not matching suggestion
- Tab key accepts entire suggestion
- Escape key dismisses suggestion

**Performance:**
- Target: < 500ms from trigger to display
- Suggestion cached for identical context (reduces API calls)
- Lazy loading after scroll pauses

## Constraints & Edge Cases

- Requires stable internet — no offline mode
- May suggest clichés or generic phrasing
- Doesn't understand plot direction perfectly
- Can be distracting for some writers (disable if so)
- Suggestion quality depends on writing clarity
- May complete sentences in wrong direction
- Not suitable for poetry or highly stylized prose

## Related Features

- [WRITE-003](WRITE-003-extend.md) — Longer continuations
- [WRITE-009](WRITE-009-unblock.md) — When stuck on direction
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Context gathering
- [LEARN-002](../learning/LEARN-002-style-adaptation.md) — Style learning

## Status & History

- `project-init` — Added to registry as planned feature
- `cr-01-audit` — Inline suggest prompt enhanced with negative examples, user preferences, and avoidance patterns
