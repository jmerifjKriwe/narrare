## ADDED Requirements

### Requirement: Record feedback endpoint
The system SHALL provide a `POST /api/v1/memory/feedback` endpoint that records user feedback (accept/reject/modify) on an AI suggestion, persisting it to the `feedback_events` table and forwarding to mem0.

#### Scenario: Record accept feedback
- **WHEN** `POST /api/v1/memory/feedback` is called with `action="accept"`, `suggestion_id`, `intent`, and `suggestion_text`
- **THEN** a `FeedbackEvent` is persisted to `feedback_events` and mem0 receives a translated memory input describing the accepted suggestion

#### Scenario: Record reject feedback
- **WHEN** `POST /api/v1/memory/feedback` is called with `action="reject"` and optional `reason`
- **THEN** a `FeedbackEvent` with `action=reject` is persisted and mem0 receives the rejection context

#### Scenario: Record modify feedback
- **WHEN** `POST /api/v1/memory/feedback` is called with `action="modify"` and `modification` text
- **THEN** a `FeedbackEvent` with `action=modify` is persisted and mem0 receives both the original suggestion and the user's modification

### Requirement: Get preferences endpoint
The system SHALL provide a `GET /api/v1/memory/preferences` endpoint that returns the user's preference profile for the current project, formatted for display in settings UI.

#### Scenario: Retrieve preferences
- **WHEN** `GET /api/v1/memory/preferences` is called
- **THEN** a `PreferenceProfile` is returned containing style, content, and constraints sections with confidence score and event count

#### Scenario: No preferences yet
- **WHEN** `GET /api/v1/memory/preferences` is called for a user with no feedback history
- **THEN** an empty profile with `event_count: 0` and `confidence: 0.0` is returned

### Requirement: Reset preferences endpoint
The system SHALL provide a `DELETE /api/v1/memory/preferences` endpoint that clears all feedback events and mem0 memories for the user in the current project.

#### Scenario: Reset preferences
- **WHEN** `DELETE /api/v1/memory/preferences` is called
- **THEN** all `feedback_events` for the user+project are deleted, mem0 `delete_all()` is called for the scope, and subsequent preference requests return an empty profile

### Requirement: Feedback events database table
The system SHALL create a `feedback_events` table via Alembic migration with columns: `id` (UUID PK), `user_id` (UUID FK), `project_id` (UUID FK), `suggestion_id` (UUID), `action` (enum), `intent` (string), `suggestion_text` (text), `modification` (text nullable), `context` (JSONB), `created_at` (timestamp with timezone).

#### Scenario: Migration applies successfully
- **WHEN** `alembic upgrade head` is run
- **THEN** the `feedback_events` table exists with all specified columns and appropriate indexes on `user_id` and `project_id`

### Requirement: Memory service contract
The system SHALL define protocols in `memory/contracts.py` for `FeedbackServiceProtocol` and `PreferenceServiceProtocol` before implementation.

#### Scenario: Protocol-first development
- **WHEN** the memory API module is implemented
- **THEN** `contracts.py` with both protocols exists before any service implementation files
