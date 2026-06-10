---
id: SET-001
title: "User Settings"
status: implemented
area: settings
mvp: true

ui_tooltip: "Manage your AI providers, models, and writing preferences."
ui_help_short: |
  Configure your AI providers and default model, set per-category model
  overrides for writing, analysis, and more, and choose token limit profiles
  to control response length and cost.
ui_help_long: |
  User Settings is where you connect Narrare to your AI providers. Add one or
  more providers (OpenAI, Anthropic, OpenRouter, Ollama, etc.) with your API
  keys, then choose which model to use as your default.

  You can go further and assign different models to different categories of
  work — use Claude for writing, GPT-4o for analysis, and a local model for
  quick suggestions. Token limit profiles (quick, balanced, long_texts) let
  you control how verbose the AI responses are.

  API keys are encrypted on the server and never exposed in the browser. You
  can add, update, or remove providers at any time.
ui_available_in: [settings]

service: settings/user_service.py
contract: settings/contracts.py#UserSettingsRepositoryProtocol
router: settings/router.py
prompt: ~
requires: [INFRA-001]
---

# SET-001 — User Settings

> **Status:** ✅ Implemented
> **Last updated:** 2026-05-14

## What it does

User Settings lets writers configure their AI providers, choose default and per-category models, and manage token limit profiles. It is the central place where the AI integration meets the user's preferences.

## Why it exists

Narrare's AI features are useless without a configured provider. Writers need to control which models they use, how much they spend, and how the AI behaves for different types of work. Without user-level settings, every writer would be stuck with whatever the server admin configured — which defeats the purpose of a personal writing tool.

## How it works (User perspective)

1. The writer opens **Settings** and navigates to **AI Providers**
2. They add a provider (e.g., OpenRouter) with their API key
3. They set a **default model** (e.g., `anthropic/claude-sonnet-4-5` via OpenRouter)
4. Optionally, they go to **AI Model & Routing** and override models per category:
   - Writing → use Claude for creative quality
   - Analysis → use GPT-4o for structured reasoning
   - KB → use a fast model for extraction tasks
5. Optionally, they choose a **token limit profile** (quick, balanced, long_texts, custom)
6. All AI features now use their configured models and limits

## How it works (Technical)

**Entry point:** `settings/router.py` → `/settings/ai/providers`, `/settings/ai`
**Services:**
- `UserProvidersService` — CRUD for provider entries, credential validation, encryption
- `UserAiSettingsService` — default model, category/intent overrides, token limit profiles
**Contracts:** `UserProvidersRepositoryProtocol`, `UserAiSettingsRepositoryProtocol` in `settings/contracts.py`
**Encryption:** `core/shared/crypto.py` — Fernet symmetric encryption via `NARRARE_ENCRYPTION_KEY`
**Database:** `user_providers` table (encrypted keys), `user_ai_settings` table (JSONB overrides)
**REST API:**
- `GET/POST /settings/ai/providers` — list/add providers
- `PATCH/DELETE /settings/ai/providers/{id}` — update/remove provider
- `GET/PATCH /settings/ai` — user AI settings (default model, overrides, token limits)

## Constraints & Edge Cases

- API keys are encrypted at rest — if `NARRARE_ENCRYPTION_KEY` is lost, all user API keys are unrecoverable
- Cannot deactivate or delete the only active provider — must add another first
- Deleting a provider that is the default clears the default model; AI features return `ConfigurationError` until a new default is set
- Provider credential validation makes a test call — if it times out (10s), the key is saved with a warning
- API keys are never returned via REST API — response includes `has_api_key: true` and last 4 characters only

## Related Features

- [SET-002](SET-002-project-settings.md) — Project-level overrides cascade over user settings
- [SET-003](SET-003-model-config.md) — The model routing cascade that uses these settings
- [SETUP-004](../setup/SETUP-004-provider-config.md) — Setup wizard seeds initial provider during onboarding
- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — The gateway that receives resolved config

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-14` — Updated: multi-provider support, AI settings, contracts (RULE-03), service layer, token limits
