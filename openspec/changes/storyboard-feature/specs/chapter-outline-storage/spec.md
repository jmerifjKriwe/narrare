## ADDED Requirements

### Requirement: Chapter outline persistence
The system SHALL store a single outline per chapter in a `chapter_outlines` table with fields: `id` (UUID), `chapter_id` (UUID FK to chapters), `version_id` (UUID FK to chapter_versions, nullable), `stage_assignment` (VARCHAR(50)), `planned_beats` (JSONB array), `outline_notes` (TEXT), `created_at`, `updated_at`.

#### Scenario: Create outline for a chapter
- **WHEN** a chapter outline is created with stage_assignment "act-1" and 3 planned beats
- **THEN** the system SHALL persist it and return the outline with all fields populated
- **THEN** querying by chapter_id SHALL return exactly one outline

#### Scenario: One outline per chapter constraint
- **WHEN** a second outline is created for a chapter that already has one
- **THEN** the system SHALL reject the creation with a uniqueness constraint error

### Requirement: Outline CRUD operations
The system SHALL provide Create, Read, Update operations for chapter outlines via a repository following the existing repository pattern.

#### Scenario: Get outline by chapter ID
- **WHEN** `get_by_chapter_id(chapter_id)` is called for a chapter with an existing outline
- **THEN** the system SHALL return the outline with all fields including parsed planned_beats

#### Scenario: Get outline for non-existent chapter
- **WHEN** `get_by_chapter_id(uuid)` is called for a chapter that does not exist
- **THEN** the system SHALL return `None`

#### Scenario: Update outline stage assignment
- **WHEN** `update(chapter_id, stage_assignment="act-2")` is called
- **THEN** the system SHALL update only the stage_assignment field and touch `updated_at`
- **THEN** other fields (planned_beats, outline_notes) SHALL remain unchanged

#### Scenario: Update planned beats
- **WHEN** `update(chapter_id, planned_beats=[{title: "Inciting incident", description: "...", completed: false}])` is called
- **THEN** the system SHALL replace the entire planned_beats JSONB array

### Requirement: Planned beats JSONB schema
Each beat in the `planned_beats` JSONB array SHALL conform to the schema: `{ "title": string, "description": string, "completed": boolean }`.

#### Scenario: Valid beat is stored and retrieved
- **WHEN** a beat `{ title: "Climax", description: "Final confrontation", completed: false }` is stored
- **THEN** retrieving the outline SHALL return the beat with all fields preserved

#### Scenario: Empty beats array is valid
- **WHEN** `planned_beats` is set to `[]`
- **THEN** the system SHALL accept and persist it

### Requirement: Outline cascade on chapter deletion
When a chapter is deleted, its associated outline SHALL be automatically deleted via CASCADE.

#### Scenario: Delete chapter removes outline
- **WHEN** a chapter with an existing outline is deleted
- **THEN** the outline SHALL no longer exist in the database

### Requirement: Alembic migration creates chapter_outlines table
A new Alembic migration SHALL create the `chapter_outlines` table with the specified schema and constraints.

#### Scenario: Migration is idempotent
- **WHEN** the migration runs against a database that already has the `chapter_outlines` table
- **THEN** the migration SHALL NOT fail (use IF NOT EXISTS or check before create)

#### Scenario: Migration is reversible
- **WHEN** `alembic downgrade` is run
- **THEN** the `chapter_outlines` table SHALL be dropped cleanly
