---
id: WRITE-002
title: "AI: New Chapter Generation"
status: planned
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

service: writing/draft_service.py
contract: writing/contracts.py#DraftServiceProtocol
router: writing/router.py
prompt: core/prompts/_bundled/writing/en/new_chapter
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

**Entry point:** `writing/router.py` → `POST /api/v1/writing/chapters/{id}/generate`
**Service:** `DraftService.generate_chapter()` in `writing/draft_service.py`
**Contract:** `DraftServiceProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.WRITE`
**Streaming:** Yes — Server-Sent Events (SSE)

**Generation pipeline:**
1. **Context assembly** (INFRA-003): Gather KB entries, recent chapters
2. **Prompt building** (INFRA-002): Assemble system + user prompts
3. **Style analysis**: Extract style patterns from previous chapters (optional)
4. **LLM call**: Stream generation via LLM Gateway
5. **Token management**: Track usage, stop at target word count
6. **Post-processing**: Format Markdown, clean artifacts

**Prompt variables:**
- `{{project_title}}`, `{{genre}}`, `{{tone}}`
- `{{chapter_outline}}` or `{{chapter_prompt}}`
- `{{kb_characters}}` — relevant character profiles
- `{{kb_locations}}` — relevant location descriptions
- `{{recent_chapters}}` — last 2-3 chapters summaries
- `{{style_examples}}` — excerpts from user's writing (if voice cloning enabled)

**User controls during generation:**
- Stop/Resume generation
- Adjust word count target mid-stream
- Regenerate from last scene break

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
