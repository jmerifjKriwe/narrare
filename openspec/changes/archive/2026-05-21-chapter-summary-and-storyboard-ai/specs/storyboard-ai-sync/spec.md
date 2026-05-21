## ADDED Requirements

### Requirement: Enhanced sync status using chapter summaries

The system SHALL update `StructuralSyncChecker.calculate_sync_status()` to use chapter summaries for more accurate status classification.

- A new rule SHALL be added between existing rules 3 (DEVIATED) and 4 (COMPLETED heuristic):
  - **Rule 3b**: If `summary is non-empty` AND `has_content is True` → `COMPLETED`
- The existing rule 4 (word_count > 0 → COMPLETED) SHALL fall through if rule 3b didn't match
- The `ChapterOutlineData` model SHALL remain unchanged (summary is checked through `has_content` and an optional storage field, or the method signature SHALL accept an additional `has_summary: bool = False` parameter)

#### Scenario: Chapter with summary and content is COMPLETED
- **WHEN** `calculate_sync_status()` is called with `stage_assignment="act-2"`, `has_content=True`, `has_summary=True`
- **THEN** the result SHALL be `SyncStatus.COMPLETED`

#### Scenario: Chapter with content but no summary falls through to heuristic
- **WHEN** `calculate_sync_status()` is called with `stage_assignment="act-2"`, `has_content=True`, `has_summary=False`
- **THEN** the result SHALL use the existing heuristic (word_count > 0 → COMPLETED, or ON_TRACK)

#### Scenario: Chapter with summary but no content is ON_TRACK
- **WHEN** `calculate_sync_status()` is called with `stage_assignment="act-2"`, `has_content=False`, `has_summary=True`
- **THEN** the result SHALL be `ON_TRACK` (summary doesn't replace content)

### Requirement: AI-powered structure remap using chapter summaries

The system SHALL implement an optional AI-powered structure remap that uses chapter summaries when available.

- The remap SHALL be implemented in a new `packages/core/narrare_core/planning/remap.py` module
- The remap SHALL implement an `AIRemapService` class with `analyze_chapter_role(summary: str) -> str` method
- The remap SHALL require a configurable threshold of chapters with summaries (default: 50% of chapters)
- Below the threshold, the system SHALL fall back to the existing position-ratio heuristic
- Above the threshold, the system SHALL pass each chapter's summary to `ChapterSummaryAgent` for role analysis
- The `preview_remap` endpoint SHALL return an `ai_confidence: float` field (0.0 = heuristic, 1.0 = full AI, 0.5 = partial AI)

#### Scenario: Sufficient summaries trigger AI remap
- **WHEN** `preview_remap` is called with a novel where 8 of 10 chapters have non-empty summaries
- **THEN** the remap SHALL use AI summary analysis
- **AND** `ai_confidence` SHALL be `1.0`

#### Scenario: Insufficient summaries fall back to heuristic
- **WHEN** `preview_remap` is called with a novel where 2 of 10 chapters have non-empty summaries
- **THEN** the remap SHALL fall back to position-ratio heuristic
- **AND** `ai_confidence` SHALL be `0.0`

#### Scenario: Partial summary coverage
- **WHEN** `preview_remap` is called with a novel where 5 of 10 chapters have non-empty summaries
- **THEN** the remap SHALL use AI for chapters with summaries and heuristic for the rest
- **AND** `ai_confidence` SHALL be `0.5`

### Requirement: AI remap updates service + schemas

The `StoryboardService.preview_remap()` method SHALL be updated to:
- Accept optional `use_ai: bool = True` parameter
- Check summary coverage ratio of novel chapters
- Delegate to `AIRemapService` when coverage meets threshold
- Return `ai_confidence` in the response

The `RemapPreviewItem` schema SHALL gain an optional `ai_suggested_stage: str | None` field.

#### Scenario: Service delegates to AI
- **WHEN** `service.preview_remap(novel_id, new_structure, use_ai=True)` is called with sufficient summaries
- **THEN** the service SHALL call `AIRemapService.analyze_chapter_role()` for each chapter with a summary
- **AND** `RemapPreviewItem.ai_suggested_stage` SHALL be populated for chapters with summaries

#### Scenario: AI remap can be disabled
- **WHEN** `service.preview_remap(novel_id, new_structure, use_ai=False)` is called
- **THEN** the service SHALL use position-ratio heuristic regardless of summary availability
- **AND** `ai_confidence` SHALL be `0.0`
