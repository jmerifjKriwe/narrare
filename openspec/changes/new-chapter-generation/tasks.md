## 1. Core — Contracts & Protocols

- [ ] 1.1 Create `packages/core/narrare_core/writing/__init__.py` with module exports
- [ ] 1.2 Create `packages/core/narrare_core/writing/contracts.py` — define `WritingPipelineProtocol`, `ContextAssemblerProtocol`, `DraftProcessorProtocol`, `SessionManagerProtocol` with full method signatures
- [ ] 1.3 Create `packages/core/narrare_core/writing/models.py` — define `GenerationMode` enum, `WritingContext` dataclass, `GenerationRequest` dataclass, `SessionState` dataclass, `SceneState` dataclass

## 2. Core — Writing Context Assembly

- [ ] 2.1 Create `packages/core/narrare_core/writing/context_assembler.py` — implement `WritingContextAssembler` with 5-tier ranking logic (immediate, recent, referenced KB, suggested KB, pinned)
- [ ] 2.2 Implement token budget enforcement per tier with overflow handling and pinned-item bypass
- [ ] 2.3 Implement KB entity relevance ranking (50% similarity, 30% frequency, 20% recency) with frontmatter reference extraction
- [ ] 2.4 Implement recent chapter summarization — include full text when within budget, summarize when exceeding
- [ ] 2.5 Implement `WritingContext.to_prompt_variables()` mapping to `{{kb_characters}}`, `{{kb_locations}}`, `{{recent_chapters}}`, `{{style_examples}}`, `{{user_preferences}}`
- [ ] 2.6 Handle edge cases: sparse KB (fewer than 3 entities), first chapter (no history), empty frontmatter
- [ ] 2.7 Write unit tests for `WritingContextAssembler` — full context, sparse KB, first chapter, budget overflow, pinned bypass, relevance ranking

## 3. Core — Draft Post-Processor

- [ ] 3.1 Create `packages/core/narrare_core/writing/draft_processor.py` — implement `DraftProcessor` with artifact stripping, Markdown normalization, incomplete sentence removal, word count enforcement
- [ ] 3.2 Write unit tests for `DraftProcessor` — artifact removal, trailing sentence cleanup, word count truncation, empty input

## 4. Core — Generation Pipeline

- [ ] 4.1 Create `packages/core/narrare_core/writing/pipeline.py` — implement `WritingPipeline` with mode dispatch for `full_draft`, `scene_by_scene`, `interview_assisted`, `interactive_session`
- [ ] 4.2 Implement `full_draft` mode — single-pass streaming: context assembly → prompt build → gateway.stream() → post-process → yield chunks
- [ ] 4.3 Implement `scene_by_scene` mode — per-scene generation with yield-after-scene and wait-for-signal logic
- [ ] 4.4 Implement `interview_assisted` mode — structured interview sequence (3-5 questions), then delegate to `full_draft` with interview answers injected
- [ ] 4.5 Implement stop signal handling — cancel in-progress LLM call, preserve partial text, mark as stopped
- [ ] 4.6 Implement error handling — LLM errors, token limits, timeouts with partial result preservation
- [ ] 4.7 Write unit tests for `WritingPipeline` — all 4 modes, stop signal, error handling, partial preservation

## 5. Core — Interactive Session Manager

- [ ] 5.1 Create `packages/core/narrare_core/writing/session_manager.py` — implement `SessionManager` with conversation history, prose buffer, session metadata, scene context
- [ ] 5.2 Implement Redis-based session persistence with TTL refresh on each message and recovery after restart
- [ ] 5.3 Implement 30-minute inactivity timeout with prose buffer auto-save
- [ ] 5.4 Implement conversation history management — cap at 20 messages, context-aware trimming
- [ ] 5.5 Implement prose buffer operations — accumulate accepted text, save-to-chapter, clear
- [ ] 5.6 Write unit tests for `SessionManager` — session lifecycle, history management, timeout, save-to-chapter

## 6. Core — Bundled Writing Prompts

- [ ] 6.1 Create prompt directory structure: `prompts/_bundled/writing/{en,de,fr}/{new_chapter,scene_by_scene,interview,interactive_session}/system.md`
- [ ] 6.2 Write English system prompts for all 4 modes with variable slots and writing persona
- [ ] 6.3 Write German system prompts for all 4 modes
- [ ] 6.4 Write French system prompts for all 4 modes
- [ ] 6.5 Write interview prompt template (`writing/{lang}/interview/system.md`) with structured question generation instructions
- [ ] 6.6 Create tone variant definitions — dramatic, quiet, suspenseful, balanced — as injectable `{{tone_instructions}}` sections
- [ ] 6.7 Write unit tests verifying prompt resolution for all modes, languages, and cascade behavior

## 7. API — Database & Migration

- [ ] 7.1 Create Alembic migration for `generation_requests` table (id, chapter_id, status, mode, model_id, provider_name, tokens_used, word_count, started_at, completed_at, error_message, user_id, novel_id, created_at, updated_at)
- [ ] 7.2 Add `generation_request_id` nullable FK column to `chapter_versions` table via migration
- [ ] 7.3 Create `apps/api/narrare/writing/models.py` — SQLAlchemy model for `GenerationRequest`
- [ ] 7.4 Update Alembic `env.py` to import the new writing model module
- [ ] 7.5 Write integration test verifying migration applies cleanly and model CRUD works

## 8. API — Schemas & Contracts

- [ ] 8.1 Create `apps/api/narrare/writing/schemas.py` — request/response schemas: `GenerateRequest`, `GenerateResponse`, `GenerationStatusResponse`, `SceneAcceptRequest`, `AcceptResponse`, `RejectResponse`
- [ ] 8.2 Create `apps/api/narrare/writing/contracts.py` — `WritingServiceProtocol` and `GenerationRepositoryProtocol` with full method signatures
- [ ] 8.3 Create `apps/api/narrare/writing/__init__.py` with module exports

## 9. API — Repository

- [ ] 9.1 Create `apps/api/narrare/writing/repository.py` — implement `GenerationRepository` with CRUD for `generation_requests`, status transitions, concurrent generation check, stale request cleanup
- [ ] 9.2 Write unit tests for `GenerationRepository` — lifecycle transitions, concurrent prevention, stale cleanup

## 10. API — Service

- [ ] 10.1 Create `apps/api/narrare/writing/service.py` — implement `WritingService` that orchestrates pipeline, repository, and feedback delegation
- [ ] 10.2 Implement `start_generation()` — validate input, check concurrent, create request, invoke pipeline
- [ ] 10.3 Implement SSE stream handler — yield text chunks, update request status, persist to chapter_versions on completion
- [ ] 10.4 Implement `stop_generation()` — cancel pipeline, save partial, update status
- [ ] 10.5 Implement `accept_draft()` — promote ai_draft version to chapter content, delegate feedback to foundation API
- [ ] 10.6 Implement `reject_draft()` — mark version rejected, delegate feedback
- [ ] 10.7 Implement scene-by-scene service methods — `next_scene()`, `accept_scene()`, final chapter assembly
- [ ] 10.8 Implement generation analytics — aggregate stats per novel/user
- [ ] 10.9 Write unit tests for `WritingService` — generation lifecycle, accept/reject, scene-by-scene, error handling

## 11. API — WebSocket Session Handler

- [ ] 11.1 Create `apps/api/narrare/writing/ws_handler.py` — WebSocket endpoint handler for interactive sessions
- [ ] 11.2 Implement message routing — user_direction, user_feedback, save_to_chapter, end_session
- [ ] 11.3 Implement session lifecycle — create on connect, greet, process messages, timeout, cleanup on disconnect
- [ ] 11.4 Integrate with `SessionManager` for state management and Redis persistence
- [ ] 11.5 Write integration tests for WebSocket session — connect, message exchange, timeout, save

## 12. API — Router

- [ ] 12.1 Create `apps/api/narrare/writing/router.py` — REST endpoints: POST generate, DELETE stop, POST accept, POST reject, POST scene/next, POST scene/accept, GET stats
- [ ] 12.2 Add SSE streaming response for generation endpoint
- [ ] 12.3 Add WebSocket route for interactive sessions
- [ ] 12.4 Register router in app with `/api/v1/writing` prefix
- [ ] 12.5 Write integration tests for all REST endpoints — authentication, validation, lifecycle

## 13. Frontend — API Client

- [ ] 13.1 Create `packages/web/lib/api/generation.ts` — typed API client: `startGeneration()`, `stopGeneration()`, `acceptDraft()`, `rejectDraft()`, `nextScene()`, `getGenerationStats()`
- [ ] 13.2 Implement SSE streaming consumer for generation text — connect, parse chunks, handle disconnect/reconnect
- [ ] 13.3 Implement WebSocket client for interactive sessions — connect, send/receive messages, handle reconnect
- [ ] 13.4 Write unit tests for API client — request formatting, SSE parsing, WebSocket message handling

## 14. Frontend — Generation Panel

- [ ] 14.1 Create `packages/web/components/editor/GenerationPanel.tsx` — generation trigger UI with 4 mode tabs (outline, prompt, auto-continue, interactive)
- [ ] 14.2 Implement mode-specific input forms — outline textarea, prompt textarea, auto-continue confirmation, interactive launcher
- [ ] 14.3 Implement generation options — word target input, tone selector (dramatic/quiet/suspenseful/balanced), language auto-detect
- [ ] 14.4 Implement draft zone in editor — visually distinct area for streaming text with "AI Draft" badge
- [ ] 14.5 Implement streaming text display — real-time text rendering in draft zone during generation
- [ ] 14.6 Implement generation controls — stop button, accept/reject buttons, regenerate button
- [ ] 14.7 Implement word count progress indicator — current/target with progress bar
- [ ] 14.8 Implement connection lost handling — banner with retry, preserved partial text

## 15. Frontend — Session Panel

- [ ] 15.1 Create `packages/web/components/editor/SessionPanel.tsx` — chat UI for interactive sessions
- [ ] 15.2 Implement message display — user messages and AI responses in chat layout
- [ ] 15.3 Implement prose preview in AI messages — distinct display with "Add to draft" button
- [ ] 15.4 Implement message input with send button and Enter key
- [ ] 15.5 Implement "Save to Chapter" action — save prose buffer as draft
- [ ] 15.6 Implement "End Session" action — save and close

## 16. Frontend — Editor Integration

- [ ] 16.1 Integrate `GenerationPanel` into `EditorLayout.tsx` — add "Generate" button to toolbar, panel toggle
- [ ] 16.2 Integrate `SessionPanel` into `EditorLayout.tsx` — replace context panel when session active
- [ ] 16.3 Add generation commands to `commands.ts` — "Generate Chapter", "Generate from Outline", "Auto-Continue", "Start Interactive Session", "Stop Generation", "Accept Draft", "Reject Draft"
- [ ] 16.4 Implement command state management — show/hide based on active generation state
- [ ] 16.5 Add editor store state for generation — `isGenerating`, `activeRequestId`, `generationMode`, `draftText`, `sessionActive`
- [ ] 16.6 Implement draft acceptance flow — insert accepted text into TipTap editor at cursor position

## 17. Testing & Quality

- [ ] 17.1 Write integration test suite for full generation lifecycle — start → stream → accept → chapter updated
- [ ] 17.2 Write integration test for scene-by-scene lifecycle — scene 1 → accept → scene 2 → accept → final assembly
- [ ] 17.3 Write integration test for interactive session lifecycle — connect → message → generate → save → disconnect
- [ ] 17.4 Write integration test for error scenarios — LLM failure, connection loss, concurrent generation
- [ ] 17.5 Run architecture validation (`check_architecture.py`) and fix any violations
- [ ] 17.6 Verify RULE-01 compliance — no direct LLM imports outside `core/llm/`
- [ ] 17.7 Verify RULE-02 compliance — no prompt f-strings outside `core/prompts/`
- [ ] 17.8 Verify RULE-04 compliance — all new files within size limits

## 18. Documentation

- [ ] 18.1 Update `docs/features/writing/WRITE-002-new-chapter.md` — status → in-progress, add implementation details
- [ ] 18.2 Update `docs/features/writing/WRITE-005-interactive-session.md` — status → in-progress, add implementation details
- [ ] 18.3 Update `docs/features/infra/INFRA-003-context-assembly.md` — add writing specialization details
- [ ] 18.4 Update `docs/_shared/CURRENT_STATE.md` — add writing module to "What Exists"
- [ ] 18.5 Update `docs/reference/directory-structure.md` — add `writing/` module entries
