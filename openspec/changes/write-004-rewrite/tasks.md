## 1. Core: GenerationMode + Rewrite Pipeline

- [x] 1.1 Add `REWRITE = "rewrite"` to `GenerationMode` in `packages/core/narrare_core/writing/_enums.py`
- [x] 1.2 Add `GenerationModeEnum.REWRITE` to `apps/api/narrare/writing/schemas.py`
- [x] 1.3 Implement `WritingPipeline._rewrite()` — extract into `pipeline_rewrite.py` (RULE-04 compliance), single LLM call via composer + gateway, streams `StreamChunk`, uses `mode="rewrite_selection"` in prompt context, includes selection text + context window + mode-specific instructions
- [x] 1.4 Add `elif request.mode == GenerationMode.REWRITE:` dispatch in `WritingPipeline.generate()`
- [x] 1.5 Add `_REWRITE_PERCENTAGES` to `budget.py` — immediate: 40%, recent: 15%, kb_referenced: 25%, kb_suggested: 10%, pinned: 10%. Wire via `TokenBudgetManager.allocate(mode="rewrite")`. Context_before/context_after are characters (max 500), not tokens.
- [x] 1.6 Write unit tests for pipeline dispatch, budget allocation (rewrite percentages), context assembly for rewrite

## 2. Core: Rewrite Prompt Updates

- [x] 2.1 Update `prompts/_bundled/writing/en/rewrite_selection/system.md` — add `<alternative>` structured output format, mode-specific instruction blocks (tone/style/voice/fix/custom), `{{rewrite_mode_instructions}}` variable, `{{selection_text}}`, `{{context_before}}`, `{{context_after}}`, `{{count}}`. Voice mode includes `{{character_voice_profiles}}` from KB.
- [x] 2.2 Update `prompts/_bundled/writing/de/rewrite_selection/system.md` — German translation of updated prompt
- [x] 2.3 Update `prompts/_bundled/writing/fr/rewrite_selection/system.md` — French translation of updated prompt
- [x] 2.4 Write promptfoo eval baseline for rewrite (3 test cases: tone shift, show-don't-tell fix, voice matching)

## 3. Core: Alternative Parser

- [x] 3.1 Implement `AlternativeParser` in `packages/core/narrare_core/writing/alternative_parser.py` — pure-function state machine: OPENING_TAG → CONTENT → CLOSING_TAG → NEXT_OR_DONE. Parses `<alternative label="...">` tags from LLM output, extracts label and text for each alternative, handles malformed/missing tags with graceful fallback (entire response = single alternative). No XML library dependency. **Purpose:** Server-side validation and testing of structured output — the frontend has its own SSE-aware parser. This core parser operates on complete text, not streamed chunks.
- [x] 3.2 Write unit tests for alternative parser: well-formed multi-alternative, single alternative, no tags (fallback), partial tags across boundaries, nested angle brackets in content, labels with special characters, tag-like content within alternatives (not at line boundary), fewer alternatives than expected, more alternatives than expected

## 4. Backend: Rewrite API

- [x] 4.1 Create `RewriteMode` enum and `RewriteRequest` schema in `apps/api/narrare/writing/schemas.py` — fields: `selection_text` (str, min 50, max 2000 characters), `context_before` (str, optional, max 500 characters), `context_after` (str, optional, max 500 characters), `mode` (RewriteMode: tone|style|voice|fix|custom), `options` (optional dict), `character_id` (optional UUID, required when mode is "voice"), `custom_instructions` (optional str, max 500 chars, required when mode is "custom"), `count` (int, 1-3, default 1), `tone` (str, default "balanced"), `language` (str, default "en")
- [x] 4.2 Create `RewriteServiceProtocol` in `writing/contracts_rewrite.py` (RULE-03)
- [x] 4.3 Implement `RewriteService` in `writing/rewrite_service.py` (separate class per RULE-04, WritingService at 295 lines) — `stream_rewrite()` validates input, checks concurrent generation, creates `generation_request` with mode "rewrite", loads KB entity for voice mode (character_id), assembles context with selection text + context window + character voice profile (for voice mode), delegates to `WritingPipeline._rewrite()`, streams alternatives via SSE with `<alternative>` tags preserved
- [x] 4.4 Create `POST /api/v1/writing/chapters/{chapter_id}/rewrite` route in `writing/router_rewrite.py` — accepts `RewriteRequest`, validates selection length (50-2000 chars), validates voice mode has character_id, validates custom mode has custom_instructions, returns SSE stream directly
- [x] 4.5 Wire rewrite service in `writing/deps.py` — `get_rewrite_service()` factory with `LLMIntent.REWRITE` model routing
- [x] 4.6 Mount rewrite router in `_app/main.py`
- [x] 4.7 Write integration tests for `/rewrite` endpoint — happy path (tone mode count=1, style mode count=2, voice mode with character_id), validation errors (selection <50 chars, selection >2000 chars, voice mode without character_id, custom mode without custom_instructions), concurrent rewrite (409), unauthorized chapter (404)

## 5. Backend: Alternative Streaming

- [x] 5.1 Implement SSE event format for alternatives — first event: `{type: "request_info", request_id, mode: "rewrite"}`, then raw text chunks (containing `<alternative>` tags), final event: `{is_final: true, usage: {...}, alternatives_count: N}`. The backend streams `<alternative>` tags as-is — client-side parser handles splitting.
- [x] 5.2 Write tests for alternative streaming format — verify `<alternative>` tags are preserved in stream, verify request_info event, verify is_final event with alternatives_count

## 6. Frontend: Alternative Parser & API Client

- [x] 6.1 Implement `parseAlternatives()` in `packages/web/lib/api/generation.ts` — client-side state machine parser for `<alternative label="...">` tags. Buffers partial tags across SSE chunk boundaries, emits complete alternatives. Fallback: entire response = single alternative if no tags found.
- [x] 6.2 Add `streamRewrite()` method in `lib/api/generation.ts` — POST to `/rewrite` endpoint, SSE stream with `onRequestInfo`, `onAlternative(label, text)` callback per parsed alternative, `onAlternativeFinal(count)` when stream completes, `onError` callback
- [x] 6.3 Add `RewriteRequest`, `RewriteMode`, `RewriteAlternative` TypeScript types matching backend schema
- [x] 6.4 Write unit tests for `parseAlternatives()` — well-formed multi-alternative, single alternative, no tags (fallback), partial tags buffered across chunks, labels with special characters

## 7. Frontend: Selection Detection & Rewrite Trigger

- [x] 7.1 Wire the existing BubbleMenu "AI Rewrite" button (`handleAIRewrite` in `TipTapEditor.tsx`) to show `RewriteModeSelector` before sending request — replace mock data with real backend call
- [x] 7.2 Add `CommandState.hasSelection` and `CommandState.selectionLength` to `commands.ts` — derived from editor state, enables/disables "Rewrite Selection" command
- [x] 7.3 Add `CommandContext.startRewrite` command for rewrite flow trigger
- [x] 7.4 Add "Rewrite Selection" to CommandPalette — visible only when `hasSelection` is true and selection length is 50-2000 chars
- [x] 7.5 Add `replaceSelectionWithAIContent(editor, requestId, source, newText, from, to)` to `aiAnnotationApi.ts` — atomic ProseMirror transaction that deletes the selection range (from→to) and inserts newText with `ai-generated` mark. This is distinct from `insertAIContent` which inserts at cursor.

## 8. Frontend: Mode Selector & Comparison UI

- [x] 8.1 Create `RewriteModeSelector.tsx` — 5 modes (Tone, Style, Voice, Fix, Custom) with mode-specific option panels. Voice mode: character dropdown populated from KB entities. Custom mode: free-text input (max 500 chars). Count selector (1-3, default 1). Shown before the AISuggestion modal after clicking "AI Rewrite" in BubbleMenu.
- [x] 8.2 Extend existing `AISuggestion` modal in `TipTapEditor.tsx` — add inline diff highlighting to suggestion cards using `diff-match-patch` library, add labels from `<alternative>` tags, show original text above the cards. This is NOT a new component — it extends the existing modal.
- [x] 8.3 Create `InlineDiff.tsx` utility — uses `diff-match-patch` to compute diffs between original and alternative text, returns React elements with green (additions) and red/strikethrough (removals) highlighting.
- [x] 8.4 Add `diff-match-patch` to `packages/web/package.json` — production-grade diff library, used by TipTap/Laravel/VS Code
- [x] 8.5 Wire alternatives display with `streamRewrite()` — on mode selection + trigger, call streamRewrite, parse alternatives via `parseAlternatives()`, populate `AISuggestion` state with results
- [x] 8.6 Wire "Replace" action in modal — calls `replaceSelectionWithAIContent()` from aiAnnotationApi instead of `editor.commands.insertContent()`, which removes original selection and inserts alternative with `ai-generated` mark (`source: "rewrite"`)
- [x] 8.7 Add "Insert as new" action to modal — inserts alternative text after the original selection with `ai-generated` mark, original text unchanged
- [x] 8.8 Write component tests for RewriteModeSelector, InlineDiff utility, and modal integration (mode selection → streaming → display → replace/insert)

## 9. Frontend: AIAnnotation & Feedback Integration

- [x] 9.1 Add `source: "rewrite"` support to AIAnnotation actions — `AIAnnotationActions.tsx` displays "AI Rewrite" label (i18n-keyed) instead of "AI Continuation" based on mark's source attribute
- [x] 9.2 Ensure Clean Save handles rewrite marks — same as extend: remove mark, record ACCEPT/MODIFY feedback before persisting (Autosave extension)
- [x] 9.3 Add i18n keys for rewrite mode labels (Tone, Style, Voice, Fix, Custom), mode option labels, and action labels in en/de/fr
- [x] 9.4 Write tests for rewrite-specific AIAnnotation lifecycle (replaceSelection, mark creation with source="rewrite", accept, reject, modify)

## 10. Docs + Validation

- [x] 10.1 Update `docs/features/writing/WRITE-004-rewrite.md` — status: "in-progress", add technical section reflecting: SSE-direct endpoint, AlternativeParser, existing BubbleMenu/Modal reuse, replaceSelectionWithAIContent, diff-match-patch, rewrite-specific budget
- [x] 10.2 Update `docs/_shared/CURRENT_STATE.md` — WRITE-004 in progress, AlternativeParser, rewrite mode, BubbleMenu integration
- [x] 10.3 Update `docs/features/writing/WRITE-003-extend.md` — add ai-annotation spec link for `replaceSelectionWithAIContent` requirement
- [x] 10.4 Run architecture validation (`scripts/check_architecture.py`) — verify all new files comply with RULE-04 size limits and RULE-06 single responsibility
- [x] 10.5 Run full test suite — backend + frontend, ensure no regressions
