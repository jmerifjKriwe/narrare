# Capability: Memory Layer

## Purpose
Implement the core memory subsystem for preference learning from user feedback. Provides feedback event recording, preference profile aggregation via mem0, and integration with the prompt composition pipeline for injecting user preferences into AI prompts.

## Requirements

### Requirement: Memory module protocols
The system SHALL define Protocol classes in `core/memory/protocols.py` for `FeedbackCollector`, `PreferenceProvider`, and `MemoryFacade`. These protocols SHALL define the interfaces for feedback recording, preference retrieval, and the combined facade.

#### Scenario: FeedbackCollector protocol
- **WHEN** a service depends on `FeedbackCollector`
- **THEN** it MUST implement `async def record(self, event: FeedbackEvent) -> None` and `async def get_history(self, user_id: UUID, project_id: UUID, *, limit: int = 100) -> list[FeedbackEvent]`

#### Scenario: PreferenceProvider protocol
- **WHEN** a service depends on `PreferenceProvider`
- **THEN** it MUST implement `async def get_preferences(self, user_id: UUID, project_id: UUID) -> PreferenceProfile` and `async def reset(self, user_id: UUID, project_id: UUID) -> None`

### Requirement: FeedbackEvent data model
The system SHALL define an immutable `FeedbackEvent` dataclass in `core/memory/models.py` with fields: `id`, `user_id`, `project_id`, `suggestion_id`, `action` (FeedbackAction enum: accept/reject/modify), `intent` (LLMIntent), `suggestion_text`, `modification` (optional), `context` (dict), `created_at`.

#### Scenario: FeedbackEvent is immutable
- **WHEN** a `FeedbackEvent` is created
- **THEN** its fields cannot be modified after creation (frozen dataclass)

### Requirement: PreferenceProfile data model
The system SHALL define a `PreferenceProfile` dataclass in `core/memory/models.py` with fields: `user_id`, `project_id`, `event_count`, `confidence` (float 0-1), `last_updated`, `style` (dict), `content` (dict), `constraints` (list of strings). It SHALL provide a `to_prompt_text()` method that formats the profile as a concise text block suitable for prompt injection.

#### Scenario: PreferenceProfile formats for prompt
- **WHEN** `profile.to_prompt_text()` is called on a non-empty profile
- **THEN** it returns a non-empty string containing structured preference information suitable for `{{user_preferences}}` substitution

#### Scenario: Empty PreferenceProfile
- **WHEN** `profile.to_prompt_text()` is called on a profile with `event_count == 0`
- **THEN** it returns an empty string

### Requirement: FeedbackService records events and forwards to mem0
The system SHALL implement `FeedbackService` in `core/memory/feedback_service.py` that: (1) persists the raw `FeedbackEvent` to the `feedback_events` PostgreSQL table, (2) translates the event into mem0-compatible input text, and (3) calls `mem0.add()` with the translated text scoped by `user_id` and `app_id` (project_id).

#### Scenario: Feedback recorded successfully
- **WHEN** `feedback_service.record(event)` is called with a valid `FeedbackEvent`
- **THEN** the event is persisted to `feedback_events` table AND mem0 receives the translated memory input

#### Scenario: mem0 unavailable during feedback
- **WHEN** `feedback_service.record(event)` is called and mem0 is unavailable (NullMemoryClient)
- **THEN** the event is still persisted to `feedback_events` table, a warning is logged, and no error is raised

### Requirement: PreferenceService queries mem0 for preferences
The system SHALL implement `PreferenceService` in `core/memory/preference_service.py` that queries mem0 using `search()` with intent-specific queries and aggregates results into a `PreferenceProfile`.

#### Scenario: Preferences retrieved for user and project
- **WHEN** `preference_service.get_preferences(user_id, project_id)` is called
- **THEN** mem0 is queried with filters `{"user_id": str(user_id), "app_id": str(project_id)}` and results are aggregated into a `PreferenceProfile`

#### Scenario: No preferences exist
- **WHEN** `preference_service.get_preferences(user_id, project_id)` is called and mem0 returns no results
- **THEN** an empty `PreferenceProfile` with `event_count == 0` and `confidence == 0.0` is returned

### Requirement: mem0 client factory with user configuration
The system SHALL provide a `create_memory_client()` factory function in `core/memory/mem0_client.py` that creates an `AsyncMemory` instance configured with: (1) pgvector backend using the application's PostgreSQL connection, (2) LLM provider from user settings with a cost-efficient default model, (3) the same embedding model as the application, (4) custom instructions for Narrare-specific memory extraction.

#### Scenario: mem0 client uses user's provider
- **WHEN** `create_memory_client()` is called with `provider_config` where `provider="anthropic"` and `api_key="sk-ant-..."`
- **THEN** the mem0 config's LLM section has `provider: "anthropic"` and the user's API key

#### Scenario: mem0 client uses default model
- **WHEN** `create_memory_client()` is called with no `memory_model` override and provider `"anthropic"`
- **THEN** the mem0 config's model defaults to a cost-efficient Anthropic model (e.g., Claude Haiku)

### Requirement: NullMemoryClient for graceful degradation
The system SHALL implement a `NullMemoryClient` that provides no-op implementations of all mem0 operations (add, search, get_all, delete, delete_all). When mem0 is unavailable, the system SHALL use `NullMemoryClient` and log warnings.

#### Scenario: NullMemoryClient add
- **WHEN** `NullMemoryClient.add()` is called
- **THEN** a warning is logged and `{"results": [], "relations": []}` is returned without error

#### Scenario: NullMemoryClient search
- **WHEN** `NullMemoryClient.search()` is called
- **THEN** a warning is logged and `{"results": []}` is returned without error

### Requirement: mem0 RULE-01 exception documentation
The system SHALL document mem0's internal LLM calls as a RULE-01 exception in `docs/_shared/CONSTRAINTS.md`, analogous to the existing embedding exception. The documentation SHALL explain that mem0 uses the user's configured provider/model and that the gateway's intent routing and rate limiting do not apply to infrastructure-level memory extraction.

#### Scenario: RULE-01 exception documented
- **WHEN** a developer reads CONSTRAINTS.md
- **THEN** there is a documented exception for mem0 memory extraction LLM calls, explaining the rationale and provider control

### Requirement: PromptContext memory fields
The system SHALL add `user_preferences: str`, `avoidance_patterns: str`, and `style_constraints: str` fields to `PromptContext` in `core/prompts/context.py`. These fields SHALL be included in `as_variables()` output.

#### Scenario: Memory variables available in prompts
- **WHEN** a `PromptContext` has `user_preferences = "Prefers short sentences"`
- **THEN** `context.as_variables()["user_preferences"]` returns `"Prefers short sentences"`

### Requirement: PromptComposer preference injection
The system SHALL extend `PromptComposer.build()` to automatically resolve user preferences if a `PreferenceService` is configured and `context.user_preferences` is empty. Resolved preferences SHALL be set on the context before variable substitution.

#### Scenario: Preferences auto-injected
- **WHEN** `PromptComposer.build()` is called with a `PreferenceService` configured and `context.user_preferences == ""`
- **THEN** the composer calls `preference_service.get_preferences()`, populates `context.user_preferences` with the formatted text, and includes it in the final prompt

#### Scenario: No PreferenceService configured
- **WHEN** `PromptComposer.build()` is called without a `PreferenceService`
- **THEN** the composer proceeds without preference injection (backward compatible)
