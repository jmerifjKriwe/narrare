## ADDED Requirements

### Requirement: WritingGraphStatus component shows pipeline state

The system SHALL provide a `WritingGraphStatus` component displayed in the editor area that visualizes the WritingGraph pipeline state machine.

- The component SHALL show the current graph step highlighted (e.g., `plan_outline`, `write_draft`, `review_draft`, `revise_draft`, `finalize`, `generate_summary`)
- The component SHALL show completed steps with a checkmark indicator
- The component SHALL show remaining/pending steps as greyed out
- The component SHALL be collapsible (expand/collapse toggle)
- The component SHALL be positioned above the toolbar area (sibling of StoryboardPanel)

#### Scenario: Pipeline status shows current step
- **WHEN** the WritingGraph is in state `drafted` (current step is `review_draft`)
- **THEN** the component SHALL highlight `review_draft` as the active step
- **AND** `plan_outline` and `write_draft` SHALL show as completed
- **AND** `revise_draft`, `finalize`, and `generate_summary` SHALL show as pending

#### Scenario: All steps completed
- **WHEN** the WritingGraph has reached `SUMMARIZED` status (all steps complete)
- **THEN** ALL steps SHALL show as completed with checkmarks

### Requirement: API client for summary endpoint

The system SHALL provide a typed API client function for the chapter summary endpoint.

- A function `summarizeChapter(chapterId: string, options?: {maxSentences?: number, language?: string}) -> Promise<{summary: string, wordCount: number}>` SHALL be added to a summary API client module
- The client SHALL handle errors (404, 500) and return typed responses

#### Scenario: Successful summarization API call
- **WHEN** `summarizeChapter("ch-123", {maxSentences: 4})` is called
- **THEN** the client SHALL make a POST request to `/api/v1/chapters/ch-123/summarize`
- **AND** return the parsed `{summary: string, wordCount: number}` response

#### Scenario: Error handling
- **WHEN** the API returns 404
- **THEN** the client SHALL throw a typed error

### Requirement: TanStack Query hook for summarization

The system SHALL provide a TanStack Query mutation hook for triggering chapter summarization.

- The hook `useSummarizeChapter()` SHALL use `useMutation` from `@tanstack/react-query`
- The hook SHALL accept `chapterId: string` and optional `{maxSentences?: number, language?: string}`
- The hook SHALL return `{summary, wordCount, isLoading, error}`

#### Scenario: Mutation succeeds
- **WHEN** `summarizeMutation.mutateAsync({chapterId: "ch-123"})` is called
- **THEN** the hook SHALL call the API client
- **AND** return the summary data
- **AND** invalidate the chapter query cache

### Requirement: SyncStatusBadge reflects enhanced sync

The `SyncStatusBadge` component SHALL display the enhanced sync status correctly.

- The badge SHALL show the same 5 statuses as before (EMPTY, PLANNED, ON_TRACK, DEVIATED, COMPLETED)
- The COMPLETED status SHALL now be more accurate (triggered by summary presence)
- No visual changes required — the backend data quality improves

#### Scenario: SyncStatusBadge shows COMPLETED
- **WHEN** the backend returns `sync_status: "completed"` for a chapter
- **THEN** the badge SHALL display the COMPLETED style (emerald green per existing implementation)

### Requirement: StructureChangeDialog shows AI confidence

The `StructureChangeDialog` SHALL display an AI confidence indicator when the remap uses chapter summaries.

- When `ai_confidence > 0.0`, the dialog SHALL show a badge or label: "AI-powered remap (X% confidence)"
- When `ai_confidence == 0.0`, no AI badge SHALL be shown
- The remap preview table SHALL show an "AI" indicator on rows where `ai_suggested_stage` differs from heuristic

#### Scenario: AI remap confidence displayed
- **WHEN** the structure change is triggered and `ai_confidence` is 0.8
- **THEN** the dialog SHALL show "AI-powered remap (80% confidence)"
- **AND** the preview table SHALL mark rows with AI-suggested stages

#### Scenario: Heuristic remap shows no AI badge
- **WHEN** the structure change is triggered and `ai_confidence` is 0.0
- **THEN** the dialog SHALL NOT show any AI badge
- **AND** the preview table SHALL use the existing heuristic-only display
