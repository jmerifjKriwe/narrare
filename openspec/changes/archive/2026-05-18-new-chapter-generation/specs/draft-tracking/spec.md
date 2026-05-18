## ADDED Requirements

### Requirement: Generation requests table tracks operational metadata
The system SHALL persist a `generation_requests` table with columns: `id` (UUID), `chapter_id` (FK), `status` (enum: pending/streaming/completed/stopped/failed), `mode` (enum: full_draft/scene_by_scene/interview_assisted/interactive_session), `model_id`, `provider_name`, `tokens_used`, `word_count`, `started_at`, `completed_at`, `error_message`, `user_id` (FK), `novel_id` (FK), `created_at`, `updated_at`.

#### Scenario: Generation request created on start
- **WHEN** a user initiates chapter generation
- **THEN** a new `generation_request` row is created with status `pending`, the requested mode, user ID, chapter ID, and novel ID.

#### Scenario: Status transitions during generation lifecycle
- **WHEN** a generation progresses through its lifecycle
- **THEN** the status transitions: `pending` → `streaming` (when first chunk arrives) → `completed` (when done), `stopped` (when user cancels), or `failed` (on error). Each transition updates `updated_at`.

#### Scenario: Failed generation records error
- **WHEN** a generation fails due to an LLM error
- **THEN** the `generation_request` row is updated with status `failed`, `error_message` contains the error details, `completed_at` is set, and `tokens_used` reflects tokens consumed before failure.

### Requirement: Draft content stored as AI draft chapter version
The system SHALL store generated text content using the existing `chapter_versions` table (ADR-011) with `version_type: "ai_draft"` and a nullable `generation_request_id` foreign key linking to the `generation_requests` table.

#### Scenario: Generated text saved as chapter version
- **WHEN** a generation completes (or is stopped with partial content)
- **THEN** the generated text is saved as a new `chapter_version` with `version_type: "ai_draft"`, `generation_request_id` set to the corresponding request, and `content` set to the full generated text.

#### Scenario: User accepts AI draft
- **WHEN** a user accepts an AI draft
- **THEN** the system promotes the `chapter_version` content to the chapter's current content (creating a new version with `version_type: "user_edit"`), and records a feedback event via the foundation's Feedback API with action "accept".

#### Scenario: User rejects AI draft
- **WHEN** a user rejects an AI draft
- **THEN** the `chapter_version` is retained (not deleted) for reference, the chapter content is unchanged, and a feedback event is recorded via the Feedback API with action "reject".

#### Scenario: User modifies AI draft before accepting
- **WHEN** a user edits the generated text before accepting
- **THEN** the system saves the modified version, records a feedback event with action "modify" including both the original and modified text for delta analysis by the memory layer.

### Requirement: Generation request lifecycle management
The system SHALL enforce generation request lifecycle rules: only one active generation per chapter at a time, automatic cleanup of stale requests after 24 hours, and status-based access control.

#### Scenario: Concurrent generation prevented
- **WHEN** a user tries to start a second generation for a chapter that already has an active generation (status `pending` or `streaming`)
- **THEN** the system returns a 409 Conflict error identifying the active generation request ID.

#### Scenario: Stale requests cleaned up
- **WHEN** a generation request has been in `streaming` status for more than 30 minutes
- **THEN** the system marks it as `failed` with error message "generation timed out" and releases the chapter for new generations.

### Requirement: Generation analytics available
The system SHALL expose aggregate generation statistics per novel and per user: total generations, success rate, average tokens per generation, average word count, and most-used model.

#### Scenario: User views generation statistics
- **WHEN** a user requests generation statistics for a novel
- **THEN** the system returns aggregated data from `generation_requests` for all generations in that novel.
