## Context

Narrare's `chapters` table has had a `summary` column since the initial migration, and `LLMIntent.SUMMARIZE` is registered in the intent system. The context assembler already falls back to `ch.summary` when full chapter content exceeds token budgets. **However, no code ever populates this column.** The spec (WRITE-012) references nonexistent paths from before the `narrare_core/` restructure.

The storyboard (committed as `6831e10`) has a sync status system that uses pure heuristics (word_count > 0 → "completed"), and a structure remap that divides chapters by position ratio. Both are documented as "future AI-powered" features dependent on WRITE-012.

Additionally, the WritingGraph (our agents-first pipeline) has 5 nodes (plan_outline → write_draft → review_draft → revise_draft → finalize), but no summary generation step. The frontend has no visibility into WritingGraph state.

### Current Architecture

```
Writer → Chapter → [chapters.summary = ""] ← nobody fills this
                 → Storyboard: sync heuristic (word_count > 0)
                 → Remap: position-ratio only

WritingGraph: plan → write → review → revise → final ✓
              (no summary step)
```

### Target Architecture

```
Writer → Chapter → ChapterSummaryAgent → ch.summary = "2-4 sentence summary"
                 → Storyboard: sync uses summary presence
                 → Remap: AI analyzes summaries for stage hints
                 → WritingGraph: new final step generates summary

Frontend → WritingGraphStatus Panel (shows current state machine step)
         → Storyboard: more accurate status badges, AI remap confidence
```

## Goals / Non-Goals

**Goals:**
- Implement ChapterSummaryAgent as a proper NarrareAgent (subclass of `NarrareAgent`)
- Create SummaryService + REST endpoint (`POST /api/v1/chapters/{id}/summarize`)
- Add `generate_summary` step to WritingGraph (after `finalize`)
- Update `StructuralSyncChecker` to use summary field for COMPLETED status
- Implement AI-powered structure remap using chapter summaries
- Build frontend WritingGraphStatus component showing pipeline state
- Update storyboard UI for enhanced sync + remap confidence

**Non-Goals:**
- Not implementing auto-summarize on every chapter save (future enhancement — event consumer pattern)
- Not full narrative analysis or beat detection (outside scope)
- Not changing the 5 existing storyboard structure adapters
- Not rebuilding the existing WritingGraph UI (adding, not replacing)

## Decisions

### D1: ChapterSummaryAgent as Output Function Agent
**Decision:** Implement `ChapterSummaryAgent` using the same pattern as `DraftAgent`, `OutlineAgent`, and `ReviewAgent` — NarrareAgent subclass with an output function class method that structures the LLM response.
**Rationale:** Consistency — all 3 existing agents follow this pattern. The output function can validate and structure the summary (`text: str`, `key_points: list[str]`, `word_count: int`).
**Alternatives considered:** Simple gateway call → rejected (would break RULE-01b pattern).

### D2: Summary prompt as bundled file
**Decision:** Create `packages/core/narrare_core/prompts/_bundled/writing/en/summary/system.md` following the existing prompt file conventions.
**Rationale:** RULE-02 requires prompts in `core/prompts/`. The existing Composer already has `SUMMARIZE → "analysis"` category and `summarize` mode mapped — the prompt auto-discovery will work if we place it at the correct path.
**Path discovery:** Category `"analysis"` (from composer.py line 44), mode `"summarize"` (from composer.py line 69), language `"en"` → `analysis/en/summarize/system.md`.

### D3: WritingGraph summary step runs after finalize
**Decision:** Add `generate_summary` as the final step in WritingGraph. It runs after `finalize`, takes `ctx.state.draft` (or `final` if non-empty), calls `ChapterSummaryAgent`, and stores the result in `ctx.state.summary`.
**Rationale:** The summary should reflect the final version. Running it earlier would waste tokens when the draft changes.
**Note:** The WritingGraph step writes the summary back to DB via the existing `GraphStateStore` — no new persistence needed.

### D4: AI Remap as optional enhancement, not replacement
**Decision:** `preview_remap` first checks if summaries exist for enough chapters (configurable threshold, default: 50%). If yes, it calls a lightweight summarization analysis using `ChapterSummaryAgent` to classify each chapter's narrative role. If not enough summaries exist, it falls back to position-ratio heuristics.
**Rationale:** Full AI remap requires summaries, which may not exist for all chapters. The hybrid approach gives best-effort AI without breaking existing functionality.
**Implementation:** Core `planning/remap.py` — new `AIRemapService` class with `analyze_chapter_role(summary) → str` method, returning stage suggestions.

### D5: Enhanced Sync via summary presence + content analysis
**Decision:** Update `StructuralSyncChecker.calculate_sync_status()` rule 4 (currently: word_count > 0 → COMPLETED). New rule: if `summary` is non-empty AND chapter has content → COMPLETED (more accurate — someone has actually processed this chapter).
**Rationale:** The summary field being non-empty is a stronger signal than just word_count > 0. It means a human (or AI) has processed and condensed the chapter.
**Edge case:** If summary exists but content is empty → still ON_TRACK (summary was maybe generated prematurely). New rule added between existing 3 and 4.

### D6: WritingGraphStatus as collapsible sidebar panel
**Decision:** A compact, collapsible status panel in the editor sidebar showing: current WritingGraph step (highlighted), completed steps (checkmark), and available actions ("Generate Outline", "Review Draft", etc.). Polls via API or WebSocket for state changes.
**Rationale:** First iteration — keep it simple and informative. Future versions could add inline triggers.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| AI remap with partial summaries could produce worse results than position-ratio | Fallback to position-ratio when <50% chapters have summaries. Show "AI" badge only when summaries are used |
| Summary generation adds LLM cost per chapter | Keep summaries short (2-4 sentences). Use cheaper model for summarization (configurable via `ModelRegistry`) |
| WritingGraph summary step could increase graph completion time | Summary step runs after finalize — doesn't block drafting loop. User can close the graph before summary completes |
| Frontend WritingGraphStatus needs polling or WS | Start with polling (simpler, matches existing patterns). Add WebSocket in future iteration |
