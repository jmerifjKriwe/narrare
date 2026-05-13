## 1. Dependencies & Configuration

- [ ] 1.1 Add `mem0ai` dependency to `packages/core/pyproject.toml` (with extras: pgvector support)
- [ ] 1.2 Verify `psycopg2-binary` or `psycopg` is available for mem0 pgvector backend
- [ ] 1.3 Add mem0 RULE-01 exception documentation to `docs/_shared/CONSTRAINTS.md`
- [ ] 1.4 Update `docs/_shared/TECH_STACK.md` mem0 section with configuration details (AsyncMemory, pgvector, configurable LLM provider)

## 2. Generation Intents (Core)

- [ ] 2.1 Add `GENERATE`, `NAME_GENERATE`, `TITLE_GENERATE` to `LLMIntent` enum in `core/llm/intents.py`
- [ ] 2.2 Add `ModelConfig` entries in `MODEL_ROUTING` for each new intent (NAME_GENERATE: haiku-grade, low temp; TITLE_GENERATE: creative, short; GENERATE: balanced defaults)
- [ ] 2.3 Add generation category mapping in `PromptComposer._INTENT_TO_CATEGORY` (all three intents → `"generation"`)
- [ ] 2.4 Add generation mode mapping in `PromptComposer._INTENT_TO_MODE` (GENERATE → `"general"`, NAME_GENERATE → `"names"`, TITLE_GENERATE → `"titles"`)
- [ ] 2.5 Write unit tests for new intents, routing, and category/mode mapping

## 3. PromptContext Extension

- [ ] 3.1 Add `user_preferences: str`, `avoidance_patterns: str`, `style_constraints: str` fields to `PromptContext` dataclass
- [ ] 3.2 Verify `as_variables()` includes new fields in output
- [ ] 3.3 Write unit tests for new fields in variable output

## 4. Memory Layer — Core Protocols & Models

- [ ] 4.1 Create `core/memory/protocols.py` with `FeedbackCollector`, `PreferenceProvider`, and `MemoryFacade` Protocol classes
- [ ] 4.2 Create `core/memory/models.py` with `FeedbackAction` enum, `FeedbackEvent` (frozen dataclass), and `PreferenceProfile` (with `to_prompt_text()` method)
- [ ] 4.3 Write unit tests for `PreferenceProfile.to_prompt_text()` (empty profile, non-empty profile, constraints formatting)

## 5. Memory Layer — mem0 Client

- [ ] 5.1 Create `core/memory/mem0_client.py` with `create_memory_client()` factory function (pgvector config, LLM from user settings, default model per provider, custom instructions)
- [ ] 5.2 Implement `_default_memory_model()` helper with provider-specific defaults
- [ ] 5.3 Implement `NullMemoryClient` class (no-op add, search, get_all, delete, delete_all with warning logs)
- [ ] 5.4 Write unit tests for `NullMemoryClient` (all methods return empty results without error)
- [ ] 5.5 Write unit tests for `_default_memory_model()` (returns correct model per provider)

## 6. Memory Layer — Core Services

- [ ] 6.1 Implement `core/memory/feedback_service.py` — `FeedbackService` with `record()` (persist to DB + forward to mem0) and `get_history()`
- [ ] 6.2 Implement `core/memory/preference_service.py` — `PreferenceService` with `get_preferences()` (query mem0 + aggregate to PreferenceProfile) and `reset()`
- [ ] 6.3 Update `core/memory/__init__.py` with public exports
- [ ] 6.4 Write unit tests for `FeedbackService.record()` (with mock mem0 client, verify DB persist + mem0 forward)
- [ ] 6.5 Write unit tests for `PreferenceService.get_preferences()` (with mock mem0, verify aggregation)
- [ ] 6.6 Write unit tests for `FeedbackService.record()` when mem0 unavailable (NullMemoryClient, verify DB persist still works)

## 7. PromptComposer — Culture & Preference Injection

- [ ] 7.1 Extend `PromptComposer` to accept optional `PreferenceService` in constructor
- [ ] 7.2 Implement automatic preference injection in `build()` — if PreferenceService configured and context.user_preferences is empty, resolve preferences
- [ ] 7.3 Implement culture definition resolution in `PromptRegistry` — new method to resolve culture files from `_bundled/{category}/cultures/{language}/{culture_id}.md` with EN fallback
- [ ] 7.4 Implement culture injection in `PromptComposer.build()` — if `context.extra["culture"]` is set and prompt contains `{{culture_guidelines}}`, resolve and inject
- [ ] 7.5 Write unit tests for preference injection (with mock PreferenceService, verify context populated)
- [ ] 7.6 Write unit tests for culture injection (with test culture files, verify placeholder replaced)
- [ ] 7.7 Write unit tests for culture fallback (missing language → EN, missing culture → empty string + warning)

## 8. Bundled Generation Prompts & Culture Definitions

- [ ] 8.1 Create directory structure: `_bundled/generation/{en,de,fr}/names/system.md`
- [ ] 8.2 Create English base name generation prompt (`_bundled/generation/en/names/system.md`) with frontmatter and `{{culture_guidelines}}` placeholder
- [ ] 8.3 Create German base name generation prompt (`_bundled/generation/de/names/system.md`)
- [ ] 8.4 Create French base name generation prompt (`_bundled/generation/fr/names/system.md`)
- [ ] 8.5 Create culture definition directories: `_bundled/generation/cultures/{en,de,fr}/`
- [ ] 8.6 Create fantasy culture definitions for all three languages (port from `_scratch/prompts/names/*/fantasy/system.md`, adapt format)
- [ ] 8.7 Create modern culture definitions for all three languages
- [ ] 8.8 Create scifi culture definitions for all three languages
- [ ] 8.9 Verify all prompt files have valid YAML frontmatter (prompt_type, prompt_language, prompt_version)

## 9. Prompt Management Service — Core

- [ ] 9.1 Port `PromptManagementService` from `_scratch/packages/core/narrare_core/prompts/service.py` to `core/prompts/management.py` — adapt to current code style, typing, and registry API
- [ ] 9.2 Port `variable_metadata.py` from `_scratch` to `core/prompts/variable_metadata.py`
- [ ] 9.3 Implement update detection logic — compare `override_of_version` in override frontmatter with current bundled version
- [ ] 9.4 Implement diff generation — return override content and current bundled content for UI comparison
- [ ] 9.5 Write unit tests for `PromptManagementService` — list, get, save, reset, cascade_info
- [ ] 9.6 Write unit tests for update detection — new bundled version detected, same version not flagged
- [ ] 9.7 Write unit tests for diff generation — override vs bundled content comparison

## 10. Memory Layer — API

- [ ] 10.1 Create `apps/api/narrare/memory/` module structure (contracts.py, models.py, schemas.py, repository.py, service.py, router.py)
- [ ] 10.2 Define `FeedbackServiceProtocol` and `PreferenceServiceProtocol` in `memory/contracts.py`
- [ ] 10.3 Define SQLAlchemy model for `feedback_events` table in `memory/models.py`
- [ ] 10.4 Define Pydantic schemas in `memory/schemas.py` (FeedbackRequest, FeedbackResponse, PreferenceResponse, ResetResponse)
- [ ] 10.5 Implement `memory/repository.py` — database operations for feedback_events
- [ ] 10.6 Implement `memory/service.py` — API service layer wrapping core FeedbackService and PreferenceService
- [ ] 10.7 Implement `memory/router.py` — POST /feedback, GET /preferences, DELETE /preferences
- [ ] 10.8 Register memory router in app dependencies
- [ ] 10.9 Create Alembic migration for `feedback_events` table
- [ ] 10.10 Write integration tests for memory API endpoints

## 11. Prompt Management — API

- [ ] 11.1 Create `apps/api/narrare/prompts/` module structure (contracts.py, schemas.py, service.py, router.py)
- [ ] 11.2 Define `PromptManagementProtocol` in `prompts/contracts.py`
- [ ] 11.3 Port schemas from `_scratch/prompts/schemas.py` to `prompts/schemas.py` (adapt to current Pydantic v2 patterns)
- [ ] 11.4 Implement `prompts/service.py` — wraps core PromptManagementService for API layer
- [ ] 11.5 Implement `prompts/router.py` — GET /prompts, GET /prompts/{id}, PUT /prompts/{id}, DELETE /prompts/{id}/override, GET /prompts/{id}/cascade, GET /prompts/updates, GET /prompts/{id}/diff
- [ ] 11.6 Register prompts router in app dependencies
- [ ] 11.7 Write integration tests for prompts API endpoints

## 12. Name Generator — API

- [ ] 12.1 Create `apps/api/narrare/generation/` module structure (contracts.py, schemas.py, name_service.py, router.py)
- [ ] 12.2 Define `NameGeneratorProtocol` in `generation/contracts.py`
- [ ] 12.3 Define Pydantic schemas in `generation/schemas.py` (NameGenerateRequest, GeneratedName, NameGenerateResponse, NameType enum, GenderEnum)
- [ ] 12.4 Implement `generation/name_service.py` — uses PromptComposer with NAME_GENERATE intent, culture injection, and KB dedup check
- [ ] 12.5 Implement `generation/router.py` — POST /generation/names
- [ ] 12.6 Register generation router in app dependencies
- [ ] 12.7 Write integration tests for name generation API endpoint

## 13. Frontend — Prompt Override UI

- [ ] 13.1 Create "AI Prompts" tab in Settings area with prompt list component (category grouping, source indicator, update badge)
- [ ] 13.2 Implement prompt editor component (view content, edit as override, save, reset)
- [ ] 13.3 Implement diff comparison view (side-by-side, keep/accept/merge actions)
- [ ] 13.4 Implement update notification badge (polling or on-load detection)
- [ ] 13.5 Add API client functions for prompts endpoints (list, get, save, reset, cascade, updates, diff)
- [ ] 13.6 Write frontend tests for prompt settings components

## 14. Frontend — Name Generator UI

- [ ] 14.1 Create name generator modal/panel component (type selector, culture selector, count/gender options, generate button)
- [ ] 14.2 Implement results display (name list with pronunciation, meaning, duplicate status)
- [ ] 14.3 Add "save to KB" action on generated names
- [ ] 14.4 Add API client functions for generation endpoints
- [ ] 14.5 Write frontend tests for name generator component

## 15. Documentation Updates

- [ ] 15.1 Update `docs/features/infra/INFRA-002-prompt-system.md` — status → in-progress, add culture injection and prompt management details
- [ ] 15.2 Update `docs/features/infra/INFRA-005-memory-layer.md` — status → in-progress, add mem0 AsyncMemory integration details, provider configuration
- [ ] 15.3 Complete `docs/features/prompts/PROMPT-001-file-overrides.md` — fill all sections with implementation details
- [ ] 15.4 Complete `docs/features/prompts/PROMPT-002-db-templates.md` — fill all sections with implementation details
- [ ] 15.5 Update `docs/features/generation/GEN-001-name-generator.md` — status → in-progress, update technical section with intent, culture, and service details
- [ ] 15.6 Update `docs/_shared/CURRENT_STATE.md` — reflect new modules, dependencies, and feature statuses

## 16. Validation & Architecture Check

- [ ] 16.1 Run `just check` (architecture validation) — verify no RULE violations
- [ ] 16.2 Run full test suite (`just test`) — all unit + integration tests pass
- [ ] 16.3 Run `pyright` — no type errors in new code
- [ ] 16.4 Verify mem0 graceful degradation — system starts and functions with mem0 unavailable
- [ ] 16.5 Verify prompt cascade works end-to-end — bundled → project override → DB template resolution
