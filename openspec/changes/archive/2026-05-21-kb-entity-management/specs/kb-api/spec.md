## ADDED Requirements

### Requirement: CRUD endpoints for KB entries
The API SHALL expose REST endpoints for creating, reading, updating, and deleting KB entries within a novel. All endpoints require authentication and scope operations to the authenticated user's novels.

#### Scenario: Create a KB entry
- **WHEN** an authenticated user sends POST /api/v1/novels/{novel_id}/kb/entries with body `{entity_type: "character", name: "Elara"}`
- **THEN** a new KB entry is created with auto-generated id, slug "elara", default status "draft", and 201 status code

#### Scenario: List KB entries for a novel
- **WHEN** an authenticated user sends GET /api/v1/novels/{novel_id}/kb/entries
- **THEN** all KB entries for that novel are returned as a paginated list with id, entity_type, name, slug, tags, status, created_at, updated_at

#### Scenario: Get a single KB entry
- **WHEN** an authenticated user sends GET /api/v1/novels/{novel_id}/kb/entries/{entry_id}
- **THEN** the full entry is returned including metadata, body, and relationship summary

#### Scenario: Update a KB entry
- **WHEN** an authenticated user sends PATCH /api/v1/novels/{novel_id}/kb/entries/{entry_id} with `{name: "Elara Thornwind", metadata: {age: 20}}`
- **THEN** the entry is updated, updated_at is refreshed, and the updated entry is returned

#### Scenario: Delete a KB entry
- **WHEN** an authenticated user sends DELETE /api/v1/novels/{novel_id}/kb/entries/{entry_id}
- **THEN** the entry and all its relationships are deleted (cascade), and 204 is returned

### Requirement: Search endpoint for KB entries
The API SHALL expose a search endpoint that accepts a query string, entity_type filter, and tag filter.

#### Scenario: Search by text query
- **WHEN** GET /api/v1/novels/{novel_id}/kb/entries/search?q=void+magic is sent
- **THEN** entries matching "void magic" in name or body are returned, ranked by relevance

#### Scenario: Filter by entity type
- **WHEN** GET /api/v1/novels/{novel_id}/kb/entries?entity_type=character is sent
- **THEN** only character entries are returned

#### Scenario: Filter by tag
- **WHEN** GET /api/v1/novels/{novel_id}/kb/entries?tags=protagonist,mage is sent
- **THEN** only entries tagged with both "protagonist" AND "mage" are returned

### Requirement: CRUD endpoints for KB relationships
The API SHALL expose endpoints for creating, listing, and deleting relationships between KB entries within a novel.

#### Scenario: Create a relationship
- **WHEN** POST /api/v1/novels/{novel_id}/kb/relationships is sent with `{source_id: A, target_id: B, rel_type: "mentor", direction: "directed"}`
- **THEN** the relationship is created and returned

#### Scenario: List relationships for an entry
- **WHEN** GET /api/v1/novels/{novel_id}/kb/entries/{entry_id}/relationships is sent
- **THEN** all relationships (incoming and outgoing) for that entry are returned with related entry names

#### Scenario: Delete a relationship
- **WHEN** DELETE /api/v1/novels/{novel_id}/kb/relationships/{relationship_id} is sent
- **THEN** the relationship is deleted and 204 is returned

### Requirement: Entry ownership validation
All KB endpoints SHALL validate that the novel belongs to the authenticated user before performing any operation.

#### Scenario: Access another user's novel KB
- **WHEN** an authenticated user tries to access KB entries for a novel owned by a different user
- **THEN** the API returns 403 Forbidden

### Requirement: Metadata validation on create and update
The API SHALL validate the `metadata` field against the entity-type-specific Pydantic schema before persisting. Invalid metadata returns a 422 with field-level error details.

#### Scenario: Invalid metadata type
- **WHEN** a character entry is created with metadata `{age: "not a number"}`
- **THEN** the API returns 422 with error detail "age: Input should be a valid integer"

### Requirement: Pagination on list endpoints
List endpoints SHALL support `page` and `page_size` query parameters with sensible defaults (page=1, page_size=50). Response includes total count.

#### Scenario: Paginated entry list
- **WHEN** GET /api/v1/novels/{novel_id}/kb/entries?page=2&page_size=10 is sent for a novel with 25 entries
- **THEN** entries 11-20 are returned with metadata `{page: 2, page_size: 10, total: 25}`
