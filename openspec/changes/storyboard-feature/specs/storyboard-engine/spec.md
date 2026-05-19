## ADDED Requirements

### Requirement: Storyboard view endpoint
The system SHALL provide `GET /api/v1/planning/storyboard/{novel_id}` that returns the full storyboard view including: novel's story structure, all stages from the structure adapter, chapters grouped by stage assignment, and sync status for each chapter.

#### Scenario: Get storyboard for a novel with chapters
- **WHEN** the storyboard endpoint is called for a novel with 6 chapters in three_act structure
- **THEN** the response SHALL contain 3 stage groups (act-1, act-2, act-3) with chapters assigned to their stages
- **THEN** each chapter SHALL include sync status, word count, and outline summary

#### Scenario: Get storyboard for novel with no chapters
- **WHEN** the storyboard endpoint is called for a novel with 0 chapters
- **THEN** the response SHALL contain stage groups with empty chapter lists
- **THEN** the response status SHALL be 200

#### Scenario: Get storyboard for non-existent novel
- **WHEN** the storyboard endpoint is called with an invalid novel_id
- **THEN** the response status SHALL be 404

### Requirement: Sync status calculation
The system SHALL calculate sync status for each chapter based on its outline and content state, using the `StructuralSyncChecker` with 5 status levels: `empty`, `planned`, `on_track`, `deviated`, `completed`.

#### Scenario: Chapter with no outline and no content
- **WHEN** sync is calculated for a chapter with no outline and 0 words
- **THEN** status SHALL be `"empty"`

#### Scenario: Chapter with outline but no content
- **WHEN** sync is calculated for a chapter with a populated outline and 0 words
- **THEN** status SHALL be `"planned"`

#### Scenario: Chapter with outline and content in correct stage
- **WHEN** sync is calculated for a chapter with an outline, content > 0 words, and all planned beats marked completed
- **THEN** status SHALL be `"completed"`

#### Scenario: Chapter with outline and content, some beats incomplete
- **WHEN** sync is calculated for a chapter with an outline, content > 0 words, and some beats not marked completed
- **THEN** status SHALL be `"on_track"`

#### Scenario: Chapter assigned to wrong stage
- **WHEN** sync is calculated for a chapter where the adapter's `suggest_stage` returns a different stage than the outline's `stage_assignment`
- **THEN** status SHALL be `"deviated"`

### Requirement: Chapter outline CRUD endpoints
The system SHALL provide `GET /api/v1/planning/outlines/{chapter_id}` and `PUT /api/v1/planning/outlines/{chapter_id}` for reading and updating chapter outlines.

#### Scenario: Get existing outline
- **WHEN** `GET /api/v1/planning/outlines/{chapter_id}` is called for a chapter with an outline
- **THEN** the response SHALL include stage_assignment, planned_beats, and outline_notes

#### Scenario: Get outline for chapter without one
- **WHEN** `GET /api/v1/planning/outlines/{chapter_id}` is called for a chapter without an outline
- **THEN** the system SHALL return a default outline with the suggested stage assignment and empty beats

#### Scenario: Update outline creates if not exists
- **WHEN** `PUT /api/v1/planning/outlines/{chapter_id}` is called for a chapter without an existing outline
- **THEN** the system SHALL create the outline and return 201

#### Scenario: Update outline modifies existing
- **WHEN** `PUT /api/v1/planning/outlines/{chapter_id}` is called for a chapter with an existing outline
- **THEN** the system SHALL update the specified fields and return 200

### Requirement: Structure change remap endpoint
The system SHALL provide `POST /api/v1/planning/storyboard/{novel_id}/remap` that accepts a new story structure, calculates a preview of stage reassignments for all existing chapter outlines, and returns the preview without persisting changes.

#### Scenario: Remap from three_act to five_act
- **WHEN** remap is called with `new_structure: "five_act"` for a novel currently in three_act
- **THEN** the response SHALL contain a list of `{chapter_id, chapter_title, old_stage, new_stage}` for all chapters with outlines
- **THEN** no outlines SHALL be modified in the database

#### Scenario: Remap with no existing outlines
- **WHEN** remap is called for a novel with no chapter outlines
- **THEN** the response SHALL contain an empty remap list
- **THEN** the response SHALL still confirm the structure change is valid

#### Scenario: Confirm remap persists changes
- **WHEN** remap is called with `confirm: true`
- **THEN** the system SHALL update all chapter outlines to their new stage assignments
- **THEN** the novel's story_structure SHALL be updated to the new value

### Requirement: Auto-generate outlines on storyboard access
When the storyboard is accessed for a novel whose chapters lack outlines, the system SHALL auto-create outlines with suggested stage assignments.

#### Scenario: First storyboard access auto-creates outlines
- **WHEN** the storyboard is accessed for a novel where none of the 6 chapters have outlines
- **THEN** the system SHALL create 6 outlines with suggested stage assignments based on position
- **THEN** each outline SHALL have empty planned_beats and outline_notes

### Requirement: Planning module follows contract-first pattern
The `planning/` domain module SHALL follow RULE-03 (Protocol-First Development) with `contracts.py` defining protocols before implementation.

#### Scenario: Contracts define service protocols
- **WHEN** the planning module is implemented
- **THEN** `contracts.py` SHALL define `StoryboardServiceProtocol`, `OutlineRepositoryProtocol`, and `SyncCheckerProtocol`
- **THEN** these protocols SHALL be implemented by the service, repository, and sync checker respectively

### Requirement: Structure remap uses position-based heuristics (AI remap is future)
The initial structure remap implementation SHALL use position-ratio heuristics to assign chapters to new stages. AI-powered remap based on chapter summaries (WRITE-012) is a future enhancement.

#### Scenario: Position-based remap for similar structures
- **WHEN** remap is called from three_act to five_act for a novel with 10 chapters
- **THEN** the system SHALL use `suggest_stage(chapter_number, total_chapters)` from the target structure's adapter
- **THEN** chapters in the first third SHALL map to early stages, middle third to middle stages, etc.

#### Scenario: Remap notes AI enhancement opportunity
- **WHEN** the remap logic is implemented
- **THEN** a code TODO SHALL reference WRITE-012 as the future dependency for intelligent summary-based remap
