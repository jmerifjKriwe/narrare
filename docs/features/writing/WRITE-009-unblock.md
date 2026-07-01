---
id: WRITE-009
title: "Writer's Unblock Tools"
status: stable
area: writing
mvp: false

ui_tooltip: "Get unstuck with AI-generated story direction suggestions."
ui_help_short: |
  Stuck on what to write next? Writer's Unblock suggests several possible
  story directions — plot developments, character moments, dialogue options,
  world details, or stylistic alternatives — each tied to your established
  threads. Use one as inspiration, or take the idea and write it your way.
ui_help_long: |
  ## Writer's Unblock Tools

  When you're stuck, Writer's Unblock suggests several possible paths forward.

  **How it works:**

  1. Open the "Writer's Unblock" panel in the editor
  2. Optionally describe what you're stuck on (e.g. "the scene feels flat,
     I don't know what the antagonist should do next")
  3. Click "Get Suggestions"
  4. The AI analyses your story context and returns 3–5 story direction
     suggestions, each labelled by category:
     - **Plot Development** — move the plot forward
     - **Character Moment** — reveal or develop a character
     - **Dialogue Option** — a line or exchange to try
     - **World Detail** — expand the setting/lore
     - **Stylistic Alternative** — a different way to write the scene
  5. Each suggestion shows a title, a one-paragraph description, and how it
     connects to your established plot threads
  6. For each suggestion you can:
     - **Accept** — insert it and keep writing
     - **Dismiss** — go back to the form
     - **Regenerate** — ask for fresh suggestions

  **When to use:**
  - A scene feels stuck or stagnant
  - You don't know what happens next
  - You want to explore different directions
  - A scene isn't working and you're unsure why

  **How to use suggestions:**
  - Accept one as-is and continue
  - Take the idea but write it your way
  - Combine elements from multiple suggestions
  - Use them as a springboard for your own direction

  Writer's Unblock is about possibilities, not prescriptions. The AI
  suggests — you decide.

  Available in the Editor → "Writer's Unblock".
ui_available_in: [editor]

service: apps/api/narrare/writing/story_suggest_service.py
contract: apps/api/narrare/writing/contracts_story_suggest.py
router: apps/api/narrare/writing/router_story_suggest.py
prompt: core/prompts/_bundled/writing/en/story_suggest/system.md
requires: [INFRA-001, INFRA-002, INFRA-003]
---

# WRITE-009 — Writer's Unblock Tools

## What it does

Generates 3–5 story direction suggestions (plot developments, character
moments, dialogue options, world details, or stylistic alternatives) to help
you get unstuck. Each suggestion carries a title, a one-paragraph description,
and an explanation of how it connects to your established plot threads.
Designed to break writer's block by offering several paths forward.

## Why it exists

Writer's block often means not seeing options. The writer knows what needs to
happen but can't find the path. Unblock shows multiple possibilities, sparking
ideas and getting words flowing again.

## How it works (User perspective)

1. Open the "Writer's Unblock" panel in the editor
2. Optionally describe what you're stuck on in the "Stuck?" field
3. Click "Get Suggestions"
4. The AI returns 3–5 story direction suggestions, each with:
   - A category (Plot Development, Character Moment, Dialogue Option,
     World Detail, or Stylistic Alternative)
   - A short title
   - A one-paragraph description
   - A note on how it connects to your established plot threads
5. For each suggestion:
   - Read the description and connection
   - Click "Accept" to insert the suggestion into your chapter
6. Use "Dismiss" to return to the form, or "New suggestions" to regenerate

Suggestions are advisory — accept one, take the idea and write it your way,
or combine elements from several.

## How it works (Technical)

**Entry point:** `apps/api/narrare/writing/router_story_suggest.py` → `POST /api/v1/writing/story-suggest/{novel_id}` (SSE)
**Service:** `StorySuggestService.suggest()` in `apps/api/narrare/writing/story_suggest_service.py`
**Contract:** `StorySuggestServiceProtocol` in `apps/api/narrare/writing/contracts_story_suggest.py`
**Schemas:** `StorySuggestRequest` / `StorySuggestionResponse` / `StorySuggestStreamEvent` in `apps/api/narrare/writing/schemas_story_suggest.py`
**Factory:** `get_story_suggest_service()` in `apps/api/narrare/writing/deps_story_suggest.py`
**LLM Intent:** `LLMIntent.SUGGEST` with `context_mode="story_suggest"` (the SUGGEST intent is a multi-mode intent — `inline_suggest` is the existing ghost-text mode; `story_suggest` is the WRITE-009 direction-suggestions mode)

**Prompt resolution (ADR-054 D1 / Mode 1):**
- The governed packages/core/narrare_core/prompts/_bundled/writing/{locale}/story_suggest/system.md template (v1.3.0) carries the task framing and project-metadata variables.
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

- Returns 3–5 suggestions per call (the exact count is AI-determined within that range)
- Optional `author_instructions` ("Stuck?" field) is capped at 2000 characters
- There are no confidence scores — use your own judgement on whether a direction fits
- Suggestions are AI-generated and may contradict your plot intentions — review before accepting
- Scoping to a chapter is optional; without a `chapter_id`, suggestions use the wider novel context
- Accepting a suggestion inserts AI-generated text — edit it as you would any draft
- LLM availability required

## Related Features

- [WRITE-003](WRITE-003-extend.md) — Direct continuation
- [WRITE-008](WRITE-008-multi-draft.md) — Multiple full drafts
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot guidance
- [PLAN-002](../planning/PLAN-002-gap-analysis.md) — Gap analysis

## Status & History

- `project-init` — Added to registry as planned feature
- 2026-06-25 — Implemented: `StorySuggestAgent` (Core), `StorySuggestService` + contract + schemas + SSE router + DI factory (Backend), `UnblockPanel` + `UnblockSuggestionCard` + `useUnblockStream` hook + SSE client (Frontend), i18n (en/de/fr), AI Operation Inventory registered (`writing.story_suggest`). Closes AUFG-04-01.
- 2026-06-26 — User-facing spec sections rewritten to match the implemented story-direction-suggestions behaviour (the original tone-based-continuations concept was superseded by the `story_suggest` template design). UnblockPanel split for RULE-04 (269→169 lines). Status → `stable`.
