---
id: WRITE-009
title: "Writer's Unblock Tools"
status: in-progress
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

service: apps/api/narrare/writing/story_suggest_service.py
contract: apps/api/narrare/writing/contracts_story_suggest.py
router: apps/api/narrare/writing/router_story_suggest.py
prompt: core/prompts/_bundled/writing/en/story_suggest/system.md
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

**Entry point:** `apps/api/narrare/writing/router_story_suggest.py` → `POST /api/v1/writing/story-suggest/{novel_id}` (SSE)
**Service:** `StorySuggestService.suggest()` in `apps/api/narrare/writing/story_suggest_service.py`
**Contract:** `StorySuggestServiceProtocol` in `apps/api/narrare/writing/contracts_story_suggest.py`
**Schemas:** `StorySuggestRequest` / `StorySuggestionResponse` / `StorySuggestStreamEvent` in `apps/api/narrare/writing/schemas_story_suggest.py`
**Factory:** `get_story_suggest_service()` in `apps/api/narrare/writing/deps_story_suggest.py`
**LLM Intent:** `LLMIntent.SUGGEST` with `context_mode="story_suggest"` (the SUGGEST intent is a multi-mode intent — `inline_suggest` is the existing ghost-text mode; `story_suggest` is the WRITE-009 direction-suggestions mode)

**Prompt resolution (ADR-054 D1 / Mode 1):**
- The governed `core/prompts/_bundled/writing/{locale}/story_suggest/system.md` template (v1.3.0) carries the task framing and project-metadata variables.
- The service resolves it through `PromptComposer` via `compose_invocation(intent=LLMIntent.SUGGEST, prompt_context=PromptContext(mode="story_suggest", ...))`. No inline f-string feature prompt is assembled in the service (RULE-02 / RULE-02a / RULE-02b).
- pydantic-ai binds `system_prompt` at agent construction, so the composed system prompt is passed to the `StorySuggestAgent` constructor.

**Core layer:**
- `StorySuggestAgent` (`packages/core/narrare_core/agents/story_suggest_agent.py`) — a `NarrareAgent` with `output_type=StorySuggestOutput` (structured JSON output) and `SYSTEM_PROMPT_KEY = "story_suggest"`.
- Types (`packages/core/narrare_core/agents/story_suggest_types.py`): `StorySuggestDeps` (project-level runtime data: title, genre, writing language), `StorySuggestOutput`, `StorySuggestion`, `StorySuggestionType` (`plot_development`, `character_moment`, `dialogue_option`, `world_detail`, `stylistic_alternative`).

**Suggestion generation:**
- A single agent run produces 3–5 distinct story direction suggestions (plot developments, character moments, dialogue options, world details, stylistic alternatives).
- Each suggestion carries a `title`, a one-paragraph `description`, and a `connection` explaining how it ties to established plot threads.

**Response / streaming format:**
- The SSE stream emits a single `"suggestions"` event carrying the full structured list, followed by a `"done"` termination event (`is_final=True`), and finally a `data: [DONE]` signal. Unlike the streaming-text writing services, there are no incremental text chunks — the structured output is returned atomically.
- Non-streaming schema `StorySuggestResponse` exists for callers that want the full list at once.

```python
class StorySuggestionResponse:
    type: str            # "plot_development", "character_moment", "dialogue_option",
                         #   "world_detail", "stylistic_alternative"
    title: str           # brief descriptive title
    description: str     # one-paragraph description of the suggestion
    connection: str      # how this connects to established plot threads
```

**Reconciliation note:** WRITE-009 uses the existing `story_suggest` template (story direction suggestions) rather than the original spec's tone-based continuations concept. This closes [AUFG-04-01](../../architecture/governance/aufg-registry.md) — the previously orphan `("writing", "story_suggest")` template now has a production consumer and is reachable via the SUGGEST route. The orphan exemption was removed from `scripts/architecture/_checkers/_check_prompt_orphan.py::_ORPHAN_EXEMPTIONS`.

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
- 2026-06-25 — Implemented: `StorySuggestAgent` (Core), `StorySuggestService` + contract + schemas + SSE router + DI factory (Backend), `UnblockPanel` + `UnblockSuggestionCard` + `useUnblockStream` hook + SSE client (Frontend), i18n (en/de/fr), AI Operation Inventory registered (`writing.story_suggest`). Closes AUFG-04-01. Status `in-progress` pending user-facing refinement.
