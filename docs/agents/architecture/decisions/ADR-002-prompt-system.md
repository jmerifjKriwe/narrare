# ADR-002 — Unified Prompt System

> **Status:** ✅ Accepted
> **Date:** project-init
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

The previous codebase had three competing prompt cascade implementations:
- `PromptManagementService` (Core) — used by the UI
- `KBPromptResolver` (API) — used by KB features
- `WritingPromptResolver` (API) — used by writing features

Each resolved overrides from different directory structures. A user-saved
override via the UI did not reliably reach the runtime resolver for the
same feature. The `OptimizedPromptBuilder` cache had a key mismatch bug
(get-key ≠ set-key) meaning it never hit. 34 of 55 LLM call sites built
prompts via f-strings outside any resolver.

## Decision Drivers

- User overrides must reliably affect runtime behavior
- One cascade implementation reduces bugs and maintenance
- Prompt building must be testable and auditable
- All clients (WebUI, MCP, A2A, CLI) must use the same prompts

## Options Considered

### Option A — Unified registry in `core/prompts/` (chosen)
Single `PromptRegistry` with one cascade algorithm.
`PromptComposer` assembles final prompts. All features use these.

### Option B — Standardize the three existing resolvers
Align path conventions, keep separate implementations.
**Rejected:** Three implementations always risk diverging again.
  The root cause is the existence of three, not their divergence.

## Decision

**We choose Option A.**

One cascade. One composer. One place where prompts are built.
Enforced by RULE-02 in `CONSTRAINTS.md`.

## Consequences

**Positive:**
- User overrides work consistently across all features
- Cache can be implemented correctly once
- Prompt building is auditable — every prompt goes through one code path

**Negative / Tradeoffs:**
- Migration effort: all three old resolvers must be replaced
- `PromptContext` dataclass must carry all variables any feature might need

**Constraints introduced:**
- RULE-02 in `CONSTRAINTS.md`

## Implementation Notes

`core/prompts/registry.py` — single cascade resolver.
`core/prompts/composer.py` — assembles final prompt from registry output + context.
`core/prompts/context.py` — `PromptContext` carries all variables.
Cache key: `f"{category}/{language}/{mode}:{hash(variables)}"` — one consistent strategy.

## Review Trigger

- [ ] When a new feature category requires cascade behavior not supported by registry
