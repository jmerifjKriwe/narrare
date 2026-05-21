## ADDED Requirements

### Requirement: WritingGraph has a generate_summary step

The system SHALL add a `generate_summary` step to the WritingGraph, positioned as the final step after `finalize`.

- The step SHALL be registered in `build_writing_graph()` after the `finalize` node
- The step SHALL take `ctx.state.final` if non-empty, otherwise `ctx.state.draft`, as input
- The step SHALL instantiate `ChapterSummaryAgent` using the model from `ctx.deps`
- The step SHALL store the summary in `ctx.state.summary`
- The step SHALL set `ctx.state.status = WritingStatus.SUMMARIZED` (new enum value: `SUMMARIZED = "summarized"`)
- The step SHALL call `_save_state(ctx)` to persist the summary to DB

#### Scenario: Summary generated after finalize
- **WHEN** the WritingGraph completes the `finalize` step
- **THEN** the `generate_summary` step SHALL execute automatically
- **AND** `ctx.state.summary` SHALL be non-empty after the step

#### Scenario: Summary uses final version
- **WHEN** `ctx.state.final` is non-empty
- **THEN** the summary SHALL be generated from `ctx.state.final`
- **AND** NOT from `ctx.state.draft`

#### Scenario: Summary step saves state
- **WHEN** `generate_summary` completes successfully
- **THEN** `_save_state(ctx)` SHALL be called
- **AND** `ctx.state.status` SHALL be `WritingStatus.SUMMARIZED`

### Requirement: WritingState has summary field

The system SHALL add a `summary: str` field to `WritingState` (default `""`).

#### Scenario: New WritingState defaults
- **WHEN** `WritingState(chapter_id="ch-1", novel_id="n-1")` is created
- **THEN** `summary` SHALL be `""`

#### Scenario: Summary field serialized
- **WHEN** `_serialize_state(writing_state)` is called with a WritingState that has a non-empty summary
- **THEN** the serialized dict SHALL contain the `summary` key with the correct value

### Requirement: WritingStatus has SUMMARIZED value

The system SHALL add `SUMMARIZED = "summarized"` to the `WritingStatus` enum, positioned between `FINALIZED` and `COMPLETED`.

#### Scenario: Status value is respected
- **WHEN** a WritingGraph run has completed the `generate_summary` step
- **THEN** `ctx.state.status` SHALL equal `WritingStatus.SUMMARIZED`
