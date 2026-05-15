## ADDED Requirements

### Requirement: Relationships are directed edges between KB entries
The system SHALL store relationships as directed edges in a `kb_relationships` table with `source_id` and `target_id` foreign keys referencing `kb_entries`, a `rel_type` string, an optional `label` string, and a `direction` field ("directed" or "mutual").

#### Scenario: Create a directed relationship
- **WHEN** a relationship is created from entry A to entry B with rel_type "mentor" and direction "directed"
- **THEN** the relationship is stored with source_id=A, target_id=B, rel_type="mentor", direction="directed"

#### Scenario: Create a mutual relationship
- **WHEN** a relationship is created from entry A to entry B with rel_type "ally" and direction "mutual"
- **THEN** the relationship is stored with source_id=A, target_id=B, rel_type="ally", direction="mutual"

### Requirement: Relationships are typed with free-form strings
The `rel_type` column SHALL be a VARCHAR(50), not a database enum. The core module provides well-known type constants, but users and AI can define custom types.

#### Scenario: Custom relationship type
- **WHEN** a relationship is created with rel_type "blood_sibling" (not in the well-known constants)
- **THEN** the relationship is stored and queryable without error

### Requirement: No self-referencing relationships
The database SHALL enforce a CHECK constraint that `source_id != target_id`.

#### Scenario: Reject self-referencing relationship
- **WHEN** a relationship is created with source_id and target_id pointing to the same entry
- **THEN** the database rejects the insert

### Requirement: Relationship uniqueness constraint
The database SHALL enforce a UNIQUE constraint on `(source_id, target_id, rel_type)` to prevent duplicate relationships.

#### Scenario: Reject duplicate relationship
- **WHEN** a relationship A→B type="ally" already exists and another A→B type="ally" is created
- **THEN** the system rejects the duplicate

#### Scenario: Allow different relationship types between same pair
- **WHEN** a relationship A→B type="mentor" exists and A→B type="colleague" is created
- **THEN** both relationships are stored

### Requirement: Relationships cascade delete with entries
When a KB entry is deleted, all relationships referencing that entry (as source or target) SHALL be automatically deleted.

#### Scenario: Delete entry removes all relationships
- **WHEN** entry A is deleted, and A has 3 outgoing relationships and 2 incoming relationships
- **THEN** all 5 relationships are deleted

### Requirement: Core provides well-known relationship type constants
The system SHALL provide a `RelationshipType` class in core with constants for common relationship types organized by entity-type pair (character→character, character→location, etc.).

#### Scenario: Suggested types for entity-type pair
- **WHEN** the frontend requests suggested relationship types for a character→character connection
- **THEN** the system returns: ally, rival, mentor, mentee, family, romantic, enemy, neutral, colleague

### Requirement: Core provides inverse suggestions
The system SHALL provide an `INVERSE_SUGGESTIONS` mapping that suggests inverse relationship types. This is informational only — the system never auto-creates inverse relationships.

#### Scenario: Suggest inverse for mentor
- **WHEN** a "mentor" relationship is created from A to B
- **THEN** the system can suggest "mentee" as the inverse type for a potential B→A relationship, but does not create it

### Requirement: Frontend prompts for inverse relationship
When a user creates a directed relationship, the frontend SHALL show an optional prompt suggesting the inverse relationship, based on `INVERSE_SUGGESTIONS`. The user can accept, dismiss, or ignore.

#### Scenario: Prompt for inverse after creating mentor relationship
- **WHEN** user creates Elara→Verrick type="mentor"
- **THEN** the UI shows: "Add inverse? Verrick considers Elara a 'mentee'"
- **WHEN** user accepts
- **THEN** Verrick→Elara type="mentee" is created

#### Scenario: Dismiss inverse prompt
- **WHEN** user creates Elara→Verrick type="mentor" and dismisses the inverse prompt
- **THEN** only the Elara→Verrick relationship exists, no inverse is created

### Requirement: Query relationships for an entry
The system SHALL support querying all relationships for a given entry, optionally filtered by direction (outgoing, incoming, or both) and by rel_type.

#### Scenario: Get all relationships for an entry
- **WHEN** the user requests relationships for entry A
- **THEN** all relationships where A is source or target are returned, with the related entry's name and type included

#### Scenario: Filter relationships by direction
- **WHEN** the user requests only outgoing relationships for entry A
- **THEN** only relationships where A is the source_id are returned
