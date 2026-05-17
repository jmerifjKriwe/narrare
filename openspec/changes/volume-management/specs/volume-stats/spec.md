## ADDED Requirements

### Requirement: Volume model enrichment
The `volumes` table SHALL have columns: `subtitle` (optional text, max 500 chars), `description` (optional text, unlimited), `word_count_target` (optional integer, minimum 0), `is_default` (boolean, default false). A novel SHALL have exactly one volume with `is_default=True`. The Alembic migration SHALL add these columns with nullable defaults to preserve existing data.

#### Scenario: Default volume has is_default flag
- **WHEN** a novel is created
- **THEN** the auto-created default volume has `is_default=True` and all other volumes have `is_default=False`

#### Scenario: Existing volumes get default column values
- **WHEN** the Alembic migration runs on an existing database
- **THEN** all existing volumes get `is_default=False`, `subtitle=NULL`, `description=NULL`, `word_count_target=NULL`

### Requirement: Default volume auto-creation
When a novel is created, the system SHALL automatically create a default volume titled "Volume 1" with `is_default=True` and `position=0`. This creation SHALL happen within the same database transaction as the novel creation.

#### Scenario: Novel creation creates default volume
- **WHEN** a user creates a new novel via `POST /api/v1/novels`
- **THEN** the response includes the novel AND a default volume exists for that novel with `is_default=True`

#### Scenario: Novel with existing volumes still has exactly one default
- **WHEN** a user creates additional volumes for a novel
- **THEN** the original default volume remains `is_default=True` and no other volume becomes default

### Requirement: Default volume deletion protection
The system SHALL prevent deletion of the default volume. If a delete request targets a volume with `is_default=True`, the service SHALL raise a validation error. The default volume CAN be renamed or updated, but not deleted.

#### Scenario: Attempt to delete default volume
- **WHEN** a user sends `DELETE /api/v1/novels/{novel_id}/volumes/{volume_id}` for the default volume
- **THEN** the API returns 422 with an error message indicating the default volume cannot be deleted

### Requirement: Volume statistics endpoint
The system SHALL provide a `GET /api/v1/novels/{novel_id}/volumes/{volume_id}/stats` endpoint that returns: `word_count` (sum of all chapter word counts in the volume), `chapter_count` (number of chapters in the volume), `word_count_target` (from the volume's `word_count_target` field), `completion_percentage` (word_count / word_count_target * 100, or null if no target set).

#### Scenario: Statistics for volume with chapters
- **WHEN** a volume has 3 chapters with word counts 1000, 2000, 3000 and `word_count_target=10000`
- **THEN** the stats endpoint returns `word_count=6000`, `chapter_count=3`, `word_count_target=10000`, `completion_percentage=60`

#### Scenario: Statistics for volume with no target
- **WHEN** a volume has chapters but `word_count_target` is NULL
- **THEN** the stats endpoint returns `word_count` and `chapter_count` normally, with `completion_percentage=null`

#### Scenario: Statistics for empty volume
- **WHEN** a volume has no chapters
- **THEN** the stats endpoint returns `word_count=0`, `chapter_count=0`

### Requirement: Volume reordering endpoint
The system SHALL provide a `PATCH /api/v1/novels/{novel_id}/volumes/reorder` endpoint that accepts an ordered list of volume IDs and updates the `position` field for all volumes in the novel in a single transaction.

#### Scenario: Reorder volumes
- **WHEN** a user sends a reorder request with volume IDs in order [C, A, B]
- **THEN** volume C gets `position=0`, A gets `position=1`, B gets `position=2`

#### Scenario: Reorder with missing volume ID
- **WHEN** a user sends a reorder request that does not include all volume IDs for the novel
- **THEN** the API returns 422 with an error indicating all volume IDs must be provided

### Requirement: Chapter–volume assignment
The chapter create and update schemas SHALL accept an optional `volume_id` field. When creating a chapter without specifying `volume_id`, the system SHALL assign the novel's default volume. The chapters list endpoint SHALL accept an optional `volume_id` query parameter to filter results by volume.

#### Scenario: Create chapter with explicit volume
- **WHEN** a user creates a chapter with `volume_id` set to a specific volume
- **THEN** the chapter is created with that `volume_id`

#### Scenario: Create chapter without volume
- **WHEN** a user creates a chapter without specifying `volume_id`
- **THEN** the chapter is assigned to the novel's default volume

#### Scenario: List chapters filtered by volume
- **WHEN** a user requests `GET /api/v1/novels/{novel_id}/chapters?volume_id=X`
- **THEN** only chapters belonging to volume X are returned

#### Scenario: Chapter reassignment on volume deletion
- **WHEN** a non-default volume is deleted
- **THEN** all chapters previously in that volume have `volume_id` set to NULL (via existing `ondelete="SET NULL"`)
