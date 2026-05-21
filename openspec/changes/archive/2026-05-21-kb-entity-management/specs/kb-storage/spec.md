## ADDED Requirements

### Requirement: KB entries are persisted in a single polymorphic table
The system SHALL store all KB entries (characters, locations, factions, objects, systems, timelines) in a single `kb_entries` table with an `entity_type` discriminator column and a CHECK constraint limiting values to the 6 defined types.

#### Scenario: Insert a character entry
- **WHEN** a new KB entry is created with entity_type "character"
- **THEN** the entry is stored in `kb_entries` with entity_type="character", metadata as JSONB, body as TEXT, and auto-generated id/slug/timestamps

#### Scenario: Reject invalid entity type
- **WHEN** a KB entry is created with entity_type "planet"
- **THEN** the database rejects the insert with a constraint violation

### Requirement: KB entries have structured metadata and narrative body
Each KB entry SHALL have a `metadata` JSONB column for structured, queryable fields and a `body` TEXT column for narrative Markdown content. The metadata holds entity-type-specific attributes (age, role, location_type, etc.). The body holds free-form prose.

#### Scenario: Character entry has both metadata and body
- **WHEN** a character entry is created with metadata `{"age": 19, "role": "protagonist"}` and body `"## Background\n\nElara was orphaned..."`
- **THEN** the metadata column contains the JSON object, the body column contains the Markdown string, and both are independently queryable

#### Scenario: Entry with empty metadata and body
- **WHEN** a KB entry is created with empty metadata `{}` and empty body `""`
- **THEN** the entry is stored successfully — neither field is mandatory

### Requirement: KB entries belong to a novel
Each KB entry SHALL have a `novel_id` foreign key referencing the `novels` table with CASCADE delete. All KB queries are scoped to a novel.

#### Scenario: Delete novel removes all KB entries
- **WHEN** a novel is deleted that has 15 KB entries
- **THEN** all 15 KB entries are automatically deleted by the database CASCADE

#### Scenario: List entries scoped to novel
- **WHEN** the user requests KB entries for novel X
- **THEN** only entries with `novel_id = X` are returned

### Requirement: KB entries have slugs unique per novel
Each KB entry SHALL have a `slug` field that is unique within a novel. The slug is auto-generated from the name (kebab-case) if not provided.

#### Scenario: Auto-generate slug from name
- **WHEN** a KB entry is created with name "Elara Thornwind" and no slug
- **THEN** the system generates slug "elara-thornwind"

#### Scenario: Reject duplicate slug within novel
- **WHEN** a KB entry is created in novel X with slug "elara-thornwind" and that slug already exists in novel X
- **THEN** the system rejects the creation with a conflict error

### Requirement: KB entries support tagging
Each KB entry SHALL have a `tags` JSONB column storing an array of strings. Tags are searchable and filterable.

#### Scenario: Filter entries by tag
- **WHEN** the user searches for entries with tag "protagonist" in novel X
- **THEN** all entries in novel X where the tags array contains "protagonist" are returned

### Requirement: KB entries have a status lifecycle
Each KB entry SHALL have a `status` field with values: "draft", "reviewed", "canon", "deprecated". Default is "draft".

#### Scenario: Create entry with default status
- **WHEN** a KB entry is created without specifying status
- **THEN** the entry has status "draft"

### Requirement: Full-text search on KB entry body and name
The system SHALL support full-text search across the `name` and `body` columns of KB entries, scoped to a novel.

#### Scenario: Search finds entries by body content
- **WHEN** the user searches for "void magic" in novel X
- **THEN** entries whose body or name contains "void magic" (or related terms via text search) are returned, ranked by relevance

#### Scenario: Empty search returns all entries
- **WHEN** the user submits an empty search query
- **THEN** all entries for the novel are returned, ordered by name

### Requirement: Demo loader populates KB entries
The demo loader SHALL parse Markdown KB files from demo data directories, separate frontmatter into metadata and content into body, and insert them as `kb_entries`.

#### Scenario: Load demo KB entries
- **WHEN** the setup wizard loads the "Echoes of the Thornwall" demo
- **THEN** 15 KB entries are created in the database with correct entity types, names, metadata (from frontmatter), and bodies (from markdown content)

#### Scenario: Demo entry with type-specific metadata
- **WHEN** `char-elara.md` is loaded (frontmatter has age: 19, role: protagonist, pov_character: true)
- **THEN** the metadata JSONB contains `{"age": 19, "role": "protagonist", "pov_character": true, ...}` and the body contains the Markdown content after the frontmatter delimiter
