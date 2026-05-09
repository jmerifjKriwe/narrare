---
id: WRITE-003
title: "AI: Extend Chapter"
status: planned
area: writing
mvp: false

ui_tooltip: "Continue your chapter seamlessly from where you stopped writing."
ui_help_short: |
  Place your cursor anywhere in your chapter and click "Continue." Narrare
  reads what you've written, understands the context, and generates a natural
  continuation that matches your style and the current scene.
ui_help_long: |
  ## AI: Extend Chapter

  Continue writing from any point in your chapter with AI assistance. Narrare
  reads your existing text, understands the scene, and generates a seamless
  continuation.

  **How it works:**

  1. Place your cursor where you want to continue
  2. Click "Continue" or press Tab+Enter
  3. AI analyzes:
     - Last 500-1000 tokens (what just happened)
     - Chapter context (POV character, location, goals)
     - Knowledge Base (relevant characters, facts)
  4. Text streams in, continuing naturally from your last sentence
  5. Keep clicking "Continue" to extend further

  **Continue options:**

  **Short** (100-200 words)
  Quick additions — a paragraph of dialogue, a bit of action

  **Medium** (300-500 words)
  Scene extensions — develop the moment, add detail

  **Long** (500-1000 words)
  Significant continuation — advance the scene substantially

  **What makes continuations work:**
  - Reads your actual text for style matching
  - Understands scene context from your writing
  - Knows your characters from the Knowledge Base
  - Maintains narrative consistency

  **Best practices:**
  - Write at least a paragraph before using Continue
  - Set chapter frontmatter (POV, location) for better context
  - Use Continue multiple times for longer passages
  - Edit the output — it's a first draft, not final prose

  Available in Editor toolbar or via keyboard shortcut.
ui_available_in: [editor]

service: writing/draft_service.py
contract: writing/contracts.py#DraftServiceProtocol
router: writing/router.py
prompt: core/prompts/_bundled/writing/en/extend_chapter
requires: [INFRA-001, INFRA-002, INFRA-003, KB-001]
---

# WRITE-003 — AI: Extend Chapter

## What it does

Generates seamless continuations from cursor position. Analyzes recent text,
chapter context, and Knowledge Base to produce natural extensions that match
user's style and scene state.

## Why it exists

Writers get stuck mid-scene. They know what needs to happen but can't find the
words. Continue provides momentum — the AI writes the next paragraph or scene
beat, breaking writer's block and maintaining flow.

## How it works (User perspective)

1. Write at least one paragraph in your chapter
2. Place cursor where you want to continue (anywhere)
3. Click "Continue" in toolbar or press Tab+Enter
4. Choose length: Short (100-200w), Medium (300-500w), Long (500-1000w)
5. Text streams in from your cursor position
6. Keep clicking "Continue" to extend further
7. Edit and refine the generated text

The continuation appears exactly where your cursor was, ready to edit.

## How it works (Technical)

**Entry point:** `writing/router.py` → `POST /api/v1/writing/chapters/{id}/extend`
**Service:** `DraftService.extend()` in `writing/draft_service.py`
**Contract:** `DraftServiceProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.EXTEND`
**Streaming:** Yes — SSE

**Context gathering:**
- **Pre-text**: Last 500-1000 tokens before cursor
- **Post-text**: Next 200 tokens after cursor (for context)
- **Chapter frontmatter**: POV, location, timeline position
- **KB entries**: Characters mentioned, current location
- **Recent chapters**: Last 1-2 chapters for story continuity

**Prompt strategy:**
- Pre-text included verbatim: "Here's what came before:"
- Cursor position marked: "[CONTINUE FROM HERE]"
- Style analysis: sentence structure, dialogue ratio from pre-text
- Scene state: what's happening, who's present, what's at stake

**Generation:**
- Streams from cursor position
- Maintains paragraph structure
- Matches dialogue formatting (quotes, tags)
- Preserves scene tone and momentum

## Constraints & Edge Cases

- Minimum 100 words of existing text for quality continuation
- Maximum 1000 words per continuation (token limits)
- Quality drops if pre-text is very short or fragmented
- May continue in wrong direction if scene is ambiguous
- Cannot "read ahead" — only uses text before cursor
- Requires LLM availability — no offline mode
- May not match intended plot direction (user guides with editing)

## Related Features

- [WRITE-002](WRITE-002-new-chapter.md) — Generate full chapters
- [WRITE-004](WRITE-004-rewrite.md) — Rewrite continuations
- [WRITE-009](WRITE-009-unblock.md) — Alternative for writer's block
- [WRITE-007](WRITE-007-inline-suggestions.md) — Inline autocomplete
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Context gathering

## Status & History

- `project-init` — Added to registry as planned feature
