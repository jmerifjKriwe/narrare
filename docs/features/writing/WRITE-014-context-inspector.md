---
id: WRITE-014
title: "Context Inspector"
status: stable
area: writing
mvp: false

ui_tooltip: "See what context the AI uses before generating text."
ui_help_short: |
  Before the AI writes, Context Inspector shows you what it knows —
  which characters, locations, and chapters were loaded, what tone is set,
  and how much of your Knowledge Base made it into the prompt.
ui_help_long: |
  ## Context Inspector

  Ever wonder what the AI actually "sees" before it writes? Context Inspector
  lifts the curtain on the context assembly process, so you can trust that
  the AI is working with the right information.

  **What it shows:**

  - **Entity counts** — How many characters, locations, and factions from your
    Knowledge Base were included in the prompt.
  - **Entity names** — The actual names of included entities (up to 5 characters,
    3 locations) displayed as chips in the expanded panel.
  - **Tone** — Which writing tone is active for this generation.
  - **Recent chapters** — How many previous chapters were loaded for continuity.
  - **Budget** — The total token budget allocated for context.
  - **Flags** — Whether your writing preferences are active, or if this is the
    first chapter (which means less prior context).

  **How to use it:**

  The Context Inspector appears in the GenerationPanel as soon as you start
  a generation. Click the info bar to expand the detail panel and see entity
  names and flags.

  **Why check it?**

  - If the AI ignores a character, check if they appear in the entity list —
    they may not have been relevant enough to include.
  - If the tone feels wrong, verify the active tone in the inspector.
  - If results seem generic, a low entity count tells you to enrich your
    Knowledge Base.

  Available in the Editor whenever AI generation is active.
ui_available_in: [editor]

service: writing/service.py
contract: writing/contracts.py#WritingServiceProtocol
router: writing/router.py
requires: [INFRA-003, WRITE-002]
---

# WRITE-014 — Context Inspector

## What it does

Shows authors exactly what context was assembled for the LLM before text
generation begins. Displays entity counts, entity names, tone, budget allocation,
and key flags in an expandable panel inside the GenerationPanel.

## Why it exists

CR-07 (UI/UX audit) rated AI transparency at ⭐⭐/5. Authors had no visibility
into what the AI "sees" — context assembly was a black box. This created distrust:
when the AI produced unexpected results, authors couldn't tell whether the problem
was the context, the prompt, or the model. Context Inspector makes the assembly
process transparent, giving authors the information they need to debug and trust
AI output.

## How it works (User perspective)

1. Author starts a generation (new chapter, extend, or scene-by-scene)
2. Before text streams in, a compact info bar appears in the GenerationPanel
   showing entity counts: "3 Characters · 1 Location · 2 Recent"
3. Author clicks the bar to expand the detail panel
4. Detail panel shows entity name chips (e.g., "Anna", "Johann", "Försterhaus"),
   active tone, token budget, and flags like "Preferences active"
5. Author can use this information to adjust their KB or generation settings
6. Inspector remains visible throughout the generation

## How it works (Technical)

**Core module:** `packages/core/narrare_core/writing/`
**API module:** `apps/api/narrare/writing/`
**Frontend module:** `packages/web/components/studio/editor/`

### Data flow

```
WritingContext.to_metadata() → ContextMetadata → StreamChunk.context_meta
    → SSE event {"type": "context_meta", ...}
    → streamGeneration onContextMeta callback
    → ContextInspector component
```

### Core layer

- **`ContextMetadata` dataclass** in `packages/core/narrare_core/writing/context_models.py` — lightweight
  summary with entity counts, names, flags, tone, and budget.
- **`WritingContext.to_metadata()`** in `packages/core/narrare_core/writing/models.py` — extracts metadata
  from the full writing context. Counts entities by scanning `### ` markers;
  forwards names from assembler-populated lists.
- **`StreamChunk.context_meta`** in `packages/core/narrare_core/llm/result.py` — optional dict field
  (default `None`) carrying context metadata on the first chunk only.

### Backend layer

- **SSE emission** in `apps/api/narrare/writing/router.py` — `event_stream()` generator checks
  `chunk.context_meta` and emits `{"type": "context_meta", ...}` as the first
  SSE event before any text chunks.
- **`ContextMetaResponse`** in `apps/api/narrare/writing/schemas.py` — Pydantic schema with all
  15 fields matching `ContextMetadata.to_dict()`.
- **Pipeline integration** in `packages/core/narrare_core/writing/pipeline.py` — after context assembly,
  yields `StreamChunk(text="", context_meta=meta_dict)` as the first chunk.

### Frontend layer

- **`ContextMeta` interface** in `packages/web/lib/api/generation.ts` — TypeScript type
  matching the backend schema exactly (RULE-17).
- **`streamGeneration`** in `packages/web/lib/api/generation.ts` — SSE client with
  `onContextMeta` callback. Parses `context_meta` events and routes them
  to the callback before processing text chunks.
- **`ContextInspector`** component in `packages/web/components/studio/editor/ContextInspector.tsx`
  — expandable panel with compact info bar (entity counts) and detail panel
  (entity name chips, tone, budget, flags).
- **`GenerationPanel`** integration — holds `contextMeta` state, resets on new
  generation, passes meta to `ContextInspector`.

### SSE protocol

```
data: {"type": "context_meta", "kb_characters_count": 3, ...}   ← first event
data: {"text": "Once upon a time..."}                            ← text chunks follow
data: {"text": "...", "is_final": true, "usage": {...}}
data: [DONE]
```

### i18n

All user-facing strings extracted to `contextInspector.*` keys in
`packages/i18n/messages/en/studio.json`, `packages/i18n/messages/de/studio.json`, and
`packages/i18n/messages/fr/studio.json` (12 keys per language).

### Tests

| Layer | File | Tests |
|-------|------|-------|
| Core | `tests/unit/core/writing/test_context_metadata.py` | 13 |
| Backend unit | `tests/unit/api/writing/test_writing_service_meta.py` | 4 |
| Integration | `tests/integration/writing/test_writing_sse_meta.py` | 3 |
| Component | `packages/web/components/studio/editor/__tests__/ContextInspector.test.tsx` | 6 |
| Panel | `packages/web/components/studio/editor/__tests__/GenerationPanel.test.tsx` (meta portion) | 3 |

## Constraints & Edge Cases

- Context metadata is computed once at generation start — it does not update
  if the KB changes during streaming.
- Entity name chips show at most 5 characters + 3 locations; overflow is
  indicated with "more...".
- When the KB is empty (no entities), the inspector shows "No context assembled"
  — this is expected for new projects.
- The inspector returns `null` (renders nothing) when `meta` is `null`, which
  covers pre-generation and error states.
- First chapters have no previous context; the "First chapter" flag signals
  this to the author.
- Token budget shows as rounded thousands (e.g., "8k") for readability.
- The `context_meta` SSE event is not guaranteed if context assembly fails
  before yielding the first chunk — in that case, text streaming may still
  proceed without context metadata.

## Related Features

- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Provides the context assembly pipeline that feeds metadata
- [WRITE-002](WRITE-002-new-chapter.md) — Primary consumer: new chapter generation
- [WRITE-005](WRITE-005-interactive-session.md) — Context also visible during interactive sessions
- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — User preferences flag shown in inspector

## Status & History

- `2026-05-24` — Implemented as CR-AUFG-07-01 (CR-07 audit finding: AI transparency ⭐⭐/5). Core data model, SSE protocol extension, frontend component, i18n (en/de/fr), 29 tests across all layers.
