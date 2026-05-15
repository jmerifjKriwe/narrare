## ADDED Requirements

### Requirement: Session state management
The system SHALL provide a `SessionManager` that maintains interactive writing session state including: conversation history (messages), prose buffer (accumulated accepted prose), session metadata (chapter ID, started_at, last_activity), and scene context (current scene goal, characters present).

#### Scenario: New session initialized
- **WHEN** an interactive session is started for a chapter
- **THEN** the `SessionManager` creates a new session with empty conversation history, empty prose buffer, and pre-populates scene context from chapter frontmatter (POV character, location, timeline).

#### Scenario: Conversation history maintained across turns
- **WHEN** a user and AI exchange 5 messages in a session
- **THEN** the `SessionManager` maintains the full conversation history and includes it in each LLM call for context continuity. History is truncated to the most recent 20 messages if exceeded.

#### Scenario: Prose buffer accumulates accepted text
- **WHEN** the user indicates acceptance of AI-generated prose in the session
- **THEN** the accepted text is appended to the prose buffer. The buffer can be saved to the chapter at any time.

#### Scenario: Session timeout and cleanup
- **WHEN** a session has no activity for 30 minutes
- **THEN** the `SessionManager` marks the session as expired, persists the prose buffer as a partial draft, and clears the session from active memory. Sessions are stored in Redis with a 30-minute TTL.

### Requirement: Session persistence in Redis
The system SHALL persist active session state in Redis with per-session keys and TTL-based expiration. This enables session recovery after server restart.

#### Scenario: Session state persisted to Redis
- **WHEN** a session message is processed
- **THEN** the full session state (conversation history, prose buffer, metadata) is serialized and stored in Redis under key `writing:session:{session_id}` with a 30-minute TTL refreshed on each message.

#### Scenario: Server restart recovers active sessions
- **WHEN** the server restarts while sessions are active
- **THEN** sessions with remaining TTL are recovered from Redis. Sessions past their TTL are marked as expired and their prose buffers saved as partial drafts.

### Requirement: Interview flow for interview-assisted mode
The system SHALL conduct a structured interview as a sequence of 3-5 targeted questions before generation. The interview collects: scene goal, characters involved, desired tone, central conflict, and target length.

#### Scenario: Interview questions generated from context
- **WHEN** an interview-assisted generation is started for a chapter with frontmatter referencing POV character "Elena"
- **THEN** the first interview question asks about the scene goal, the second references Elena specifically ("What is Elena trying to achieve?"), and subsequent questions adapt based on previous answers.

#### Scenario: User can skip interview questions
- **WHEN** a user skips an interview question
- **THEN** the system proceeds to the next question or, if all remaining are skipped, starts generation with whatever context is available (chapter frontmatter + KB entries).

#### Scenario: Interview answers used as generation context
- **WHEN** the interview completes with 4 answers collected
- **THEN** the answers are formatted and injected into the generation prompt as structured context (`{{interview_answers}}`), supplementing the standard `WritingContext`.

### Requirement: Save-to-chapter from session
The system SHALL allow saving the prose buffer to the chapter at any point during an interactive session. This creates an `ai_draft` chapter version linked to a generation request.

#### Scenario: User saves prose buffer mid-session
- **WHEN** a user clicks "Save to Chapter" during an active session with 1500 words in the prose buffer
- **THEN** the system creates an `ai_draft` chapter version with the buffer content, linked to a `generation_request` with mode `interactive_session`.

#### Scenario: Empty prose buffer save rejected
- **WHEN** a user tries to save with an empty prose buffer
- **THEN** the system returns a validation error: "No prose to save yet."

### Requirement: Session integrates with memory layer
The system SHALL record feedback events for interactive session prose through the foundation's Feedback API. Accept/save actions create positive feedback; rejected generations create negative feedback.

#### Scenario: User modifies AI prose before accepting
- **WHEN** a user edits AI-generated prose in the session and then accepts it
- **THEN** the system records a "modify" feedback event containing both the original AI text and the user's edited version, enabling the memory layer to learn from the delta.
