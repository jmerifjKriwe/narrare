# ADR-035 — Agent Output Validation Policy

> **Status:** ✅ Accepted
> **Date:** 2026-06-04
> **Deciders:** User, Architecture Agent
> **Supersedes:** —
> **Related:** ADR-015, ADR-026, ADR-027, ADR-032, ADR-034

---

## Context

Pydantic AI supports output validators. Narrare already relies on structured agent behavior for preferences, KB extraction, rewrite decisions, consistency/timeline analysis, and prompt safety. Without a policy, validators may be added inconsistently or used to compensate for bad prompts.

Root cause chain:

1. **Symptom:** Output validation candidates are known, but no architecture defines what belongs in validators versus prompts, services, schemas, or evals.
2. **Why:** Structured output validation is a cross-cutting agent concern.
3. **Why:** Existing rules cover prompt construction and typed schemas, but not semantic validation placement.
4. **Design:** Define a policy: validators enforce deterministic output invariants at the agent boundary; they do not replace prompt quality, service validation, or evals.

---

## Decision Drivers

- Keep prompt instructions, output schemas, validators, service validation, and evals distinct.
- Prevent silent malformed AI outputs.
- Support Pydantic Evals with validator-aware cases.
- Preserve deterministic failure semantics.
- Avoid validators that make hidden LLM calls or mutate business state.

---

## Options Considered

### Option A — Systematic output validation policy (chosen)

Define where validators are required, allowed, and forbidden.

**Pros:**
- Consistent safety layer across agents.
- Clear separation of concerns.
- Testable and eval-friendly.

**Cons:**
- Requires auditing agents and defining validator contracts.

### Option B — Add validators opportunistically per agent

Let implementation teams add validators only where they see failures.

**Pros:**
- Flexible and quick.

**Cons:**
- Inconsistent coverage.
- Encourages symptom patches.
- Hard to reason about failure semantics.

### Option C — Rely only on Pydantic output models

Use schema parsing and no semantic validators.

**Pros:**
- Simple.

**Cons:**
- Catches shape errors but not semantic violations.
- Cannot enforce domain rules like "rewrite selection must reference valid candidate ids".

### Option D — Move semantic checks into services only

Let services repair/reject outputs after the agent returns.

**Pros:**
- Keeps agent code smaller.

**Cons:**
- Pushes AI-boundary concerns into business services.
- Makes retries/repair loops harder to structure.

---

## Decision

**We choose Option A: systematic output validation policy.**

Validator placement rules:

- **Required in Pydantic-AI output validators:** deterministic invariants of an agent's structured output that can be checked using output, deps, and runtime context.
- **Allowed in services:** business authorization, persistence constraints, cross-aggregate rules, and DB-backed checks.
- **Required in schemas:** shape/type constraints for API/service boundaries.
- **Required in evals:** qualitative or probabilistic judgments, rubric scoring, and regression detection.
- **Forbidden in validators:** hidden LLM calls, DB writes, prompt assembly, provider selection, and broad business workflows.

Initial validator candidates:

- PreferenceAnalysisAgent: preference category, confidence bounds, evidence references, metadata completeness.
- KB Extraction: entity type validity, source-span references, duplicate/conflict markers.
- Rewrite: candidate id validity, no empty rewrite, preservation constraints declared by deps.
- Consistency/Timeline: reference integrity, timestamp/order constraints, severity bounds.

Forbidden steady states:

- Validators used as a workaround for underspecified prompts.
- Services silently accepting invalid agent outputs and repairing them without trace/error semantics.
- Validators with side effects beyond validation/retry guidance.

---

## Rationale

Structured outputs reduce ambiguity, but schemas alone cannot encode all domain invariants. Output validators belong at the agent boundary because they can reject or guide retries before invalid data enters services. This keeps business services cleaner while preserving explicit domain validation where it belongs.

The policy prevents a common anti-pattern: using validators as hidden business logic or prompt repair hacks.

---

## Consequences

**Positive:**
- More reliable AI outputs before service consumption.
- Clear failure semantics for malformed outputs.
- Better eval coverage for validator behavior.

**Negative / Tradeoffs:**
- More agent contracts and tests are required.
- Some invariants must be carefully classified between validator and service.

**Constraints introduced:**
- New structured-output agents must declare their validation policy in the spec.
- Validator failures must be observable via OTel spans/logs per ADR-031.

---

## Implementation Plan / Migration Plan

1. Define an output validation policy document or contract in the agent architecture before code changes.
2. Audit existing structured-output agents and classify validators as required/allowed/not applicable.
3. Implement validators starting with Preference Analysis, KB Extraction, Rewrite, and Consistency/Timeline.
4. Add deterministic unit tests for validators and Pydantic Evals cases for validator-driven quality gates.
5. Emit validation span attributes/results through OTel instrumentation.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | Validators live in approved agent architecture; no direct provider calls. |
| RULE-02 | ✅ | Validators do not assemble prompt content. |
| RULE-03 | ✅ | Validator contracts/specs precede implementation. |
| RULE-06 | ✅ | Validation remains distinct from service business logic and persistence. |
| RULE-09 | ✅ | Validator functions require complete type signatures. |
| RULE-10 | ✅ | Each validator needs unit coverage and eval coverage where qualitative. |
| RULE-11 | ✅ | Invalid outputs are rejected or converted to typed errors; no silent acceptance. |
| RULE-20 | ✅ | No opportunistic partial validator layer. |

---

## Sustainability Check

- Correct in 3 months: yes; every new structured-output agent can apply the same classification.
- Hard-to-undo coupling: reduced by keeping validation at the agent boundary.
- Simplest correct solution: yes; policy, not ad hoc validators.
- Design intent clear: yes; validators enforce deterministic invariants only.

---

## Review Triggers

- Pydantic AI changes output validator semantics.
- Validators require DB access or LLM calls to decide correctness.
- Eval results show repeated validator-driven retries due to prompt/schema mismatch.
