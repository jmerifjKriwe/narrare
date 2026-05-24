## Why

Writers get stuck mid-scene. They know what needs to happen but can't find the
words. WRITE-003 provides an "Extend Chapter" action that reads the text around
the cursor and streams a seamless continuation directly into the editor — with
full feedback tracking (accept/reject/modify) for the mem0 learning loop.

Unlike WRITE-002 (full chapter generation via side panel), Extend inserts text
_inline at the cursor position_. This requires new editor infrastructure to
track AI-generated text, detect user modifications, and capture structured
feedback — infrastructure that WRITE-004 (Rewrite) and WRITE-009 (Unblock) will
also need.

## What Changes

- **New TipTap Extension `AIAnnotation`**: A ProseMirror `Mark` (`ai-generated`)
  that annotates AI-inserted text with metadata (`request_id`, `source`,
  `original_text`, `status`). Includes a `Plugin` that tracks modifications
  within marked ranges for precise modify-detection.

- **New TipTap Extension `AIAnnotationUI`**: Floating action component that
  renders accept/reject/rate controls alongside pending AI-generated text.
  Reusable by all AI text features (Extend, Rewrite, Unblock).

- **New `GenerationMode.EXTEND`**: Separate generation mode in core and API,
  distinct from `FULL_DRAFT` because the input contract is fundamentally
  different (cursor context vs. outline).

- **New API endpoint `POST /writing/chapters/{id}/extend`**: Accepts
  `text_before`, `text_after`, `length` preference, and tone. Creates a
  `generation_request`, streams via existing SSE infrastructure, and integrates
  with the existing accept/reject/feedback lifecycle.

- **New `WritingPipeline._extend()` method**: Direct LLM call (no WritingGraph)
  using the `extend_chapter` prompt. Style-matches the pre-text for seamless
  continuation.

- **New prompt files** `extend_chapter/system.md` (en, de, fr): Prompts
  specialized for seamless continuation from cursor position, matching the
  user's established style and scene state.

- **Clean Save behavior**: `Autosave` extension removes pending `ai-generated`
  marks before persisting (implicit accept). Saved chapter content is always
  clean — AI annotation is an editor state, not a document state.

## Capabilities

### New Capabilities
- `ai-annotation`: Editor infrastructure for tracking AI-generated text — ProseMirror mark with lifecycle management, modification detection, and feedback capture. Reusable across Extend, Rewrite, Unblock.
- `extend-chapter`: Core + API pipeline for cursor-position-based chapter continuation. New GenerationMode, endpoint, pipeline method, and prompt files.

### Modified Capabilities
- `draft-generation-api`: Extend adds `GenerationMode.EXTEND` to the existing generation mode enum and reuses the `generation_requests` table lifecycle.
- `generation-editor-ui`: Extend adds inline insertion flow to the editor, complementing the existing side-panel generation UI. The `AIAnnotation` infrastructure enhances all AI text interactions in the editor.
- `writing-context-assembly`: Extend uses the existing 5-tier context assembler but shifts budget emphasis toward immediate context (pre/post text around cursor).

## Impact

- **Core** (`packages/core/narrare_core/writing/`): New `_extend()` on WritingPipeline, `GenerationMode.EXTEND` in `_enums.py`, `ExtendRequest` concept in models.
- **API** (`apps/api/narrare/writing/`): New `POST /extend` endpoint, `ExtendRequest` schema, extend-specific service method. Reuses `generation_requests` table.
- **Frontend** (`packages/web/`): Two new TipTap extensions (`AIAnnotation` mark + tracker, `AIAnnotationUI` floating actions), `ContinueButton` component, extend API client methods, editor command registration.
- **Prompts** (`packages/core/narrare_core/prompts/_bundled/writing/`): New `extend_chapter/system.md` in 3 languages (en, de, fr).
- **DB**: No schema changes — reuses `generation_requests` table.
- **Tests**: Unit tests for pipeline extend path, integration tests for `/extend` endpoint, frontend tests for AIAnnotation lifecycle and modify detection.
- **Depends on**: Existing infrastructure (INFRA-001 LLM Gateway, INFRA-002 Prompt System, INFRA-003 Context Assembly, LEARN-001 Feedback Loop).
