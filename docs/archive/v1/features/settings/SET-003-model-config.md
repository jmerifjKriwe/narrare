---
id: SET-003
title: "Per-task Model Configuration"
status: implemented
area: settings
mvp: false

ui_tooltip: "Choose which AI model handles each type of task."
ui_help_short: |
  Assign different AI models to different categories of work — writing,
  analysis, knowledge base, planning — with optional per-task overrides
  and configurable token limits.
ui_help_long: |
  Per-task Model Configuration gives you fine-grained control over which AI
  model handles each type of work. Set a default model for everything, then
  override per category (writing, analysis, kb, planning, extraction, chat,
  research) to use the best model for each job.

  For power users, the "Advanced" toggle reveals per-intent overrides — so you
  can use one model for "extend chapter" and a different one for "rewrite
  selection" within the writing category.

  Token limit profiles (quick, balanced, long_texts, custom) control how long
  AI responses can be. Override max_tokens and temperature per category or
  per intent for precise control.

  The configuration cascade ensures project-level settings take precedence
  over user-level, so you can tune AI behavior per novel without affecting
  your global defaults.
ui_available_in: [settings, project-settings]

service: settings/model_routing_resolver.py
contract: settings/contracts.py#UserAiSettingsServiceProtocol
router: settings/router.py
prompt: ~
requires: [SET-001, SET-002, INFRA-001]
---

# SET-003 — Per-task Model Configuration

> **Status:** ✅ Implemented
> **Last updated:** 2026-05-14

## What it does

Per-task Model Configuration replaces Narrare's hardcoded model routing with a runtime configuration cascade. Writers choose which AI model handles each category of work, with optional per-intent overrides and configurable token limits. Settings can be overridden at the project level for genre-specific tuning.

## Why it exists

Previously, the model-to-intent mapping was hardcoded in the `intents` package (`packages/core/narrare_core/llm/intents/__init__.py`, formerly a monolithic intents.py module) — a Python dictionary mapping every intent to specific Anthropic models. Changing the model for any task required a code change and redeploy. Writers who used OpenRouter, Ollama, or any non-Anthropic provider could not use their chosen provider for AI features. This feature puts model selection in the writer's hands.

## How it works (User perspective)

1. The writer opens **Settings → AI Model & Routing**
2. They see their default model (set during setup or in AI Providers)
3. They see 7 category rows: writing, analysis, kb, planning, extraction, chat, research
4. Each category can optionally use a different model from the default
5. An **"Advanced"** toggle reveals individual intents within each category
6. They choose a **token limit profile**: quick, balanced, long_texts, or custom
7. For "custom" profile, they can set per-category max_tokens and temperature
8. In a specific project, **Project Settings → AI** lets them override any of these for that project only

## How it works (Technical)

**Core resolution:** `ModelRoutingResolver` protocol in `packages/core/narrare_core/llm/model_routing.py`
**Cascade priority:**
```
Project-level intent override → Project-level category override
    → User-level intent override → User-level category override
    → User's default model → ConfigurationError
```

**Intent categories (7 categories, 20 intents):**
| Category | Intents |
|----------|---------|
| writing | WRITE, EXTEND, REWRITE, CO_AUTHOR |
| analysis | ANALYSE, SENTIMENT, CONSISTENCY, BETA_READ, VOICE |
| kb | KB_CREATE, KB_IMPROVE, KB_EXTRACT |
| planning | PLAN, SUMMARIZE |
| extraction | EXTRACT, SUGGEST |
| chat | CHAT |
| research | RESEARCH |

**Token limit profiles:**
| Profile | Default max_tokens |
|---------|--------------------|
| quick | 500 |
| balanced | 2000 |
| long_texts | 8000 |
| custom | User-defined per category |

**Key types:**
- `ResolvedModelConfig` (dataclass) — `provider_name`, `model_id`, `temperature`, `max_tokens`, `streams`
- `ResolvedModel` — config + source metadata (which cascade level was used)
- `IntentCategory` enum — the 7 categories
- `INTENT_CATEGORY_MAP` — maps each `LLMIntent` to its category

**Gateway integration:** Services call `ModelRoutingResolver` to get `ResolvedModelConfig` + credentials, then pass them to `gateway.run()` or `gateway.stream()`. The gateway never calls `get_model_config()` or `infer_provider()`.

**REST API:**
- `GET/PATCH /settings/ai` — user AI settings
- `GET/PATCH /settings/ai/novels/{id}` — project AI settings with source metadata

## Constraints & Edge Cases

- No hardcoded fallback — if no provider is configured, AI features return `ConfigurationError` directing the user to Settings
- Provider is always stored explicitly (not inferred from model name) — critical for OpenRouter where model names like `anthropic/claude-sonnet-4-5` are ambiguous
- Token limits are validated: `max_tokens >= 1`, `temperature 0.0–2.0`, warn if `max_tokens` exceeds known model context window
- `infer_provider()` is demoted to dev-only utility and is never called on the runtime path
- Resolution result includes source information (e.g., "user_category", "project_intent") for observability

## Related Features

- [SET-001](SET-001-user-settings.md) — User-level provider and AI settings
- [SET-002](SET-002-project-settings.md) — Project-level overrides
- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — The gateway that receives resolved config

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-14` — Updated to in-progress: runtime cascade implemented, 7 intent categories, token limit profiles, multi-provider support
