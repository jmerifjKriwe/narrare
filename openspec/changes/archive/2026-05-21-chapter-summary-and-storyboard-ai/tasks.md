## 1. Core: SummaryOutput Types + Prompt File

- [x] 1.1 Create `packages/core/narrare_core/agents/summary_types.py` — `SummaryOutput` Pydantic model (`summary`, `key_points`, `word_count`, `metadata`)
- [x] 1.2 Create prompt file at `packages/core/narrare_core/prompts/_bundled/writing/en/summary/system.md` — concise summarization prompt following Composer's `analysis/en/summarize/` path convention
- [x] 1.3 Verify prompt auto-discovery: `composer.build(LLMIntent.SUMMARIZE, context)` loads the prompt by checking if the file path matches Composer's category/mode mapping

## 2. Core: ChapterSummaryAgent

- [x] 2.1 Create `packages/core/narrare_core/agents/summary_agent.py` — `SummaryDeps` class with `language`, `genre`, `chapter_title`, `max_sentences` fields
- [x] 2.2 Implement `ChapterSummaryAgent(NarrareAgent[SummaryDeps, SummaryOutput])` with `_process_summary` output function
- [x] 2.3 Write unit tests for `ChapterSummaryAgent` — TestModel instantiation, output structure, deps defaults (10+ tests)
- [x] 2.4 Export `ChapterSummaryAgent`, `SummaryDeps`, `SummaryOutput` from `agents/__init__.py`

## 3. Core: WritingGraph — Summary Node + WritingState Update

- [x] 3.1 Add `summary: str = ""` field to `WritingState` in `writing_graph_types.py`
- [x] 3.2 Add `SUMMARIZED = "summarized"` to `WritingStatus` enum
- [x] 3.3 Add `generate_summary` step to `writing_graph.py` — runs after `finalize`, uses `ChapterSummaryAgent`, stores result in `ctx.state.summary`
- [x] 3.4 Update tests in `test_writing_graph.py` — verify summary step, serialization, status transition (3+ new tests)

## 4. Core: Storyboard Enhanced Sync

- [x] 4.1 Update `StructuralSyncChecker.calculate_sync_status()` in `planning/sync.py` — add rule 3b: if summary exists AND has_content → COMPLETED
- [x] 4.2 Write unit tests for new sync rule — 3 test cases (summary+content, content-only, summary-only)
- [x] 4.3 Ensure backward compatibility — existing tests still pass with unchanged `ChapterOutlineData` signature

## 5. Core: AI-Powered Structure Remap

- [x] 5.1 Create `packages/core/narrare_core/planning/remap.py` — `AIRemapService` with `analyze_chapter_role(summary) -> str` method
- [x] 5.2 Implement summary coverage check (threshold: 50% of chapters must have non-empty summaries)
- [x] 5.3 Write unit tests for `AIRemapService` — coverage threshold, role analysis with mock summaries, fallback behavior (5+ tests)

## 6. Backend: SummaryService + Contract + API

- [x] 6.1 Create `apps/api/narrare/writing/summary_contracts.py` — `SummaryServiceProtocol`, `SummaryResult` dataclass
- [x] 6.2 Implement `apps/api/narrare/writing/summary_service.py` — `ChapterSummaryService` with `summarize(chapter_id, config?)` method
- [x] 6.3 Implement `apps/api/narrare/writing/summary_router.py` — `POST /api/v1/chapters/{chapter_id}/summarize` endpoint
- [x] 6.4 Register router in `apps/api/narrare/_app/main.py` with `/api/v1` prefix
- [x] 6.5 Write unit tests for SummaryService — happy path, chapter not found, LLM failure (5+ tests)
- [x] 6.6 Write integration tests for summary API — 200/404/403 responses, full flow

## 7. Backend: Storyboard AI Remap Integration

- [x] 7.1 Update `apps/api/narrare/planning/service.py` — `preview_remap` checks summary coverage, delegates to `AIRemapService`
- [x] 7.2 Update `apps/api/narrare/planning/schemas.py` — add `ai_suggested_stage: str | None` to `RemapPreviewItem`, `ai_confidence: float` to `RemapResponse`
- [x] 7.3 Update `apps/api/narrare/planning/router.py` — pass `use_ai` parameter through
- [x] 7.4 Write unit tests for updated remap — AI path, heuristic fallback, partial coverage (3+ tests)

## 8. Frontend: API Client + Hooks for Summary

- [x] 8.1 Create `packages/web/lib/api/summary.ts` — `summarizeChapter()` function with typed request/response
- [x] 8.2 Create `packages/web/lib/hooks/useSummary.ts` — `useSummarizeChapter()` TanStack Query mutation hook
- [x] 8.3 Write unit tests for API client and hooks (Vitest)

## 9. Frontend: WritingGraph UI Component

- [x] 9.1 Create `packages/web/components/studio/writing/WritingGraphStatus.tsx` — collapsible pipeline state display with step indicators (using frontend-design skill)
- [x] 9.2 Integrate `WritingGraphStatus` into `EditorView.tsx` — positioned above toolbar area
- [x] 9.3 Add i18n keys for WritingGraph step labels to `packages/i18n/messages/en/studio.json`, `de/studio.json`, `fr/studio.json`
- [x] 9.4 Write unit tests for WritingGraphStatus — shows current step, completed steps, collapsed/expanded (Vitest + Testing Library)

## 10. Frontend: Storyboard Updates

- [x] 10.1 Update `StructureChangeDialog.tsx` — show AI confidence badge and per-row AI-suggested stage indicators (using frontend-design skill)
- [x] 10.2 Verify `SyncStatusBadge.tsx` works correctly with enhanced sync data (no visual changes needed)
- [x] 10.3 Add i18n keys for AI remap labels to `packages/i18n/messages/`
- [x] 10.4 Write unit tests for StructureChangeDialog AI features (Vitest + Testing Library)

## 11. Verification

- [x] 11.1 Run `scripts/check_architecture.py` — verify no RULE violations
- [x] 11.2 Run full backend test suite — no regressions
- [x] 11.3 Run full frontend test suite (Vitest) — no regressions
- [x] 11.4 Review frontend with web-design-guidelines skill — verify UI meets accessibility and design standards

## 12. Documentation

- [x] 12.1 Update `docs/features/writing/WRITE-012-chapter-summary.md` — fix stale paths, document implementation
- [x] 12.2 Update `docs/features/planning/PLAN-005-storyboard.md` — document AI remap + enhanced sync
- [x] 12.3 Update `docs/_shared/CURRENT_STATE.md` — reflect new capabilities
- [x] 12.4 Update `docs/features/INDEX.md` — mark WRITE-012 as implemented
