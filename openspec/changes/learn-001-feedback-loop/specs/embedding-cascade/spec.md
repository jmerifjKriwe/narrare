## ADDED Requirements

### Requirement: Embedding cascade resolver
The system SHALL provide an `EmbeddingCascadeResolver` in `core/memory/embedding_cascade.py` that selects the best available embedding configuration based on the user's configured providers. The cascade order SHALL be: (1) OpenAI text-embedding-3-small if an OpenAI provider exists, (2) provider-native embeddings if the provider advertises embedding support, (3) local sentence-transformers with all-MiniLM-L6-v2, (4) disabled (NullMemoryClient).

#### Scenario: User has OpenAI provider
- **WHEN** `resolve_embedding_config(user_providers)` is called and the user has an OpenAI provider with a valid API key
- **THEN** the resolver returns `EmbeddingConfig(provider="openai", model="text-embedding-3-small", api_key=<user_key>)`

#### Scenario: User has z.ai provider only
- **WHEN** `resolve_embedding_config(user_providers)` is called and the user has only a z.ai provider
- **THEN** the resolver returns `EmbeddingConfig(provider="huggingface", model="all-MiniLM-L6-v2")` with no API key

#### Scenario: User has Anthropic provider only
- **WHEN** `resolve_embedding_config(user_providers)` is called and the user has only an Anthropic provider
- **THEN** the resolver returns `EmbeddingConfig(provider="huggingface", model="all-MiniLM-L6-v2")` with no API key

#### Scenario: User has Ollama provider
- **WHEN** `resolve_embedding_config(user_providers)` is called and the user has an Ollama provider
- **THEN** the resolver returns `EmbeddingConfig(provider="ollama", model="nomic-embed-text", base_url=<ollama_url>)`

#### Scenario: User has multiple providers including OpenAI
- **WHEN** `resolve_embedding_config(user_providers)` is called and the user has both OpenAI and z.ai providers
- **THEN** the resolver returns OpenAI configuration (Stufe 1 takes priority)

### Requirement: Embedding configuration in user settings
The system SHALL add `embedding_provider` and `embedding_model` fields to the `user_ai_settings` table and corresponding Pydantic schemas. `embedding_provider` SHALL accept values: "auto" (default), "openai", "local", "disabled". When set to "auto", the cascade resolver determines the provider automatically.

#### Scenario: Default embedding setting is auto
- **WHEN** a new user is created
- **THEN** their `user_ai_settings.embedding_provider` defaults to "auto"

#### Scenario: User explicitly chooses local embeddings
- **WHEN** a user sets `embedding_provider` to "local" via `PATCH /settings/ai`
- **THEN** the system uses sentence-transformers regardless of available providers

#### Scenario: User disables memory features
- **WHEN** a user sets `embedding_provider` to "disabled" via `PATCH /settings/ai`
- **THEN** the system uses NullMemoryClient and no embedding or mem0 operations occur

### Requirement: Embedding configuration migration
The system SHALL create an Alembic migration that adds `embedding_provider` (VARCHAR, default "auto") and `embedding_model` (VARCHAR, nullable) columns to the `user_ai_settings` table.

#### Scenario: Migration applies successfully
- **WHEN** `alembic upgrade head` is run
- **THEN** the `user_ai_settings` table has `embedding_provider` and `embedding_model` columns with correct defaults

### Requirement: Embedding settings in API
The system SHALL include `embedding_provider` and `embedding_model` in the `GET/PATCH /settings/ai` request/response schemas. The settings UI SHALL display the currently active embedding tier.

#### Scenario: Get embedding settings
- **WHEN** `GET /settings/ai` is called for a user with `embedding_provider="auto"`
- **THEN** the response includes `embedding_provider: "auto"` and `active_embedding_tier` indicating which cascade level is in use

### Requirement: sentence-transformers local embedding support
The system SHALL add `sentence-transformers` as an optional dependency. When Stufe 3 (local embeddings) is active, the system SHALL use `all-MiniLM-L6-v2` via the HuggingFace provider in mem0's embedder config.

#### Scenario: Local embeddings work without API keys
- **WHEN** mem0 is configured with `embedder.provider="huggingface"` and `embedder.config.model="all-MiniLM-L6-v2"`
- **THEN** embeddings are generated locally without any API call
