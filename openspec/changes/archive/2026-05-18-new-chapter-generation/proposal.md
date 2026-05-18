## Why

Narrare's editor exists, chapters can be created and managed, and the LLM gateway + prompt system are production-ready — but there is no way to actually generate chapter content with AI. WRITE-002 (New Chapter Generation) is the first AI-powered writing feature, and it must establish the architectural pattern that WRITE-003 through WRITE-010 and all future writing features will follow. This change builds on top of `generation-prompt-memory-foundation` (which provides memory layer, feedback API, prompt management, and generation intents) to deliver a complete writing generation experience. The solution supports four modes — full AI generation, scene-by-scene with review, AI-assisted interview/outline flow, and interactive session (WRITE-005) — to serve different creative workflows.

## Prerequisites

This change **requires** `generation-prompt-memory-foundation` to be implemented first. It consumes:
- Memory layer (mem0) for preference injection into prompts
- Feedback API for accept/reject/modify on generated drafts
- Prompt management service for override cascade
- Extended `PromptContext` with `user_preferences` and `avoidance_patterns` fields
- Generation intents and culture/genre injection in the prompt system

## What Changes

- **Writing context assembly**: Concrete implementation of the context assembly stub (`core/context/`) specialized for writing operations — 5-tier relevance ranking of KB entities, recent chapter summarization, frontmatter extraction, and token budget management. Consumes the extended `PromptContext` from the foundation.
- **Chapter generation pipeline**: New `writing/` module in `packages/core/` with a streaming draft generation pipeline that orchestrates context assembly → prompt building → LLM streaming → post-processing. Supports four modes: full draft, scene-by-scene, interview-assisted, and interactive session (WRITE-005).
- **Bundled writing prompts**: Prompt templates under `prompts/_bundled/writing/` for new chapter generation (system prompts with persona, instruction templates with variable slots) in English, German, and French. Consumes the prompt override cascade from the foundation.
- **Draft tracking**: `generation_requests` table for operational metadata (status, model, tokens, timing) linked to existing `chapter_versions` (ADR-011) via `version_type: "ai_draft"` for actual content storage.
- **Draft generation API**: New `writing/` API module with SSE streaming for one-shot generation, WebSocket for interactive sessions, REST endpoints for start/stop/accept/reject.
- **Generation editor UI**: Frontend component for triggering generation (from outline, from prompt, auto-continue, or interactive interview), real-time streaming display, stop/resume controls, scene-by-scene review, and draft acceptance flow integrated into the TipTap editor.

## Capabilities

### New Capabilities

- `writing-context-assembly`: Context assembly pipeline specialized for writing — gathers and ranks KB entities (characters, locations, factions) via 5-tier relevance scoring, summarizes recent chapters, extracts frontmatter metadata, and produces a structured `WritingContext` with token budgeting. Consumes extended `PromptContext` from foundation.
- `chapter-generation-pipeline`: Core streaming draft generation — orchestrates context assembly → prompt building (via existing `PromptComposer`) → LLM streaming (via existing gateway) → post-processing into a reusable pipeline. Supports four generation modes: `full_draft`, `scene_by_scene`, `interview_assisted`, and `interactive_session`.
- `generation-prompts`: Bundled prompt templates for new chapter generation in EN/DE/FR — system prompts with Narrare's writing persona, instruction templates with variable slots (`{{chapter_outline}}`, `{{kb_characters}}`, `{{kb_locations}}`, `{{recent_chapters}}`, `{{style_examples}}`, `{{user_preferences}}`), and per-tone variants.
- `draft-tracking`: Operational tracking for generation requests — `generation_requests` table with status lifecycle (pending → streaming → completed/stopped/failed), model/token/timing metadata. Content stored via existing `chapter_versions` as `version_type: "ai_draft"`. Linked via `generation_request_id` foreign key.
- `draft-generation-api`: Backend API module with `POST /writing/chapters/{id}/generate` (start), `DELETE /writing/generation/{id}` (stop), SSE endpoint for streaming text, WebSocket endpoint for interactive sessions, `POST /writing/generation/{id}/accept` and `/reject`. Delegates feedback to foundation's Feedback API.
- `interactive-writing-session`: Interview and chat-based generation mode (WRITE-005) — conversational loop where AI asks about scene goals, characters, tone, then generates prose iteratively. Uses same pipeline with session state management (conversation history, prose buffer, save-to-chapter). Supports both structured interview and freeform chat.
- `generation-editor-ui`: Frontend generation UI — generation trigger panel with 4 input modes (outline, prompt, auto-continue, interactive), real-time streaming text display in editor, stop/resume/regenerate controls, scene-by-scene review with accept/edit per scene, word count tracking against target, and draft acceptance flow that inserts generated text into the TipTap editor. CommandPalette integration for keyboard-driven generation.

### Modified Capabilities

*(none — this change consumes existing capabilities from `generation-prompt-memory-foundation` without modifying their requirements)*

## Impact

**Core (`packages/core/narrare_core/`):**
- `writing/` — new module: `pipeline.py`, `context_assembler.py`, `draft_processor.py`, `session_manager.py`, `contracts.py`
- `context/` — upgrade from stub to concrete writing context assembly
- `prompts/_bundled/writing/` — new bundled prompt templates (EN/DE/FR) for all generation modes

**API (`apps/api/narrare/`):**
- `writing/` — new module: `router.py`, `service.py`, `contracts.py`, `schemas.py`, SSE handler, WebSocket handler
- Alembic migration — `generation_requests` table
- `chapter_versions` model — add `generation_request_id` nullable FK column

**Frontend (`packages/web/`):**
- New `components/editor/GenerationPanel.tsx` — generation trigger, mode selection, streaming display, scene review
- New `components/editor/SessionPanel.tsx` — interactive session chat UI
- Extension of `EditorLayout.tsx` — panel integration
- New `lib/api/generation.ts` — API client for generation endpoints + SSE streaming
- Extension of `commands.ts` — generation commands in CommandPalette

**Dependencies:**
- No new external dependencies — uses existing LLM gateway, prompt system, streaming client, and foundation's memory/feedback services

**Cross-feature interactions:**
- `generation-prompt-memory-foundation` — **hard prerequisite**, this change consumes its memory, feedback, prompt management, and intent infrastructure
- INFRA-003 (context assembly) — this change implements the writing specialization
- INFRA-005 (memory layer) — consumed via foundation; preferences injected into writing prompts
- SET-002/SET-003 (model routing) — generation uses resolved model config per WRITE intent
- KB-001 (entity management) — context assembly queries KB entities for relevance ranking
- ADR-011 (content versioning) — draft content stored as `ai_draft` version type
- WRITE-003 (extend) / WRITE-004 (rewrite) — same pipeline architecture, future changes with different prompts
