# Capability: Model Routing Cascade

## Purpose
Resolve which AI model to use for each LLM call through a configuration cascade: project → user → default. Replaces the hardcoded MODEL_ROUTING dict with runtime configuration.

## Requirements

### Requirement: Model routing cascade resolves per intent
The system SHALL resolve which model to use for an LLM call by checking a configuration cascade in this priority order: (1) project-level intent override, (2) project-level category override, (3) user-level intent override, (4) user-level category override, (5) user's default model. If no configuration exists at any level, the system SHALL raise a `ConfigurationError`.

#### Scenario: User has default model, no overrides
- **WHEN** LLM call with intent `WRITE` is made for user with default model `{provider: "openrouter", model: "anthropic/claude-sonnet-4-5"}`
- **THEN** system resolves to `{provider: "openrouter", model: "anthropic/claude-sonnet-4-5"}`

#### Scenario: User has category override
- **WHEN** LLM call with intent `ANALYSE` is made for user with default model `{provider: "openrouter", model: "anthropic/claude-sonnet-4-5"}` AND category override for "analysis" = `{provider: "openrouter", model: "openai/gpt-4o-mini"}`
- **THEN** system resolves to `{provider: "openrouter", model: "openai/gpt-4o-mini"}` (category override wins)

#### Scenario: User has intent override that is more specific than category
- **WHEN** LLM call with intent `CONSISTENCY` is made for user with category override for "analysis" = model A AND intent override for "consistency" = model B
- **THEN** system resolves to model B (intent override is more specific than category)

#### Scenario: Project override takes precedence over user override
- **WHEN** LLM call with intent `WRITE` is made in project with project-level override for "writing" = model A AND user-level override for "writing" = model B
- **THEN** system resolves to model A (project overrides user)

#### Scenario: No provider configured
- **WHEN** LLM call with intent `WRITE` is made for user with no provider configured
- **THEN** system raises `ConfigurationError` with message "No AI provider configured. Go to Settings → AI Provider to set up a provider."

### Requirement: Intent categories group related intents
The system SHALL group intents into categories for manageable configuration:

| Category | Intents |
|----------|---------|
| writing | WRITE, EXTEND, REWRITE, CO_AUTHOR |
| analysis | ANALYSE, SENTIMENT, CONSISTENCY, BETA_READ, VOICE |
| kb | KB_CREATE, KB_IMPROVE, KB_EXTRACT |
| planning | PLAN, SUMMARIZE |
| extraction | EXTRACT, SUGGEST |
| chat | CHAT |
| research | RESEARCH |

#### Scenario: Category lookup for intent
- **WHEN** system resolves model for intent `SENTIMENT`
- **THEN** system maps SENTIMENT to category "analysis" and checks for category override

#### Scenario: New intent added to existing category
- **WHEN** a developer adds intent `OUTLINE` to the `planning` category
- **THEN** existing category override for "planning" automatically applies to the new intent

#### Scenario: Intent not in any category
- **WHEN** system encounters an intent not mapped to any category
- **THEN** system skips category override level and proceeds to next cascade level

### Requirement: Model selection stores provider explicitly
Every model selection (default, category override, intent override) SHALL store both `provider_id` (reference to a `user_providers` entry) and `model_id` (the model identifier as known to that provider). The provider SHALL NOT be inferred from the model name.

#### Scenario: Select model from provider
- **WHEN** user selects model "anthropic/claude-sonnet-4-5" from provider "openrouter"
- **THEN** system stores `{provider_id: <openrouter-provider-uuid>, model_id: "anthropic/claude-sonnet-4-5"}`

#### Scenario: Same model name, different providers
- **WHEN** user has two providers (direct Anthropic + OpenRouter) and selects "claude-sonnet-4-5-20251020" from Anthropic
- **THEN** system routes through Anthropic's API with Anthropic API key, NOT through OpenRouter

### Requirement: Default model is required for AI features
A user SHALL have exactly one default model configured. All AI features SHALL require a default model to function. The default model SHALL be set during the Setup Wizard.

#### Scenario: First AI call after setup
- **WHEN** user completed setup with default model `{provider: "openai", model: "gpt-4o"}`
- **THEN** all AI features use `gpt-4o` via OpenAI unless overridden

#### Scenario: Default model references deleted provider
- **WHEN** user deletes the provider referenced by their default model
- **THEN** system clears the default model; all AI features return `ConfigurationError` until user selects a new default

### Requirement: Gateway accepts resolved model config
The LLM gateway SHALL accept a `ResolvedModelConfig` (containing `provider_name`, `model_id`, `temperature`, `max_tokens`, `streams`) and explicit credentials (`api_key`, `base_url`) from the caller. The gateway SHALL NOT call `get_model_config()` or `infer_provider()` at runtime.

#### Scenario: Gateway call with resolved config
- **WHEN** service calls `gateway.run(intent=LLMIntent.WRITE, config=ResolvedModelConfig(provider_name="openrouter", model_id="gpt-4o", ...), api_key="sk-or-...")`
- **THEN** gateway creates an OpenRouter provider instance with the provided API key and calls the model

#### Scenario: Gateway receives no config
- **WHEN** service calls `gateway.run()` without a `config` parameter
- **THEN** gateway raises `ValueError("ResolvedModelConfig is required")`

### Requirement: Provider factories accept explicit credentials
All provider factory functions SHALL accept optional `api_key` and `base_url` keyword arguments. When provided, these override environment variable defaults.

#### Scenario: Factory with explicit credentials
- **WHEN** `_make_openrouter("gpt-4o", api_key="sk-or-...", base_url="https://openrouter.ai/api/v1")` is called
- **THEN** provider instance uses the explicit API key and base URL

#### Scenario: Factory without explicit credentials (dev/test)
- **WHEN** `_make_anthropic("claude-sonnet-4-5-20251020")` is called without api_key
- **THEN** provider instance reads from `ANTHROPIC_API_KEY` env var (backward compatibility for tests)

### Requirement: Resolution result includes source information
When the model routing resolver resolves a config for an intent, it SHALL return the resolved `ResolvedModelConfig` along with metadata indicating which cascade level was used (e.g., "user_category", "user_default", "project_intent").

#### Scenario: Resolution metadata for logging
- **WHEN** resolver resolves intent WRITE to user's category override
- **THEN** result includes `source="user_category"` and `category="writing"` for observability and debugging
