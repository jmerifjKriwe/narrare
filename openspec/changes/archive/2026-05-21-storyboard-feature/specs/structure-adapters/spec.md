## ADDED Requirements

### Requirement: Structure adapter registry provides adapters for all story structures
The system SHALL provide a registry (`StructureAdapterRegistry`) that returns a `StructureAdapter` for each `StoryStructure` enum value. The registry SHALL support all 5 structures: `three_act`, `five_act`, `heros_journey`, `save_the_cat`, `seven_point`.

#### Scenario: Get adapter for three_act structure
- **WHEN** `StructureAdapterRegistry.get("three_act")` is called
- **THEN** the system SHALL return an adapter with 3 stages and beat expectations for each stage

#### Scenario: Get adapter for heros_journey structure
- **WHEN** `StructureAdapterRegistry.get("heros_journey")` is called
- **THEN** the system SHALL return an adapter with stages representing the hero's journey narrative arc

#### Scenario: Get adapter for unknown structure
- **WHEN** `StructureAdapterRegistry.get("unknown_structure")` is called
- **THEN** the system SHALL raise a `ValueError`

### Requirement: Each adapter defines stages with metadata
Each `StructureAdapter` SHALL define a list of `StageDef` objects, each containing: `id` (kebab-case string), `name` (display name), `description`, `position` (integer for ordering), and `expected_beat_count` (integer).

#### Scenario: Three-act stages are defined
- **WHEN** the three_act adapter's stages are accessed
- **THEN** it SHALL contain exactly 3 stages with ids `act-1`, `act-2`, `act-3`, with `act-1` having `expected_beat_count` appropriate for setup, `act-2` for confrontation, and `act-3` for resolution

#### Scenario: Save-the-cat beats are defined within acts
- **WHEN** the save_the_cat adapter's stages are accessed
- **THEN** it SHALL organize 15 beats into 3 act groups, where each stage includes its expected beats as `BeatDef` objects

### Requirement: Adapter suggests stage assignment based on chapter position
Each adapter SHALL implement `suggest_stage(chapter_number, total_chapters)` that returns a stage ID based on the chapter's relative position in the story.

#### Scenario: Chapter 1 of 9 in three_act maps to act-1
- **WHEN** `suggest_stage(1, 9)` is called on the three_act adapter
- **THEN** it SHALL return `"act-1"`

#### Scenario: Chapter 6 of 9 in three_act maps to act-2
- **WHEN** `suggest_stage(6, 9)` is called on the three_act adapter
- **THEN** it SHALL return `"act-2"`

#### Scenario: Chapter 9 of 9 in three_act maps to act-3
- **WHEN** `suggest_stage(9, 9)` is called on the three_act adapter
- **THEN** it SHALL return `"act-3"`

#### Scenario: Fewer chapters than stages collapses stages
- **WHEN** `suggest_stage(1, 3)` is called on the heros_journey adapter (which has many stages)
- **THEN** it SHALL map chapter 1 to an appropriate beginning-stage group

### Requirement: Adapter provides beat expectations per stage
Each adapter SHALL implement `get_beat_expectations(stage_id)` returning a list of `BeatDef` objects, each with `title`, `description`, and `required` (boolean).

#### Scenario: Three-act act-1 has setup beats
- **WHEN** `get_beat_expectations("act-1")` is called on the three_act adapter
- **THEN** it SHALL return beats including at minimum an "inciting incident" beat

#### Scenario: Unknown stage returns empty list
- **WHEN** `get_beat_expectations("unknown-stage")` is called
- **THEN** it SHALL return an empty list

### Requirement: Adapters are pure data modules
Structure adapters SHALL NOT import or use any database, HTTP, or LLM dependencies. They SHALL be importable from `packages/core/` without any side effects.

#### Scenario: Adapter imports succeed without database
- **WHEN** an adapter module is imported
- **THEN** no database connection, HTTP client, or LLM gateway SHALL be initialized
