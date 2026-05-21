## Why

Chapter summaries unlock smarter AI features across Narrare. The database already has a `chapters.summary` column, an `LLMIntent.SUMMARIZE`, and context assembly code that consumes summaries — but **no one produces them**. Without summaries, the storyboard's sync status can only guess whether a chapter is "completed" (it checks word_count > 0), and the structure remap resorts to position-ratio heuristics. Implementing WRITE-012 fills this gap and immediately improves the storyboard's intelligence.

## What Changes

- **ChapterSummaryAgent** — A proper NarrareAgent (subclass of `NarrareAgent`) that takes chapter content and metadata and produces a concise 2-4 sentence summary
- **SummaryService + API** — Backend service and `POST /api/v1/chapters/{id}/summarize` endpoint; optionally auto-triggers on chapter save
- **WritingGraph Summary Node** — A new `generate_summary` step in the WritingGraph that runs after `finalize`
- **Storyboard Enhanced Sync** — `StructuralSyncChecker` updated: if `summary` is non-empty AND content exists, mark as `COMPLETED` (instead of the current word-count heuristic)
- **Storyboard AI Remap** — `preview_remap` optionally uses chapter summaries to analyze narrative content for stage suggestions (fallback to position-ratio when no summary exists)
- **WritingGraph UI** — Frontend panel showing the current graph state (outlined → drafted → reviewed → revised → finalized) with per-step status indicators
- **Storyboard UI Updates** — Status badges reflect new sync accuracy; remap dialog shows AI confidence indicator when summaries are used

## Capabilities

### New Capabilities
- `chapter-summary-agent`: NarrareAgent that generates chapter summaries via LLM. Includes output types, prompt file, and agent class.
- `chapter-summary-api`: Backend service + REST endpoint for triggering chapter summarization. Optional auto-summarize on chapter content change.
- `writing-graph-summary-node`: New WritingGraph step `generate_summary` that creates a chapter summary after finalizing the draft, and writes it back to the DB.
- `storyboard-ai-sync`: Enhanced sync status using chapter summaries (5 rules re-evaluated with summary-aware logic) and AI-powered structure remap via summary analysis.
- `writing-graph-ui`: Frontend component showing WritingGraph state machine — current step, completed steps, status indicators, and trigger actions.

### Modified Capabilities
<!-- No existing spec-level requirements change — all additions are new capabilities. -->

## Impact

**Core (`packages/core/narrare_core/`):**
- New: `agents/summary_agent.py` — ChapterSummaryAgent (+ `SummaryOutput` types)
- New: `agents/writing_graph_types.py` — optional `summary` field on WritingState
- Modified: `agents/writing_graph.py` — new `generate_summary` step after `finalize`
- New: `planning/sync.py` — summary-aware `StructuralSyncChecker.calculate_sync_status()` update
- New: `planning/remap.py` — AI-powered remap analysis (uses summaries when available)
- New: `prompts/_bundled/writing/en/summary/system.md` — summarization prompt template

**Backend (`apps/api/narrare/`):**
- New: `writing/summary_service.py` — ChapterSummaryService (contract + implementation)
- New: `writing/summary_router.py` — `POST /api/v1/chapters/{id}/summarize` endpoint
- Modified: `writing/service.py` — optional auto-summarize on chapter content save
- Modified: `planning/service.py` — AI-powered remap in `preview_remap` when summaries exist

**Frontend (`packages/web/`):**
- New: `components/studio/writing/WritingGraphStatus.tsx` — state machine display component
- New: `lib/api/summary.ts` — API client for summary endpoints
- Modified: `components/studio/EditorView.tsx` — integrate WritingGraph status panel
- Modified: `components/studio/planning/StructureChangeDialog.tsx` — show AI confidence when remap uses summaries
- Modified: `components/studio/planning/SyncStatusBadge.tsx` — reflect more accurate sync

**i18n (`packages/i18n/`):**
- New keys: WritingGraph step labels, summary trigger text, AI remap confidence labels
