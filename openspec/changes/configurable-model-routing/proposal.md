## Why

Narrare's LLM model routing is hardcoded in `core/llm/intents.py` — a Python dictionary mapping ~20 intents to specific models (all Anthropic). Changing the model for any function requires a code change and redeploy. Users who configured a provider during setup (e.g., OpenRouter, OpenAI, local Ollama) cannot use their chosen provider for AI features. The settings module violates RULE-03 (no contracts) and lacks a service layer entirely. As AI-assisted features grow, users need control over which model/provider combination serves each function, with configurable token limits per category.

## What Changes

- **Replace hardcoded `MODEL_ROUTING`** with a runtime configuration cascade: project-level → user-level → user default → error (no provider configured). Remove the hardcoded defaults entirely — they assumed universal Anthropic access which is false.
- **Add multi-provider support per user**: users can configure multiple AI providers (OpenAI, Anthropic, OpenRouter, Ollama, Z.AI, etc.) with API keys and base URLs. Provider is stored explicitly — not inferred from model names (OpenRouter models like `anthropic/claude-sonnet-4-5` cannot be mapped by heuristic).
- **Add model routing with category/intent granularity**: users choose a default model (from their configured providers), then optionally override per category (writing, analysis, kb, planning) or per individual intent (write, extend, rewrite, etc.).
- **Add configurable token limits**: per-category and per-intent overrides for `max_tokens`, `temperature`, and other generation parameters — with named profiles ("quick", "balanced", "long_texts", "custom").
- **Fix settings module**: add contracts (RULE-03), service layer, and proper AI-specific settings tables for both user-level and project-level configuration.
- **Update gateway** to accept runtime model config instead of hardcoded routing.

## Capabilities

### New Capabilities

- `provider-management`: Multi-provider configuration per user (CRUD for provider entries: name, API key, base URL, activation status). Part of user settings.
- `model-routing-cascade`: Runtime model resolution with configuration cascade (project override → user override → user default → error). Replaces hardcoded `MODEL_ROUTING`.
- `token-limit-profiles`: Named token limit profiles with per-category/per-intent overrides. Profiles: quick, balanced, long_texts, custom.

### Modified Capabilities

- `settings-service`: Add contracts (RULE-03 compliance), service layer, AI-specific settings tables (`user_providers`, `user_ai_settings`, project-level AI settings). Currently has no contracts, no service, no AI settings support.

## Impact

- **Core** (`packages/core/narrare_core/llm/`): `intents.py` loses `MODEL_ROUTING` dict and `get_model_config()` — replaced by a runtime resolver. `gateway.py` gains ability to receive `ModelConfig` from external configuration instead of hardcoded lookup. `_providers/registry.py`'s `infer_provider()` becomes dev-only utility, not runtime dependency.
- **Backend** (`apps/api/narrare/settings/`): New contracts, service, schemas, and repository for AI settings. New `user_providers` table migration. Modified `user_settings` and `project_settings` tables.
- **Frontend** (`packages/web/`): New settings UI for provider management, model selection per category/intent, token limit configuration. Complex UI challenge — category-level defaults with optional intent-level drill-down.
- **Database**: Migration with 2 new tables (`user_providers`, `user_ai_settings`), modifications to existing settings tables.
- **Setup Wizard**: Already captures provider/model during setup — this becomes the foundation of the user's AI configuration.
- **Tests**: Significant new test coverage needed for cascade resolution, provider management, token limit profiles, and gateway integration.
