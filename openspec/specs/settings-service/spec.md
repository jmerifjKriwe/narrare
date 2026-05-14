# Capability: Settings Service

## Purpose
Service layer for AI settings — user-level defaults, category/intent overrides, project-level overrides, and provider CRUD. Validates provider references and encrypts API keys.

## Requirements

### Requirement: Settings module follows contract-first pattern
The settings module SHALL define Protocol classes in `contracts.py` BEFORE implementing repository and service classes. All repository and service classes SHALL implement their corresponding Protocol.

#### Scenario: Contracts define repository interfaces
- **WHEN** developer opens `settings/contracts.py`
- **THEN** they find `UserSettingsRepositoryProtocol`, `ProjectSettingsRepositoryProtocol`, `UserProvidersRepositoryProtocol`, `UserAiSettingsRepositoryProtocol` — each defining the async methods the repositories must implement

#### Scenario: Service layer exists between router and repository
- **WHEN** router receives a request
- **THEN** it delegates to a service class (e.g., `UserAiSettingsService`), NOT directly to a repository. The service contains business logic; the repository contains only database queries.

### Requirement: User AI settings service
The system SHALL provide `UserAiSettingsService` that manages the user's default model, category overrides, intent overrides, and token limit profile. The service SHALL validate that any referenced provider exists and is active before persisting.

#### Scenario: Set default model
- **WHEN** user sets default model to `{provider_id: <uuid>, model_id: "gpt-4o"}`
- **THEN** service verifies the provider exists and is active; persists the default model

#### Scenario: Set default model with inactive provider
- **WHEN** user sets default model referencing a deactivated provider
- **THEN** service rejects with error "Provider is not active"

#### Scenario: Set category override
- **WHEN** user sets category override for "writing" to `{provider_id: <uuid>, model_id: "claude-sonnet-4-5-20251020"}`
- **THEN** service validates the provider exists; persists the override; future WRITE/EXTEND/REWRITE/CO_AUTHOR calls use this model

#### Scenario: Clear override
- **WHEN** user removes the category override for "writing"
- **THEN** service removes the entry from the overrides JSONB; future writing intents fall through to the next cascade level

### Requirement: Project AI settings service
The system SHALL provide `ProjectAiSettingsService` that manages project-level model and token limit overrides. Project overrides SHALL cascade over user-level settings.

#### Scenario: Set project-level category override
- **WHEN** user sets project override for "analysis" to a specific model
- **THEN** all analysis intents within that project use the project override, regardless of user-level settings

#### Scenario: Get effective settings with source information
- **WHEN** client requests project AI settings
- **THEN** response includes the resolved effective settings AND a `source` map indicating which level each setting comes from: `{"writing": "project", "analysis": "user", "chat": "default"}`

### Requirement: Settings REST API endpoints
The system SHALL expose REST API endpoints for AI settings management:

- `GET /settings/ai/providers` — list user's providers (masked keys)
- `POST /settings/ai/providers` — add a provider
- `PATCH /settings/ai/providers/{id}` — update provider
- `DELETE /settings/ai/providers/{id}` — delete provider
- `GET /settings/ai` — get user AI settings (default model, overrides, token limits)
- `PATCH /settings/ai` — update user AI settings
- `GET /settings/ai/novels/{novel_id}` — get project AI settings
- `PATCH /settings/ai/novels/{novel_id}` — update project AI settings

#### Scenario: List providers returns masked keys
- **WHEN** client calls `GET /settings/ai/providers`
- **THEN** response includes providers with `api_key_last4: "...abc"` and `has_api_key: true`, never the full key

#### Scenario: Add provider validates credentials
- **WHEN** client calls `POST /settings/ai/providers` with provider name and API key
- **THEN** service validates credentials via test call before persisting; returns 400 if validation fails

#### Scenario: Update user AI settings validates references
- **WHEN** client calls `PATCH /settings/ai` with a default_provider_id referencing a non-existent provider
- **THEN** service returns 422 with error "Referenced provider not found"

### Requirement: Database migration for AI settings
The system SHALL provide an Alembic migration that creates the `user_providers` and `user_ai_settings` tables and adds AI override columns to `project_settings`. Existing data in `project_settings.ai_provider`, `project_settings.ai_model`, and `project_settings.model_overrides` SHALL be migrated to the new structure where possible.

#### Scenario: Fresh installation
- **WHEN** migration runs on a fresh database
- **THEN** `user_providers` and `user_ai_settings` tables are created; `project_settings` gains new JSONB columns for category/intent/token overrides

#### Scenario: Migration of existing provider data
- **WHEN** migration runs and a project has `ai_provider="anthropic"` and `ai_model="claude-sonnet-4-5-20251020"`
- **THEN** migration creates a `user_providers` entry for the project owner with provider "anthropic" and sets their `user_ai_settings.default_model` to "claude-sonnet-4-5-20251020"; API key is NOT migrated (user must re-enter)
