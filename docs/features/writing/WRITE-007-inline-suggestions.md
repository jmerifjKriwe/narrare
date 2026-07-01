---
id: WRITE-007
title: "Inline AI Suggestions"
status: stable
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

service: apps/api/narrare/writing/suggest_service.py
contract: apps/api/narrare/writing/contracts.py#SuggestServiceProtocol
router: apps/api/narrare/writing/router_suggest.py
prompt: packages/core/narrare_core/prompts/_bundled/writing/en/inline_suggest/system.md
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

**Core layer:**
- **Agent:** `InlineSuggestAgent` (NarrareAgent subclass) in `packages/core/narrare_core/agents/inline_suggest_agent.py`
- **Deps:** `InlineSuggestDeps` in `packages/core/narrare_core/agents/inline_suggest_types.py`
- **Prompts:** 3 locale templates (en/de/fr) in packages/core/narrare_core/prompts/_bundled/writing/{locale}/inline_suggest/system.md
- **Variable engine:** `text_before`, `text_after`, `chapter_context` variables
- **LLM Intent:** `LLMIntent.SUGGEST`

**Backend layer:**
- **Entry point:** `POST /api/v1/writing/chapters/{chapter_id}/suggest` (SSE endpoint)
- **Service:** `InlineSuggestService` in `apps/api/narrare/writing/suggest_service.py` — chapter validation, rate limiting, minimal context assembly
- **Contract:** `SuggestServiceProtocol` in `apps/api/narrare/writing/contracts.py`
- **Router:** `apps/api/narrare/writing/router_suggest.py` (dedicated per RULE-04)
- **Dependencies:** `apps/api/narrare/writing/deps.py` → `get_suggest_service()`
- **Protocol:** Server-Sent Events (SSE) for low-latency streaming

**Triggering:**
- Suggestions requested after N words (configurable, default 5)
- Debounced 300ms after last keystroke (configurable via GhostTextConfig)
- Not triggered if user is actively typing (prevents distraction)

**Context for suggestions:**
- `text_before`: text before cursor position
- `text_after`: text after cursor position
- Chapter context (frontmatter, POV, location)
- KB entries (if entities mentioned)

**Suggestion generation:**
- Model predicts next 10-20 tokens
- Streaming generates suggestion progressively via SSE
- Suggestion truncated at sentence end
- Maximum 3 sentences per suggestion

**Frontend layer:**
- **Extension:** `packages/web/components/studio/editor/extensions/GhostText.ts` TipTap extension (ProseMirror Decoration.widget) — streaming, accept/reject/word-accept, prefix cache, analytics
- **Settings:** `packages/web/components/studio/editor/GhostTextConfig.tsx` — enable/disable toggle + delay slider
- **API client:** `createSseSuggestionFetcher()` in `packages/web/lib/api/suggest.ts` — real SSE integration
- **Styles:** CSS in `packages/web/styles/editor.css`
- Ghost text rendered as ProseMirror Decoration.widget
- Disappears if user types a character not matching suggestion
- Tab key accepts entire suggestion
- Escape key dismisses suggestion
- Word-level accept via ArrowRight

**Performance:**
- Target: < 500ms from trigger to display
- Suggestion cached for identical context (reduces API calls)
- Lazy loading after scroll pauses

**Testing:**
- Core: 12 unit tests for InlineSuggestAgent
- Backend: 11 integration tests for suggest endpoint
- Frontend: GhostTextConfig.test.tsx, suggest.test.ts, mocks in EditorView/TipTapEditor tests

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
- `2026-05-29` — Full implementation: InlineSuggestAgent (core) + SSE endpoint (backend) + GhostText TipTap extension (frontend). 23 backend tests, frontend tests. ADR-016 accepted. Feature → stable.
