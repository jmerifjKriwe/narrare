---
id: INFRA-001
title: "LLM Gateway"
status: maintained
area: infra
mvp: true

ui_tooltip: "Unified interface to all AI providers with automatic retries and error handling."
ui_help_short: |
  Narrare's central AI gateway handles all communication with AI providers like
  Anthropic, OpenAI, and Google. It automatically retries failed requests,
  tracks costs, and routes different tasks to the most appropriate models.
ui_help_long: |
  ## LLM Gateway

  The LLM Gateway is the single entry point for all AI operations in Narrare.
  You don't need to configure API keys in individual features — the gateway
  manages everything centrally.

  **What it handles:**
  - Provider selection (Anthropic, OpenAI, Google, Groq, Ollama, OpenRouter, Z.AI)
  - Automatic retries with exponential backoff
  - Cost tracking and token usage
  - Error classification and helpful error messages
  - Intent-based model routing (different tasks use different models)

  **Model routing:**
  Writing tasks use Claude Sonnet, while quick operations like consistency checks
  might use Haiku. The gateway automatically routes each task to the right model.

  **When things go wrong:**
  - Rate limits: Waits and retries automatically
  - Invalid API keys: Clear error message pointing to Settings
  - Network issues: Retries up to 3 times
  - Context too large: Suggests reducing your scope

  The gateway is configured in Settings → AI Provider. All features use it
  automatically — no setup needed per feature.
ui_available_in: [settings]

service: core/llm/gateway.py
contract: ~
router: ~
prompt: ~
requires: []
---

# INFRA-001 — LLM Gateway

## What it does

Central gateway for all LLM calls that handles provider selection, automatic retries,
cost tracking, and intent-based model routing. Every AI feature in Narrare goes through
this single interface.

## Why it exists

Without a central gateway, every feature would need its own provider integration,
retry logic, and error handling. This creates duplication, inconsistent behavior,
and makes it hard to add new providers. The gateway provides a single, well-tested
interface that all features can rely on.

## How it works (User perspective)

1. You configure your AI provider once in Settings (API key, model preferences)
2. Every AI feature automatically uses the gateway
3. If a request fails, the gateway retries automatically
4. Your token usage and costs are tracked centrally
5. You can switch providers anytime without reconfiguring individual features

## How it works (Technical)

**Entry point:** `core/llm/gateway.py`
**Primary class:** `ModelRegistry` (v2, seit ADR-015); `LLMGateway` als Legacy-Re-Export (Phase-2-Removal-Target)
**Providers:** `core/llm/_providers/` — one adapter per provider
**Intents:** `core/llm/intents.py` — defines task types and model routing
**Errors:** `shared/errors.py` — classified error types (auth, rate limit, timeout, etc.)

**Flow:**
1. Service calls `gateway.run(intent=LLMIntent.WRITE, ...)`
2. Gateway resolves model from intent's routing config
3. Provider factory creates pydantic-ai Model instance
4. Agent created with system prompt
5. Call wrapped in retry logic with exponential backoff
6. Success/failure recorded in metrics
7. `LLMResult` returned with text and token usage

**Streaming:** `gateway.stream()` returns async iterator of `StreamChunk` objects.

**Retry logic:** Configurable `RetryConfig` — defaults to 3 attempts with exponential
backoff. Only retries transient failures (rate limits, network errors).

**Usage Limits:** `ModelRegistry.get_model()` accepts an optional `UsageLimits`
parameter to enforce token budgets per request. Three profiles are available:
`conservative` (32K tokens), `balanced` (64K tokens), and `unlimited`.

**Observability:** `NarrareObservability` is a pydantic-ai capability that hooks
into every model request to track tokens, duration, and errors. It is automatically
injected into all `NarrareAgent` instances and replaces the manual
`record_success`/`record_failure` pattern (ADR-015 Phase 1).

## Constraints & Edge Cases

- Maximum retry attempts: 3 (configurable)
- Context size limits vary by model — gateway throws `LLMContextTooLargeError`
- Provider API keys must be valid — gateway throws `LLMAuthError` immediately
- Streaming responses cannot be retried mid-stream
- Token counts are provider-specific (may not be 100% accurate across providers)

## Related Features

- [INFRA-002](INFRA-002-prompt-system.md) — Prompt System works with gateway
- [INFRA-004](INFRA-004-embedding-store.md) — Embeddings use same provider infrastructure
- [SET-001](../setup/SETUP-001-setup-wizard.md) — Setup Wizard configures gateway

## Status & History

- `project-init` — Implemented as core infrastructure
- `2025-01-09` — Stable, fully implemented with all providers
- `2026-05-20` — Maintained (ADR-015 Phase 1): `ModelRegistry` ersetzt `LLMGateway` als primären Entry-Point; `LLMGateway` bleibt als Legacy-Re-Export erhalten. `UsageLimits`-Parameter und `NarrareObservability`-Hook-Capability hinzugefügt.
