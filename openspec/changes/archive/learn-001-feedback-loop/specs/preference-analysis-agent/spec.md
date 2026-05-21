## ADDED Requirements

### Requirement: PreferenceAnalysisAgent types
The system SHALL define `PreferenceAnalysisOutput` (Pydantic model) and `PreferenceAnalysisDeps` in `core/agents/preference_analysis_types.py`. `PreferenceAnalysisOutput` SHALL contain fields: `style_patterns` (dict), `content_patterns` (dict), `avoidance_patterns` (list[str]), `confidence` (float 0-1), `summary` (str). `PreferenceAnalysisDeps` SHALL contain fields: `language` (str), `genre` (str), `event_count` (int).

#### Scenario: Output types are valid Pydantic models
- **WHEN** `PreferenceAnalysisOutput` is instantiated with `style_patterns={"sentence_length": "short"}, content_patterns={}, avoidance_patterns=["purple prose"], confidence=0.75, summary="User prefers concise writing"`
- **THEN** the model validates and serializes correctly

### Requirement: PreferenceAnalysisAgent implementation
The system SHALL implement `PreferenceAnalysisAgent` as a `NarrareAgent[PreferenceAnalysisDeps, PreferenceAnalysisOutput]` in `core/agents/preference_analysis_agent.py`. The agent SHALL analyze accumulated feedback events and extract structured writing preferences.

#### Scenario: Agent analyzes feedback batch
- **WHEN** the agent is run with a prompt containing 20+ formatted feedback events and `PreferenceAnalysisDeps(language="en", genre="Fantasy", event_count=25)`
- **THEN** the agent returns a `PreferenceAnalysisOutput` with non-empty `style_patterns`, `content_patterns`, and `avoidance_patterns`

#### Scenario: Agent handles insufficient data
- **WHEN** the agent is run with fewer than 5 feedback events
- **THEN** the agent returns a `PreferenceAnalysisOutput` with empty patterns and `confidence=0.0`

### Requirement: Preference analysis triggering
The system SHALL trigger the PreferenceAnalysisAgent when feedback event count crosses thresholds: 20, 50, 100, 200, and every 200 thereafter. The trigger SHALL run as a TaskIQ background task after the feedback recording event.

#### Scenario: Analysis triggered at threshold
- **WHEN** a feedback event is recorded and the user's total event count for the project becomes exactly 20
- **THEN** a TaskIQ task is enqueued to run the PreferenceAnalysisAgent for that user/project

#### Scenario: Analysis not triggered below threshold
- **WHEN** a feedback event is recorded and the user's total event count is 15
- **THEN** no PreferenceAnalysisAgent task is enqueued

### Requirement: Preference analysis result storage
The system SHALL store the PreferenceAnalysisAgent output in a `preference_profiles` PostgreSQL table with columns: `id` (UUID PK), `user_id` (UUID), `project_id` (UUID), `style_patterns` (JSONB), `content_patterns` (JSONB), `avoidance_patterns` (JSONB), `confidence` (float), `summary` (text), `event_count_at_analysis` (int), `created_at` (timestamp), `updated_at` (timestamp). There SHALL be a unique constraint on (user_id, project_id) — the profile is upserted on each analysis.

#### Scenario: Profile created on first analysis
- **WHEN** the PreferenceAnalysisAgent completes for a user/project with no existing profile
- **THEN** a new row is inserted in `preference_profiles`

#### Scenario: Profile updated on subsequent analysis
- **WHEN** the PreferenceAnalysisAgent completes for a user/project with an existing profile
- **THEN** the existing row is updated with the new analysis results

### Requirement: Preference analysis migration
The system SHALL create an Alembic migration for the `preference_profiles` table.

#### Scenario: Migration applies successfully
- **WHEN** `alembic upgrade head` is run
- **THEN** the `preference_profiles` table exists with all specified columns and the unique constraint on (user_id, project_id)

### Requirement: Preference analysis API endpoint
The system SHALL provide a `POST /api/v1/memory/analyze` endpoint that manually triggers the PreferenceAnalysisAgent for the authenticated user and specified project. The endpoint SHALL return the analysis result.

#### Scenario: Manual analysis trigger
- **WHEN** `POST /memory/analyze` is called with `project_id`
- **THEN** the PreferenceAnalysisAgent runs (or enqueues) and returns the resulting PreferenceProfile

#### Scenario: Manual analysis with insufficient data
- **WHEN** `POST /memory/analyze` is called but the user has fewer than 5 feedback events
- **THEN** the endpoint returns a 400 error with message indicating insufficient data
