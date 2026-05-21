## MODIFIED Requirements

### Requirement: Record feedback endpoint
The system SHALL provide a `POST /api/v1/memory/feedback` endpoint that records user feedback (accept/reject/modify) on an AI suggestion, persisting it to the `feedback_events` table. The request SHALL accept an optional `rating` field (integer 1-5) and enriched `context` containing `chapter_id`, `genre`, `mode`, and `project_id`. The endpoint SHALL persist to PostgreSQL synchronously and publish a `FeedbackRecorded` event for async mem0 processing.

#### Scenario: Record accept feedback with rating
- **WHEN** `POST /api/v1/memory/feedback` is called with `action="accept"`, `suggestion_id`, `intent`, `suggestion_text`, `rating=4`, and `context={"chapter_id": "...", "genre": "Fantasy", "mode": "full_draft"}`
- **THEN** a `FeedbackEvent` with `rating=4` is persisted to `feedback_events` and a `FeedbackRecorded` event is published

#### Scenario: Record reject feedback
- **WHEN** `POST /api/v1/memory/feedback` is called with `action="reject"`, `suggestion_id`, `intent`, and optional `modification` as rejection reason
- **THEN** a `FeedbackEvent` with `action=reject` is persisted and a `FeedbackRecorded` event is published

#### Scenario: Record modify feedback
- **WHEN** `POST /api/v1/memory/feedback` is called with `action="modify"`, `suggestion_id`, `intent`, `suggestion_text`, and `modification` text
- **THEN** a `FeedbackEvent` with `action=modify` is persisted and a `FeedbackRecorded` event is published

#### Scenario: Feedback event triggers preference analysis at threshold
- **WHEN** a feedback event is recorded and the total event count for the user/project crosses a trigger threshold (20, 50, 100, 200, every 200 after)
- **THEN** a `PreferenceAnalysisTriggered` event is published in addition to `FeedbackRecorded`

### Requirement: Feedback events database table
The system SHALL extend the `feedback_events` table with a `rating` column (INTEGER, nullable, CHECK constraint 1-5) and ensure `context` JSONB column stores enriched feedback context including `chapter_id`, `genre`, and `mode`.

#### Scenario: Migration adds rating column
- **WHEN** `alembic upgrade head` is run
- **THEN** the `feedback_events` table has a `rating` column accepting NULL or integers 1-5
