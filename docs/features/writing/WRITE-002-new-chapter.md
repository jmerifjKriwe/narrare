---
id: WRITE-002
title: "AI: New Chapter Generation"
status: stable
area: writing
mvp: true

ui_tooltip: "Generate complete chapter drafts from outline or prompts."
ui_help_short: |
  Narrare can write complete chapter drafts based on your outline, scene notes,
  or a simple prompt. The AI uses your Knowledge Base to maintain consistency
  with characters, locations, and established facts.
ui_help_long: |
  ## AI: New Chapter Generation

  Generate complete chapter drafts with AI assistance. From a detailed outline
  or a simple prompt, Narrare writes prose that matches your style and story
  world.

  **Input options:**

  **From Outline** 📋
  - Scene-by-scene beats
  - Chapter goals and conflicts
  - POV character and location
  - Target word count

  **From Prompt** 💭
  - Simple description: "Elena confronts the Council about the magic ban"
  - Detailed instructions with specific requirements
  - Mix of outline and freeform guidance

  **From Previous Chapters** 📖
  - Analyze your existing chapters
  - Match your writing style automatically
  - Continue the story naturally

  **Generation modes:**

  **Full Draft**
  - Complete chapter from start to finish
  - 1500-5000 words depending on your target
  - Streams in real-time as AI writes

  **Scene by Scene**
  - Generate one scene at a time
  - Review and adjust between scenes
  - More control, slower process

  **What the AI uses:**
  - Your Knowledge Base (characters, locations, world facts)
  - Previous chapters (for context and style matching)
  - Chapter frontmatter (POV, location, timeline)
  - Your instructions and outline

  **After generation:**
  - Review and edit the draft
  - Run analysis tools (consistency, voice, POV)
  - Use Co-Author mode to refine specific sections

  **Best practices:**
  - Provide clear outline for better results
  - Set word count targets appropriately
  - Run consistency check before accepting
  - Edit the draft — AI output is a starting point

  Available in Editor → "Generate Chapter" or via CLI:
  `narrare writing generate --chapter <id> --outline <file>`
ui_available_in: [editor, cli]

service: writing/service.py
contract: writing/contracts.py#WritingServiceProtocol, core/writing/contracts.py#WritingPipelineProtocol
router: writing/router.py, writing/router_stats.py
prompt: core/prompts/_bundled/writing/{en,de,fr}/{new_chapter,scene_by_scene,interview}/system.md
requires: [INFRA-001, INFRA-002, INFRA-003, KB-001]
---

# WRITE-002 — AI: New Chapter Generation

## What it does

Generates complete chapter drafts from outlines, prompts, or previous chapter
context. Uses Knowledge Base for consistency and style matching. Streams output
in real-time with user controls for length, tone, and content focus.

## Why it exists

Blank pages are daunting. Even with outlines, transforming beats into prose
is work. AI generation provides a first draft — imperfect but complete — that
writers can revise, extend, or delete. It breaks writer's block and accelerates
drafting.

## How it works (User perspective)

1. Open chapter (new or existing) in Editor
2. Click "Generate" or "Generate from Outline"
3. Choose input:
   - **From outline**: Paste scene beats or upload outline file
   - **From prompt**: Describe what should happen
   - **Auto**: Let AI continue from previous chapter
4. Set options:
   - Word count target
   - Tone (dramatic, quiet, suspenseful, etc.)
   - Content focus (character, plot, atmosphere)
5. Click "Generate"
6. Text streams in real-time
7. Click "Stop" anytime to halt generation
8. Review, edit, and save

Generated text is fully editable — treat it as your rough draft.

## How it works (Technical)

**Core module:** `packages/core/narrare_core/writing/`
**API module:** `apps/api/narrare/writing/`

**Entry point:** `writing/router.py` → `POST /api/v1/writing/chapters/{id}/generate`
**Streaming:** `GET /api/v1/writing/generation/{id}/stream` (SSE)
**Stats:** `writing/router_stats.py` → generation analytics endpoints
**Service:** `WritingService` in `writing/service.py` (orchestrates pipeline + repo + feedback)
**Contract:** `WritingServiceProtocol` in `writing/contracts.py`, `WritingPipelineProtocol` in `core/writing/contracts.py`
**LLM Intent:** `LLMIntent.GENERATE`
**Streaming:** Yes — Server-Sent Events (SSE)

**4 Generation modes (dispatch via WritingPipeline):**
1. **full_draft** — Complete chapter from start to finish via `pipeline.py`
2. **scene_by_scene** — Generate one scene at a time with review between scenes via `pipeline_scene.py` (see `scene_service.py` on API side)
3. **interview_assisted** — Guided Q&A to build context, then generate via `pipeline_interview.py`
4. **interactive_session** — Real-time collaborative writing via WebSocket (see WRITE-005)

**Generation pipeline:**
1. **Context assembly** (INFRA-003): `WritingContextAssembler` with 5-tier ranking + token budgets
   - Immediate context (30%), Recent chapters (20%), KB referenced (25%), KB suggested (15%), Pinned (10%)
   - Token budget enforcement via `budget.py` (`TokenBudgetManager`)
   - KB entity relevance: 50% similarity, 30% frequency, 20% recency
2. **Prompt building** (INFRA-002): Assemble system + user prompts from `_bundled/writing/{lang}/{mode}/`
   - 12 system prompts (4 modes × 3 languages: en, de, fr)
   - 4 tone variants: balanced, dramatic, suspenseful, quiet
3. **LLM call**: Stream generation via LLM Gateway
4. **Post-processing**: `DraftProcessor` — artifact removal + markdown normalization
5. **Persistence**: `GenerationRepository` — status transitions, concurrent generation prevention

**API models:**
- SQLAlchemy model: `generation_requests` table (migration 0008) with FK to `chapter_versions`
- 11 Pydantic schemas in `writing/schemas.py`
- Status lifecycle: pending → generating → completed/failed

**User controls during generation:**
- Stop/Resume generation
- Mode selection via `GenerationConfig.tsx`
- Draft review via `GenerationDraft.tsx`
- Real-time streaming display via `GenerationPanel.tsx`

**Frontend components:**
- `lib/api/generation.ts` — API client with SSE streaming + WebSocket client
- `components/studio/editor/GenerationPanel.tsx` — Generation trigger + streaming display
- `components/studio/editor/GenerationConfig.tsx` — Mode selection + options
- `components/studio/editor/GenerationDraft.tsx` — Draft zone + controls
- Generation commands registered in CommandPalette

## Constraints & Edge Cases

- Minimum 500 words for meaningful generation
- Maximum 10,000 words per generation (token limits)
- Quality degrades with very sparse KB (no characters/locations defined)
- First chapter has no previous context — user must provide more detail
- Style matching requires 3+ existing chapters
- Streaming requires stable connection — interruption loses generated text
- LLM availability required — no offline mode

## Related Features

- [WRITE-003](WRITE-003-extend.md) — Continue existing chapters
- [WRITE-004](WRITE-004-rewrite.md) — Rewrite generated text
- [WRITE-006](WRITE-006-co-author.md) — Refine generated chapters
- [WRITE-009](WRITE-009-unblock.md) — Alternative when stuck
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Provides context
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Voice consistency

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-17` — Implementation started (in-progress). Core writing pipeline with 4 generation modes, API endpoints with SSE streaming, frontend GenerationPanel/Config/Draft components. Prompts: 12 system prompts (4 modes × 3 languages) + 4 tone variants. Migration 0008 for generation_requests table.
- `2026-05-18` — Fully implemented (stable). All 4 generation modes operational, SSE streaming + WebSocket sessions, frontend generation UI complete, 98 tasks done.
