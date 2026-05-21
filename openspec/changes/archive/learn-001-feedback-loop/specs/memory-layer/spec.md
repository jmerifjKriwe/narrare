## MODIFIED Requirements

### Requirement: FeedbackService records events and forwards to mem0
The system SHALL implement `FeedbackService` in `core/memory/feedback_service.py` that: (1) persists the raw `FeedbackEvent` to the `feedback_events` PostgreSQL table, (2) translates the event into mem0-compatible input text including rating and enriched context, (3) the mem0 forwarding SHALL be done asynchronously via the event system (not synchronously in the request). The `_translate_to_memory_text()` method SHALL include rating information and context (chapter, genre, mode) in the translated text.

#### Scenario: Feedback with rating translated to memory text
- **WHEN** a `FeedbackEvent` with `action=accept`, `rating=5`, `intent="write"`, `context={"genre": "Fantasy", "mode": "full_draft"}` is translated
- **THEN** the memory text includes the rating, intent, context, and suggestion text

#### Scenario: Async mem0 forwarding
- **WHEN** `feedback_service.record(event)` is called
- **THEN** the event is persisted to PostgreSQL synchronously, and mem0 forwarding happens asynchronously via the event system

#### Scenario: mem0 unavailable during feedback
- **WHEN** `feedback_service.record(event)` is called and mem0 is unavailable
- **THEN** the event is still persisted to `feedback_events` table, a warning is logged, and no error is raised

### Requirement: mem0 client factory with user configuration
The system SHALL provide a `create_memory_client()` factory in `core/memory/mem0_client.py` that creates an `AsyncMemory` instance configured with: (1) pgvector backend using the application's PostgreSQL connection, (2) LLM provider from user settings with a cost-efficient default model per provider, (3) embedding provider resolved via the embedding cascade (not hardcoded to OpenAI), (4) custom instructions for Narrare-specific writing preference extraction.

#### Scenario: mem0 client uses z.ai provider with local embeddings
- **WHEN** `create_memory_client()` is called for a user with z.ai as their only provider
- **THEN** the mem0 config's LLM uses glm-4-flash via OpenAI-compatible endpoint, and the embedder uses sentence-transformers locally

#### Scenario: mem0 client uses OpenAI provider with OpenAI embeddings
- **WHEN** `create_memory_client()` is called for a user with OpenAI provider
- **THEN** the mem0 config's LLM uses gpt-4.1-nano and the embedder uses text-embedding-3-small

#### Scenario: Custom extraction instructions
- **WHEN** any `create_memory_client()` call creates an AsyncMemory instance
- **THEN** the config includes `custom_instructions` with writing-domain-specific extraction guidance

### Requirement: FeedbackEvent data model
The system SHALL extend the `FeedbackEvent` dataclass in `core/memory/models.py` with an optional `rating` field (int | None, values 1-5).

#### Scenario: FeedbackEvent with rating
- **WHEN** a `FeedbackEvent` is created with `rating=4`
- **THEN** the event's `rating` field is `4`

#### Scenario: FeedbackEvent without rating
- **WHEN** a `FeedbackEvent` is created without `rating`
- **THEN** the event's `rating` field is `None`

### Requirement: mem0 client lifecycle caching
The system SHALL cache mem0 `AsyncMemory` clients per user_id in a bounded LRU cache. The cache SHALL be invalidated when the user's provider settings or embedding settings change. Cache bounds SHALL be configurable (default: 100 users).

#### Scenario: Client reused across requests
- **WHEN** two feedback requests arrive for the same user within a short time
- **THEN** the same AsyncMemory client instance is reused (not created twice)

#### Scenario: Cache invalidated on settings change
- **WHEN** a user updates their AI provider settings
- **THEN** their cached mem0 client is removed and a new one will be created on next request
