## 1. Core: Data Model & Types

- [ ] 1.1 Create `ResolvedModelConfig` dataclass in `core/llm/intents.py` (replacing `ModelConfig`): fields `provider_name`, `model_id`, `temperature`, `max_tokens`, `streams`
- [ ] 1.2 Define `IntentCategory` enum and `INTENT_CATEGORY_MAP` mapping each `LLMIntent` to its category (writing, analysis, kb, planning, extraction, chat, research)
- [ ] 1.3 Create `core/llm/model_routing.py` with `ModelRoutingResolver` protocol and `ResolvedModel` result type (config + source metadata)
- [ ] 1.4 Define Pydantic schemas for overrides: `CategoryOverride(provider_id, model_id)`, `IntentOverride(provider_id, model_id)`, `TokenLimitOverride(max_tokens, temperature)` with validation

## 2. Core: Provider Factory Updates

- [ ] 2.1 Update `ProviderFactory` protocol in `registry.py` to accept optional `api_key` and `base_url` kwargs
- [ ] 2.2 Update `anthropic.py` factory to accept explicit `api_key` parameter
- [ ] 2.3 Update `openai.py` factory to accept explicit `api_key` and `base_url` parameters
- [ ] 2.4 Update `others.py` factories (google, groq, openrouter, zai) to accept explicit credentials
- [ ] 2.5 Update `ollama.py` factory to accept explicit `base_url` parameter
- [ ] 2.6 Update `registry.get()` to support credential pass-through, or add `get_with_credentials()` method

## 3. Core: Gateway Refactor

- [ ] 3.1 Add `ResolvedModelConfig` parameter to `gateway.run()` — caller provides resolved config + credentials
- [ ] 3.2 Add `ResolvedModelConfig` parameter to `gateway.stream()` — same pattern
- [ ] 3.3 Remove `get_model_config()` call from gateway; remove `model_override` parameter
- [ ] 3.4 Remove `infer_provider()` call from gateway runtime path (keep as dev utility in registry)
- [ ] 3.5 Add credential lookup: gateway uses explicit `api_key`/`base_url` from caller to construct provider instances

## 4. Core: Remove Hardcoded Routing

- [ ] 4.1 Remove `MODEL_ROUTING` dict from `intents.py` (was documentation-only, now dead code)
- [ ] 4.2 Remove `get_model_config()` function from `intents.py`
- [ ] 4.3 Keep `LLMIntent` enum and `ModelConfig` (renamed to `ResolvedModelConfig`) — these are still needed

## 5. Backend: Database Migration

- [ ] 5.1 Create Alembic migration: `user_providers` table (id, user_id, provider_name, api_key_encrypted, base_url, is_active, timestamps)
- [ ] 5.2 Add `user_ai_settings` table (user_id PK, default_provider_id FK, default_model, category_overrides JSONB, intent_overrides JSONB, token_limit_profile, token_limit_overrides JSONB, timestamps)
- [ ] 5.3 Add JSONB columns to `project_settings`: `category_overrides`, `intent_overrides`, `token_limit_overrides`
- [ ] 5.4 Add data migration: move existing `project_settings.ai_provider`/`ai_model` to `user_providers` + `user_ai_settings` where owner is identifiable

## 6. Backend: Settings Contracts (RULE-03)

- [ ] 6.1 Define `UserProvidersRepositoryProtocol` in `settings/contracts.py` (CRUD for provider entries)
- [ ] 6.2 Define `UserAiSettingsRepositoryProtocol` in `settings/contracts.py` (get/update AI settings)
- [ ] 6.3 Define `ProjectAiSettingsRepositoryProtocol` in `settings/contracts.py` (get/update project AI overrides)
- [ ] 6.4 Define `UserProvidersServiceProtocol` and `UserAiSettingsServiceProtocol` in `settings/contracts.py`
- [ ] 6.5 Update existing `UserSettingsRepositoryProtocol` and `ProjectSettingsRepositoryProtocol` to reflect new schema

## 7. Backend: API Key Encryption

- [ ] 7.1 Create `core/crypto.py` (or `shared/crypto.py`): Fernet encrypt/decrypt helper, reads `NARRARE_ENCRYPTION_KEY` at import/startup
- [ ] 7.2 Add startup check: fail fast if `NARRARE_ENCRYPTION_KEY` is missing when any provider write is attempted

## 8. Backend: Repository Layer

- [ ] 8.1 Implement `UserProvidersRepository` (create, get, get_by_user, update, delete, get_active)
- [ ] 8.2 Implement `UserAiSettingsRepository` (get, update, with Pydantic JSONB validation)
- [ ] 8.3 Implement `ProjectAiSettingsRepository` (get, update, with Pydantic JSONB validation)
- [ ] 8.4 Update `ProjectSettingsRepository` to handle new JSONB columns

## 9. Backend: Service Layer

- [ ] 9.1 Implement `UserProvidersService` — CRUD with credential validation (test call), encryption on save, masking on read
- [ ] 9.2 Implement `UserAiSettingsService` — default model management, category/intent overrides, token limit profile management, provider reference validation
- [ ] 9.3 Implement `ProjectAiSettingsService` — project-level overrides, effective settings resolution with source metadata
- [ ] 9.4 Implement `ModelRoutingResolver` (backend side) — resolves `ResolvedModelConfig` for a given intent + user + project using the cascade

## 10. Backend: Schemas & Router

- [ ] 10.1 Create Pydantic schemas for providers: `CreateProviderRequest`, `UpdateProviderRequest`, `ProviderResponse` (masked key), `ProviderListResponse`
- [ ] 10.2 Create Pydantic schemas for AI settings: `UserAiSettingsResponse`, `UpdateUserAiSettingsRequest`, `ProjectAiSettingsResponse`, `UpdateProjectAiSettingsRequest`
- [ ] 10.3 Create token limit schemas: `TokenLimitProfileConfig`, `TokenLimitOverrides`
- [ ] 10.4 Add REST endpoints in `settings/router.py`: provider CRUD (`/settings/ai/providers`), user AI settings (`/settings/ai`), project AI settings (`/settings/ai/novels/{id}`)
- [ ] 10.5 Add dependency injection for new services in `_app/dependencies.py`

## 11. Backend: Gateway Integration

- [ ] 11.1 Wire `ModelRoutingResolver` into service DI — services call resolver to get `ResolvedModelConfig` + credentials
- [ ] 11.2 Update all existing LLM-calling services to use resolver → gateway pattern (pass `ResolvedModelConfig` instead of `model_override`)
- [ ] 11.3 Add `ConfigurationError` handling in services — return user-friendly error when no provider configured

## 12. Tests: Core Unit Tests

- [ ] 12.1 Test `IntentCategory` mapping — every `LLMIntent` maps to exactly one category
- [ ] 12.2 Test `ModelRoutingResolver` cascade: all 5 priority levels, missing config raises error
- [ ] 12.3 Test Pydantic override schemas: valid/invalid `max_tokens`, `temperature`, provider references
- [ ] 12.4 Test provider factory credential pass-through: explicit key used, env var fallback
- [ ] 12.5 Test `ResolvedModelConfig` creation and immutability

## 13. Tests: Backend Unit Tests

- [ ] 13.1 Test `UserProvidersService`: CRUD, credential validation, encryption/masking, cannot-deactivate-last-provider
- [ ] 13.2 Test `UserAiSettingsService`: default model, category/intent overrides, provider validation, token limits
- [ ] 13.3 Test `ProjectAiSettingsService`: project overrides cascade over user, source metadata
- [ ] 13.4 Test encryption helper: round-trip, missing key raises at startup
- [ ] 13.5 Test schemas: all request/response validation, edge cases

## 14. Tests: Integration Tests

- [ ] 14.1 Test provider CRUD API endpoints: create, list (masked), update, delete
- [ ] 14.2 Test AI settings API: set default model, set overrides, get effective settings with source
- [ ] 14.3 Test project settings API: project-level overrides cascade correctly
- [ ] 14.4 Test gateway integration: end-to-end intent → resolver → gateway → mock provider
- [ ] 14.5 Test migration: existing project_settings data migrates correctly

## 15. Frontend: Provider Management UI

- [ ] 15.1 Create Settings → AI Providers page: list active providers, add/edit/delete
- [ ] 15.2 Provider form: select from supported providers, enter API key, optional base URL, validate button
- [ ] 15.3 API key display: show last 4 chars + "Change" button, never full key

## 16. Frontend: Model Routing UI

- [ ] 16.1 Create Settings → AI Model page: default model selector (provider dropdown + model dropdown)
- [ ] 16.2 Category-level override UI: 7 categories with optional model override each
- [ ] 16.3 "Advanced" toggle to show intent-level overrides within each category
- [ ] 16.4 Model dropdown fetches models from selected provider via `ProviderService.list_models()`

## 17. Frontend: Token Limits UI

- [ ] 17.1 Profile selector: quick / balanced / long_texts / custom radio buttons
- [ ] 17.2 When "custom": show per-category max_tokens/temperature inputs
- [ ] 17.3 Validation: max_tokens >= 1, temperature 0.0–2.0, warn if exceeds known context window

## 18. Frontend: Project-Level Settings

- [ ] 18.1 Add AI tab to project settings: same category/intent override UI scoped to project
- [ ] 18.2 Show effective settings with source indicators ("from project", "from user", "default")

## 19. Documentation & Cleanup

- [ ] 19.1 Update ADR for LLM Gateway (ADR-001) to reflect runtime config resolution
- [ ] 19.2 Resolve Q-006 (Configurable Model Routing) with decision summary
- [ ] 19.3 Update feature specs SET-001, SET-002, SET-003 with actual content
- [ ] 19.4 Update `CURRENT_STATE.md` and `docs/reference/directory-structure.md`
- [ ] 19.5 Add `NARRARE_ENCRYPTION_KEY` to deployment docs and `.devcontainer/` env setup
- [ ] 19.6 Update `_scratch/` settings schemas or remove if fully replaced
