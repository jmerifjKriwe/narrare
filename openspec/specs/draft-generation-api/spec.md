# Draft Generation API

**Purpose**: The system SHALL provide REST API endpoints for managing AI generation of chapter content, including starting, stopping, accepting, and rejecting drafts.

## Requirements

### Requirement: Start generation endpoint
The system SHALL provide `POST /api/v1/writing/chapters/{chapter_id}/generate` that accepts a generation request with: `mode` (required), `prompt` or `outline` (at least one required unless mode is `auto_continue`), `word_target` (optional), `tone` (optional, default "balanced"), and `language` (optional, defaults to project language). Returns a `generation_request_id` and connects to an SSE stream for text delivery.

#### Scenario: Start full draft generation from outline
- **WHEN** a POST request is sent with `mode: "full_draft"`, `outline: "Elena confronts the Council"`, and `word_target: 3000`
- **THEN** the system creates a `generation_request`, starts the writing pipeline, and returns the request ID with an SSE connection for streaming the generated text.

#### Scenario: Start auto-continue generation
- **WHEN** a POST request is sent with `mode: "full_draft"` and `auto_continue: true` (no prompt or outline)
- **THEN** the system uses the chapter's existing content and frontmatter as implicit context to continue the chapter where it left off.

#### Scenario: Missing required input returns validation error
- **WHEN** a POST request is sent with `mode: "full_draft"` but no prompt, outline, or auto_continue flag
- **THEN** the system returns a 422 Validation Error: "At least one of prompt, outline, or auto_continue is required."

### Requirement: Stop generation endpoint
The system SHALL provide `DELETE /api/v1/writing/generation/{request_id}` that stops an in-progress generation. Preserves all text generated up to the stop point.

#### Scenario: Stop active generation
- **WHEN** a DELETE request is sent for a generation request with status `streaming`
- **THEN** the system stops the LLM call, saves all generated text as a partial `ai_draft` chapter version, updates the request status to `stopped`, and returns the partial word count.

#### Scenario: Stop already-completed generation returns 409
- **WHEN** a DELETE request is sent for a generation request with status `completed`
- **THEN** the system returns 409 Conflict: "Generation already completed."

### Requirement: Accept draft endpoint
The system SHALL provide `POST /api/v1/writing/generation/{request_id}/accept` that promotes the AI draft to chapter content and records positive feedback.

#### Scenario: Accept completed draft
- **WHEN** a POST request is sent to accept a generation with status `completed`
- **THEN** the system promotes the `ai_draft` chapter version to the chapter's current content, records a feedback event with action "accept", and returns the updated chapter.

#### Scenario: Accept partial (stopped) draft
- **WHEN** a POST request is sent to accept a generation with status `stopped`
- **THEN** the system promotes the partial `ai_draft` content to chapter content (user is aware it's partial), records feedback, and returns the updated chapter.

### Requirement: Reject draft endpoint
The system SHALL provide `POST /api/v1/writing/generation/{request_id}/reject` that discards the draft from active content and records negative feedback. The draft version is retained for reference.

#### Scenario: Reject draft
- **WHEN** a POST request is sent to reject a generation
- **THEN** the system marks the `ai_draft` version as rejected, records a feedback event with action "reject", and the chapter content remains unchanged.

### Requirement: Scene-by-scene control endpoints
The system SHALL provide `POST /api/v1/writing/generation/{request_id}/scene/next` to trigger generation of the next scene, and `POST /api/v1/writing/generation/{request_id}/scene/{scene_number}/accept` to accept individual scenes.

#### Scenario: Request next scene after review
- **WHEN** a POST request is sent to generate the next scene after reviewing scene 1
- **THEN** the system starts generating scene 2 from the outline, streams it via SSE, and marks scene 1 as accepted.

#### Scenario: No more scenes available
- **WHEN** a POST request is sent for the next scene but all scenes in the outline have been generated
- **THEN** the system returns 200 with a completion message and assembles the final chapter from all accepted scenes.

### Requirement: WebSocket endpoint for interactive sessions
The system SHALL provide `WS /api/v1/writing/sessions/{chapter_id}` for interactive writing sessions (WRITE-005). The WebSocket accepts user messages and returns AI-generated prose in real-time.

#### Scenario: Start interactive session
- **WHEN** a WebSocket connection is opened to the sessions endpoint
- **THEN** the system creates a session with conversation history, sends a greeting message ("What would you like to write today?"), and waits for user direction.

#### Scenario: User sends direction, AI generates prose
- **WHEN** the user sends a message like "Write the scene where Elena enters the Council chamber"
- **THEN** the AI generates prose based on the direction and assembled context, streams it back as a WebSocket message, and appends it to the session's prose buffer.

#### Scenario: User requests revision
- **WHEN** the user sends "Make it more tense, shorter sentences"
- **THEN** the AI regenerates the last prose segment with the revised direction, maintaining conversation context.

#### Scenario: Session timeout after inactivity
- **WHEN** no messages are exchanged for 30 minutes
- **THEN** the system sends a session timeout notification, saves the prose buffer as a partial draft, and closes the WebSocket connection.

### Requirement: GenerationMode enum supports EXTEND
The `GenerationMode` enum SHALL include `EXTEND = "extend"` alongside the existing FULL_DRAFT, SCENE_BY_SCENE, INTERVIEW_ASSISTED, and INTERACTIVE_SESSION values.

#### Scenario: Extend mode in pipeline dispatch
- **WHEN** `WritingPipeline.generate()` receives a request with `mode == EXTEND`
- **THEN** it SHALL dispatch to `_extend()` instead of raising `WritingError("Unsupported generation mode")`

#### Scenario: Extend mode stored in generation_requests
- **WHEN** a generation_request is created with `mode = "extend"`
- **THEN** the mode column SHALL accept the value without CHECK constraint violation

#### Scenario: Extend mode in API schema
- **WHEN** a `GenerateRequest` or `ExtendRequest` uses mode "extend"
- **THEN** the `GenerationModeEnum` SHALL validate it as a legal value

### Requirement: GenerationMode enum supports REWRITE
The `GenerationMode` enum SHALL include `REWRITE = "rewrite"` alongside the existing FULL_DRAFT, SCENE_BY_SCENE, INTERVIEW_ASSISTED, INTERACTIVE_SESSION, and EXTEND values.

#### Scenario: Rewrite mode in pipeline dispatch
- **WHEN** `WritingPipeline.generate()` receives a request with `mode == REWRITE`
- **THEN** it SHALL dispatch to `_rewrite()` instead of raising `WritingError("Unsupported generation mode")`

#### Scenario: Rewrite mode stored in generation_requests
- **WHEN** a generation_request is created with `mode = "rewrite"`
- **THEN** the mode column SHALL accept the value without CHECK constraint violation

#### Scenario: Rewrite mode in API schema
- **WHEN** a `RewriteRequest` uses mode "rewrite"
- **THEN** the `GenerationModeEnum` SHALL validate it as a legal value

### Requirement: All endpoints require authentication
All writing API endpoints SHALL require a valid JWT access token. Generation requests are scoped to the authenticated user.

#### Scenario: Unauthenticated request rejected
- **WHEN** a request is sent without a valid JWT token
- **THEN** the system returns 401 Unauthorized.
