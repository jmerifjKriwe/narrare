## 1. Core: GenerationMode + Extend Pipeline

- [x] 1.1 Add `EXTEND = "extend"` to `GenerationMode` in `packages/core/narrare_core/writing/_enums.py`
- [x] 1.2 Add `GenerationModeEnum.EXTEND` to `apps/api/narrare/writing/schemas.py`
- [x] 1.3 Implement `WritingPipeline._extend()` — direct LLM call via composer + gateway, streams `StreamChunk`, uses `mode="extend_chapter"` in prompt context, respects length→word_target mapping (short~150, medium~400, long~750)
- [x] 1.4 Add `elif request.mode == GenerationMode.EXTEND:` dispatch in `WritingPipeline.generate()`
- [x] 1.5 Write unit tests for `_extend()` dispatch, word-target mapping, and prompt context construction

## 2. Core: Extend Prompts

- [x] 2.1 Create `packages/core/narrare_core/prompts/_bundled/writing/en/extend_chapter/system.md` — prompt specialized for seamless continuation: reads pre-text verbatim, marks `[CONTINUE FROM HERE]`, includes style analysis from pre-text, scene state, KB context, voice profiles, preferences
- [x] 2.2 Create `packages/core/narrare_core/prompts/_bundled/writing/de/extend_chapter/system.md` — German translation
- [x] 2.3 Create `packages/core/narrare_core/prompts/_bundled/writing/fr/extend_chapter/system.md` — French translation
- [ ] 2.4 Write promptfoo eval baseline for extend (3 test cases: short continuation, medium with dialogue, long scene advancement) — DEFERRED: evals/ directory exists but baseline can be added in a follow-up session

## 3. Backend: Extend API

- [x] 3.1 Create `ExtendRequest` schema in `apps/api/narrare/writing/schemas.py` — `text_before` (required, max 10000), `text_after` (optional, max 2000), `length` (ExtendLength enum: short/medium/long), `tone`, `language`
- [x] 3.2 Create `ExtendLength` enum in `schemas.py`
- [x] 3.3 Implement `ExtendService.start_extend()` — validates input, checks concurrent generation, creates `generation_request` with mode "extend", returns `GenerateResponse` (separate `ExtendService` class per RULE-04)
- [x] 3.4 Implement `ExtendService.stream_extend()` — SSE-direct: creates request AND streams in one call, assembles context with `text_before`/`text_after` as chapter content, delegates to `WritingPipeline._extend()`, reuses existing streaming + status update logic
- [x] 3.5 Add `POST /api/v1/writing/chapters/{chapter_id}/extend` route in `writing/router_extend.py` — accepts `ExtendRequest`, returns SSE stream directly (SSE-direct pattern, like `/suggest`)
- [x] 3.6 Wire extend service in `writing/deps.py` — `get_extend_service()` factory with `LLMIntent.EXTEND` model routing
- [x] 3.7 Write integration tests for `/extend` endpoint — happy path (short/medium/long), missing text_before (422), concurrent extend (409), unauthorized chapter (404), SSE streaming lifecycle

## 4. Backend: Context Assembly Budget Adjustment

- [x] 4.1 Add mode-aware budget allocation to `WritingContextAssembler.assemble()` — when mode is EXTEND, shift immediate context tier to ~50%, recent chapters to ~15%, KB tiers retain proportions
- [x] 4.2 Ensure `existing_content` in PromptContext is populated with pre-text + `[CONTINUE FROM HERE]` + post-text for extend mode
- [x] 4.3 Write unit tests for extend-specific budget allocation

## 5. Frontend: AIAnnotation Mark + Tracker Extension

- [x] 5.1 Create `packages/web/components/studio/editor/extensions/AIAnnotation.ts` — ProseMirror `Mark` definition (`ai-generated`) with attributes: `request_id`, `source`, `original_text`, `status`, `created_at`; configure `excludes: "_"`, `inclusive: false`, `parseHTML`/`renderHTML` for safety
- [x] 5.2 Implement `AIAnnotationTracker` Plugin — monitors transactions within pending mark ranges, compares `original_text` vs. current text for modify detection, maintains single-pending-mark constraint (auto-resolves existing pending on new insertion)
- [x] 5.3 Implement Clean Save integration — `Autosave` extension removes pending `ai-generated` marks before calling `saveFn`, records implicit ACCEPT/MODIFY feedback event
- [x] 5.4 Expose mark lifecycle API as standalone functions — `insertAIContent()`, `appendToPendingMark()`, `finalizePendingMark()`, `acceptMark()`, `rejectMark()`, `hasPendingMark()`, `getPendingModification()`, `resolveAllPendingMarks()` — all take `editor` as explicit parameter (bypasses TipTap Proxy issue). Storage methods are thin wrappers for convenience.
- [x] 5.5 Register `AIAnnotation` mark in `TipTapEditor.tsx` extensions array
- [x] 5.6 Write Vitest tests for mark application, modify detection, single-pending constraint, accept/reject, append/finalize — 11 tests all passing

## 6. Frontend: AIAnnotationUI Floating Actions

- [x] 6.1 Create `packages/web/components/studio/editor/AIAnnotationActions.tsx` — floating accept/reject/rate UI positioned near pending mark, shows word count and source label, triggers mark lifecycle actions via standalone functions
- [x] 6.2 Implement position tracking — decoration-based positioning that follows the pending mark range via ProseMirror `Decoration.widget()` in AIAnnotationTracker plugin
- [x] 6.3 Integrate `RatingPrompt` component — shown after accept/reject action, records rating + reason via `useRecordFeedback` hook
- [x] 6.4 Add i18n keys for annotation actions — source labels ("AI Continuation", "AI Rewrite"), accept/reject/rate labels in 3 languages
- [x] 6.5 Write Vitest tests for floating actions render, accept flow, reject flow — 4 tests passing

## 7. Frontend: Extend Command + API Client

- [x] 7.1 Add `ExtendRequest` type and `ExtendLength` type to `lib/api/generation.ts`
- [x] 7.2 Add `writingApi.startExtend()` method to `lib/api/generation.ts` — POST to `/writing/chapters/${chapterId}/extend`
- [x] 7.3 Create `ContinueButton` component — toolbar button with length selector dropdown (short/medium/long), triggers extend flow using standalone `insertAIContent()`/`appendToPendingMark()`/`finalizePendingMark()` functions
- [x] 7.4 Register "Continue writing" command in `commands.ts` — keyboard shortcut (Tab+Enter or configurable), appears in CommandPalette
- [x] 7.5 Wire extend streaming — `streamExtend()` feeds chunks to `insertAIContent()`/`appendToPendingMark()`/`finalizePendingMark()` standalone functions
- [x] 7.6 Wire feedback — accept/reject/rate flow calls `writingApi.acceptDraft()`/`writingApi.rejectDraft()` + `useRecordFeedback()` with modify detection from `getPendingModification()`
- [x] 7.7 Write Vitest tests for ContinueButton render, API client extend method, command registration

## 8. Docs + Validation

- [x] 8.1 Update `docs/features/writing/WRITE-003-extend.md` — status: "in-progress", add technical section reflecting actual implementation
- [x] 8.2 Update `docs/_shared/CURRENT_STATE.md` — WRITE-003 in progress, AIAnnotation infrastructure
- [x] 8.3 Run architecture validation (`scripts/check_architecture.py`) — verify all new files comply with RULE-04 size limits and RULE-06 single responsibility
- [x] 8.4 Run full test suite — backend + frontend, ensure no regressions
