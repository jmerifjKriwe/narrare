# Capability: Provider Management

## Purpose
Manage user AI provider entries — register, update, deactivate, delete providers with encrypted API keys. Provider entries are referenced by model routing and AI settings.

## Requirements

### Requirement: User can register multiple AI providers
The system SHALL allow users to register one or more AI providers. Each provider entry SHALL consist of: a provider name (from a supported list), an API key (encrypted at rest), an optional base URL (for OpenAI-compatible providers), and an active/inactive status.

#### Scenario: Register first provider during setup
- **WHEN** user completes Setup Wizard Step 4 with provider "openrouter" and API key "sk-or-..."
- **THEN** system creates a `user_providers` entry with the provider name, encrypted API key, no base URL (uses provider default), and status active

#### Scenario: Register additional provider via settings
- **WHEN** user navigates to Settings → AI Providers and adds provider "anthropic" with API key "sk-ant-..."
- **THEN** system creates a second `user_providers` entry; both providers are available for model selection

#### Scenario: Register provider with custom base URL
- **WHEN** user adds provider "openai" with API key and custom base URL "https://my-proxy.example.com/v1"
- **THEN** system stores the base URL; all calls to this provider SHALL route through the custom URL

### Requirement: User can update provider credentials
The system SHALL allow users to update the API key and base URL of an existing provider entry.

#### Scenario: Update API key
- **WHEN** user updates the API key for provider "anthropic"
- **THEN** system replaces the encrypted API key; the new key is used for subsequent LLM calls

#### Scenario: Regenerate key with zero downtime
- **WHEN** user updates an API key while an LLM call is in progress using the old key
- **THEN** the in-progress call completes with the old key; subsequent calls use the new key

### Requirement: User can deactivate a provider
The system SHALL allow users to deactivate a provider without deleting it. Deactivated providers SHALL NOT appear in model selection dropdowns.

#### Scenario: Deactivate provider
- **WHEN** user deactivates provider "groq"
- **THEN** the provider's `is_active` is set to false; it no longer appears in model selection; any model routing referencing this provider returns a validation error

#### Scenario: Deactivate only remaining provider
- **WHEN** user attempts to deactivate their only active provider
- **THEN** system rejects the operation with error "Cannot deactivate the only active provider. Add another provider first."

### Requirement: User can delete a provider
The system SHALL allow users to permanently delete a provider entry. If the deleted provider is referenced as a default or in any override, those references SHALL be cleared.

#### Scenario: Delete provider not referenced by any setting
- **WHEN** user deletes provider "groq" which is not set as default and not in any override
- **THEN** system removes the `user_providers` entry permanently

#### Scenario: Delete provider that is the default
- **WHEN** user deletes their default provider "anthropic"
- **THEN** system removes the entry AND clears the default provider/model from `user_ai_settings`; system prompts user to select a new default

### Requirement: API keys are encrypted at rest
All API keys stored in the database SHALL be encrypted using Fernet symmetric encryption. The encryption key SHALL come from the `NARRARE_ENCRYPTION_KEY` environment variable.

#### Scenario: API key stored encrypted
- **WHEN** user saves an API key "sk-ant-abc123"
- **THEN** database stores a Fernet-encrypted token, NOT the plaintext key

#### Scenario: API key never returned via API
- **WHEN** client requests user settings or provider list via REST API
- **THEN** response includes `has_api_key: true` and last 4 characters, but NEVER the full API key

#### Scenario: Missing encryption key
- **WHEN** `NARRARE_ENCRYPTION_KEY` is not set and the system attempts to encrypt or decrypt an API key
- **THEN** system raises `ConfigurationError` at startup, NOT at runtime

### Requirement: Provider validation on save
The system SHALL validate provider credentials by making a minimal test call before persisting them.

#### Scenario: Valid credentials
- **WHEN** user saves provider "anthropic" with a valid API key
- **THEN** system makes a test call; on success, credentials are persisted

#### Scenario: Invalid credentials
- **WHEN** user saves provider "anthropic" with an invalid API key
- **THEN** system rejects the save with error "API key validation failed: authentication error"

#### Scenario: Validation timeout
- **WHEN** provider validation call times out after 10 seconds
- **THEN** system persists credentials with a warning "Could not verify API key — saved but unverified"

### Requirement: Supported providers list is extensible
The system SHALL provide a known list of supported providers (anthropic, openai, google, groq, openrouter, zai, ollama) and SHALL allow adding new providers without changing the provider management code.

#### Scenario: Provider listed in settings
- **WHEN** user opens provider settings
- **THEN** system shows the list of registered providers from `core/llm/_providers/registry.py :: available()`

#### Scenario: New provider added to codebase
- **WHEN** a developer registers a new provider "mistral" in `core/llm/_providers/`
- **THEN** it automatically appears in the provider settings dropdown without UI code changes
