# ADR-001 — Single LLM Gateway for all model calls

> **Status:** ✅ Accepted
> **Date:** project-init
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

The previous Narrare codebase had 55+ LLM call sites across 20+ files.
Of these, 34 built prompts locally via f-strings and 2 bypassed the wrapper
entirely with direct `openai.AsyncOpenAI()` calls. This meant retry logic,
cost tracking, model selection, and error classification were applied
inconsistently — or not at all.

Any future client (MCP, A2A, CLI) would need its own LLM integration
unless a single gateway existed.

## Decision Drivers

- Cost tracking requires a single measurement point
- Retry and error classification must be consistent across all features
- Model selection (which model for which intent) must be changeable without
  touching feature code
- MCP and A2A clients must be able to use the same logic as WebUI

## Options Considered

### Option A — Central Gateway (chosen)
One class in `core/llm/gateway.py`. All LLM calls go through it.
Enforced via AST check in CI.

**Pros:** Single point for policy, metrics, retry, model routing.
**Cons:** Slightly more indirection for simple cases.

### Option B — Wrapper convention (status quo)
`run_agent()` and `stream_agent()` wrappers exist but are optional.
**Pros:** Less architectural change.
**Cons:** Does not prevent bypasses. Already proven to fail (2 direct bypasses existed).

## Decision

**We choose Option A.**

A wrapper that can be bypassed is not a gateway. The gateway must be the
only path to any LLM API, enforced by tooling — not by convention.

## Consequences

**Positive:**
- Consistent retry, error handling, and telemetry for all features
- Model routing is a config change, not a code change
- MCP/A2A can reuse the same gateway

**Negative / Tradeoffs:**
- Every LLM call requires `LLMGateway` to be injected — slightly more setup
- Simple one-off LLM calls (e.g., a health check) require going through the gateway

**Constraints introduced:**
- RULE-01 in `CONSTRAINTS.md`

## Implementation Notes

Gateway lives at `core/llm/gateway.py`.
Providers are adapters in `core/llm/_providers/`.
`LLMIntent` enum in `core/llm/intents.py` drives model selection.
Approved exceptions use `# narrare: allow-direct-llm reason="..."` inline comment.

## Review Trigger

- [ ] When pydantic-ai releases a major version with breaking changes
- [ ] When a new provider requires fundamentally different calling convention

---

## Update: Runtime Model Routing (2026-05-14)

This ADR is updated to reflect the replacement of hardcoded model routing with a runtime configuration cascade. The gateway's core responsibility (single entry point for all LLM calls) is unchanged, but how model selection works has been fundamentally redesigned.

### What changed

1. **Gateway receives `ResolvedModelConfig` from external callers.** The `run()` and `stream()` methods now accept a `ResolvedModelConfig` containing `provider_name`, `model_id`, `temperature`, `max_tokens`, and `streams` — plus explicit `api_key` and `base_url` credentials. The gateway no longer performs any model lookup internally.

2. **`MODEL_ROUTING` dict and `get_model_config()` removed from `intents.py`.** The hardcoded Python dictionary mapping `LLMIntent` values to specific Anthropic models has been removed entirely. There is no runtime fallback to hardcoded defaults.

3. **Provider factories accept explicit `api_key` and `base_url`.** All six provider factories (Anthropic, OpenAI, Google, Groq, OpenRouter, Z.AI, Ollama) now accept optional `api_key` and `base_url` keyword arguments. When provided, these override environment variable defaults. This enables per-user, per-request credentials from the database.

4. **`infer_provider()` demoted to dev-only utility.** The heuristic provider inference function in `registry.py` is no longer called on any runtime path. It remains available for developer tooling and debugging. Provider is always stored explicitly alongside the model ID — critical for OpenRouter and multi-provider scenarios where model names alone are ambiguous.

5. **New `ModelRoutingResolver` protocol resolves config via cascade.** A resolver in `core/llm/model_routing.py` implements the following priority chain:
   ```
   Project-level intent override → Project-level category override
       → User-level intent override → User-level category override
       → User's default model
       → ConfigurationError("No AI provider configured")
   ```
   No hardcoded fallback. If a user has no provider configured, the system returns a clear error directing them to Settings.

6. **Intent categories provide manageable override granularity.** The 20 `LLMIntent` values are grouped into 7 categories:
   | Category | Intents |
   |----------|---------|
   | writing | WRITE, EXTEND, REWRITE, CO_AUTHOR |
   | analysis | ANALYSE, SENTIMENT, CONSISTENCY, BETA_READ, VOICE |
   | kb | KB_CREATE, KB_IMPROVE, KB_EXTRACT |
   | planning | PLAN, SUMMARIZE |
   | extraction | EXTRACT, SUGGEST |
   | chat | CHAT |
   | research | RESEARCH |

   Users configure defaults per category in the UI. Intent-level overrides are available via an "Advanced" toggle for power users.

### New infrastructure

- **`user_providers` table** — encrypted API keys, base URLs, activation status per user
- **`user_ai_settings` table** — default model, category/intent overrides, token limit profiles
- **JSONB columns on `project_settings`** — project-level category/intent/token overrides
- **`core/shared/crypto.py`** — Fernet encryption for API keys at rest (`NARRARE_ENCRYPTION_KEY` env var)
- **Settings service layer** — contracts, repositories, and services for provider management, AI settings, and model routing resolution (RULE-03 compliant)

### Impact on ADR-001 consequences

The positive consequences of ADR-001 are strengthened:
- Model routing is now a runtime config change (no code change, no redeploy) — the original ADR promise is fully realized
- MCP/A2A can reuse the same gateway with per-user credentials

The negative tradeoff is slightly expanded:
- Every LLM call now requires `ResolvedModelConfig` + credentials to be resolved by the caller
- New infrastructure dependency: `NARRARE_ENCRYPTION_KEY` env var (loss = unrecoverable API keys)

### Reference

- OpenSpec change: `openspec/changes/configurable-model-routing/`
- Design decisions: D1–D8 in `design.md`
- Feature specs: SET-001 (User Settings), SET-002 (Project Settings), SET-003 (Model Configuration)
