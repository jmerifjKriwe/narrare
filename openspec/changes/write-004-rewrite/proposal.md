## Why

Writers need to revise specific passages — shift tone, strengthen voice, show instead of tell — without losing meaning. Manual rewriting is slow and mentally draining. WRITE-004 provides AI-powered rewriting of selected text with multiple modes (tone, style, voice, fix, custom), generating 1-3 alternatives for the writer to compare and apply. This is the second core AI writing feature in Phase 6, building directly on the AIAnnotation infrastructure (WRITE-003) and the existing WritingPipeline.

## What Changes

- **New endpoint**: `POST /api/v1/writing/chapters/{chapter_id}/rewrite` — accepts a `RewriteRequest` (selection text, mode, options, count) and returns `RewriteResponse` with 1-3 alternatives
- **New `GenerationMode.REWRITE`** enum value in core and backend schemas
- **New `RewriteService`** (separate class per RULE-04, since `WritingService` is at 295 lines) with SSE-direct streaming that wraps each alternative in `<alternative>` tags for client-side parsing
- **Rewrite prompts**: Already exist in `_bundled/writing/{en,de,fr}/rewrite_selection/system.md` — need to be updated to produce structured multi-alternative output with `<alternative>` tags
- **Frontend rewrite UI**: Selection detection in TipTap, mode selector (5 modes + custom instructions), alternatives comparison cards with inline diff highlighting, one-click replace or insert-as-new
- **AIAnnotation reuse**: Rewrite alternatives are inserted using the same `aiAnnotationApi` lifecycle (pending mark, accept/reject), with `source: "rewrite"` to distinguish from extend continuations
- **Feedback integration**: Accept/reject/rate flow reuses the existing `useRecordFeedback` hook with `source: "rewrite"`

## Capabilities

### New Capabilities
- `rewrite-selection`: Backend rewrite endpoint, service, schemas, and prompt updates for multi-alternative structured output
- `rewrite-editor-ui`: Frontend selection detection, mode selector, alternatives comparison UI, and replace/insert actions

### Modified Capabilities
- `draft-generation-api`: Add `GenerationMode.REWRITE` to the enum, pipeline dispatch for rewrite mode
- `generation-editor-ui`: Add "Rewrite" command to `CommandPalette`, toolbar button, and context menu entry; register `startRewrite` command

## Impact

- **Core**: `writing/_enums.py` (REWRITE enum), `writing/pipeline_rewrite.py` (new, `_rewrite()` method), `writing/budget.py` (rewrite budget allocation), `prompts/_bundled/writing/*/rewrite_selection/system.md` (update for structured output)
- **Backend**: `writing/schemas.py` (RewriteRequest, RewriteMode, RewriteAlternative), `writing/contracts_rewrite.py` (new), `writing/rewrite_service.py` (new), `writing/router_rewrite.py` (new), `writing/deps.py` (wire rewrite service), `_app/main.py` (mount router)
- **Frontend**: New `RewriteButton.tsx`, `RewriteModeSelector.tsx`, `AlternativesComparison.tsx`, `InlineDiff.tsx` components; new `streamRewrite()` in `lib/api/generation.ts`; new i18n keys for rewrite actions
- **Dependencies**: Writing pipeline (core), AIAnnotation infrastructure (from WRITE-003), feedback API (from LEARN-001)
