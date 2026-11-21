---
id: WRITE-003
title: "AI: Extend Chapter"
status: stable
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

service: writing/extend_service.py
contract: writing/contracts_extend.py#ExtendServiceProtocol
router: writing/router_extend.py
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

**Entry point:** `POST /api/v1/writing/chapters/{chapter_id}/extend` (SSE-direct — same endpoint starts and streams)
**Service:** `ExtendService` in `apps/api/narrare/writing/extend_service.py` (separate from DraftService per RULE-04)
**Contract:** `ExtendServiceProtocol` in `apps/api/narrare/writing/contracts_extend.py`
**LLM Intent:** `LLMIntent.EXTEND`
**Streaming:** SSE-direct — no two-step start/stream; the endpoint returns an SSE stream immediately
**Schema:** `ExtendRequest` with `text_before` (required, max 10000), `text_after` (optional, max 2000), `length` (ExtendLength enum: short/medium/long), `tone`, `language`

**Pipeline:** `WritingPipeline._extend()` — direct LLM call via PromptComposer + Gateway (no WritingGraph). Uses `mode="extend_chapter"` in prompt context. Length maps to word targets: short~150, medium~400, long~750.

**Context assembly:** `WritingContextAssembler` with extend-specific budget allocation:
- 50% immediate context (text_before + text_after around cursor)
- 15% recent chapters
- 20% KB referenced entities
- 10% KB suggested entities
- 5% pinned KB entries

**Frontend infrastructure:**
- `AIAnnotation` TipTap Mark (`ai-generated`) with attributes: `request_id`, `source`, `original_text`, `status`, `created_at`
- `AIAnnotationTracker` Plugin — monitors transactions within pending mark ranges, detects modifications, enforces single-pending-mark constraint
- `ContinueButton` — toolbar button with length selector dropdown (short/medium/long), triggers extend flow
- `AIAnnotationActions` — floating accept/reject/rate UI positioned near pending mark
- Standalone lifecycle functions: `insertAIContent()`, `appendToPendingMark()`, `finalizePendingMark()`, `acceptMark()`, `rejectMark()`
- `replaceSelectionWithAIContent()` — atomic selection replacement added as part of WRITE-004 for rewrite support, extending the `aiAnnotationApi` with selection replacement capability. Swaps editor selection with AI content in a single transaction, preserving undo history. Shared by both Extend (replace pending mark content) and Rewrite (swap selected text with alternative).
- Clean Save integration — Autosave removes pending marks before save, records implicit ACCEPT/MODIFY feedback

**Prompt strategy:**
- Pre-text included verbatim: "Here's what came before:"
- Cursor position marked: `[CONTINUE FROM HERE]`
- Style analysis: sentence structure, dialogue ratio from pre-text
- Scene state: what's happening, who's present, what's at stake
- Voice profiles from KB character metadata
- User preferences injected via PromptComposer

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
- `2026-05-24` — Implementation started: Core pipeline (`_extend()`), extend prompts (en/de/fr), extend-specific context budget, Backend API (`ExtendService`, SSE-direct endpoint), Frontend AIAnnotation infrastructure (Mark + Tracker Plugin, ContinueButton, AIAnnotationActions, Clean Save integration)
- `2026-05-25` — **Complete.** 23 new unit tests (12 validation + 11 streaming). Promptfoo eval baseline: evals/extend-chapter.yaml (356 lines, 9 test cases). Architecture validation clean.
