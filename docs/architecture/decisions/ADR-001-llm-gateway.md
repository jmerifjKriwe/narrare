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
