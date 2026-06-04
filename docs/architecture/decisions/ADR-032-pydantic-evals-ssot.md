# ADR-032 — Pydantic Evals as Evaluation Single Source of Truth

> **Status:** ✅ Accepted
> **Date:** 2026-06-04
> **Deciders:** User, Architecture Agent
> **Supersedes:** ADR-018
> **Related:** ADR-001, ADR-002, ADR-015, ADR-026, ADR-027, ADR-031

---

## Context

ADR-018 selected promptfoo for prompt quality evals. The AI runtime has since moved decisively toward Pydantic-AI agents, `PromptComposer`, `ModelRegistry`, capabilities, structured outputs, and output validators.

Root cause chain:

1. **Symptom:** Evals risk becoming a separate YAML/provider stack that does not exercise Narrare's real agent runtime.
2. **Why:** promptfoo evaluates prompt/provider matrices well, but Narrare's quality-critical behavior is now inside Python agents, typed deps, tools, output validators, capabilities, and prompt composition.
3. **Why:** Keeping promptfoo would preserve a parallel test universe rather than making runtime architecture itself evaluable.
4. **Design:** Use Pydantic Evals as the Python-native evaluation SSOT and remove promptfoo completely.

---

## Decision Drivers

- Evals must run through Narrare's actual `NarrareAgent`, `PromptComposer`, and `ModelRegistry` paths.
- No permanent parallel eval stack.
- Python-native evaluators fit the backend/core test ecosystem and typed contracts.
- Evaluation data should be reusable for unit/integration/e2e quality gates.
- Pydantic Evals supports datasets, cases, evaluators, LLM judges, and span-based evals.
- Optional Logfire integration must not become a dependency.

---

## Options Considered

### Option A — Pydantic Evals as SSOT (chosen)

Replace promptfoo with Pydantic Evals. Evaluation suites are Python code and exercise Narrare's actual agent/prompt/model paths.

**Pros:**
- Best architectural fit with Pydantic-AI agent runtime.
- Typed cases and evaluators.
- Can evaluate structured outputs and validators directly.
- Can attach to OpenTelemetry span context without Logfire.
- Eliminates promptfoo's separate Node/YAML/provider layer.

**Cons:**
- Less suited than promptfoo for declarative prompt-matrix exploration.
- Requires implementation of Narrare-specific evaluator libraries.

### Option B — Keep promptfoo as primary eval framework

Continue ADR-018.

**Pros:**
- Strong YAML prompt matrices and red-team style workflows.
- Existing ADR and likely existing scripts are already aligned to it.

**Cons:**
- Does not naturally run through Narrare's Python agent architecture.
- Keeps a second quality gate stack.
- Risks validating prompt text while missing tool/output-validator/runtime regressions.

### Option C — Run promptfoo and Pydantic Evals in parallel

Use promptfoo for prompt matrices and Pydantic Evals for agent runtime cases.

**Pros:**
- Maximum tool coverage.

**Cons:**
- Explicitly violates the user decision against permanent parallel stacks.
- Duplicates cases and reporting.
- Makes quality ownership ambiguous.

### Option D — Custom pytest eval fixtures only

Write bespoke pytest-based LLM evals without Pydantic Evals.

**Pros:**
- No additional eval framework.

**Cons:**
- Rebuilds dataset/case/evaluator abstractions already provided by Pydantic Evals.
- Weak span-based evaluation story.

---

## Decision

**We choose Option A: Pydantic Evals is Narrare's evaluation SSOT.**

promptfoo is superseded and must be removed in the implementation phase. No promptfoo suites, CI jobs, or dependencies remain as a steady state.

Initial required suites:

1. KB Extraction.
2. Rewrite Selection.
3. Preference Analysis.

Forbidden steady states:

- promptfoo plus Pydantic Evals both maintained.
- Evals that bypass `PromptComposer` for user-customizable prompt content.
- Evals that call model providers directly instead of `ModelRegistry`/approved agent paths.
- Logfire required for eval execution or reporting.

---

## Rationale

Narrare's AI quality is now runtime quality, not only prompt text quality. Pydantic Evals evaluates the same Python abstractions that production uses: agent deps, tools, result types, output validators, model routing, and prompt composition. That makes it a better long-term architectural fit than promptfoo.

The accepted tradeoff is losing promptfoo's declarative YAML matrix ergonomics. That is acceptable because Narrare's correctness depends more on typed agent behavior and structured outputs than on raw prompt permutations.

---

## Consequences

**Positive:**
- One evaluation stack aligned with Pydantic-AI runtime.
- Evals can cover structured outputs, validators, tool calls, and memory interactions.
- Better RULE-01b/RULE-02/RULE-03 fit than provider-direct YAML evals.

**Negative / Tradeoffs:**
- Existing promptfoo artifacts must be migrated, not kept.
- Teams lose promptfoo's web UI and YAML-first workflow.
- Evaluator library design is now a core/platform architecture task.

**Constraints introduced:**
- All AI eval suites must route through approved Narrare agent/runtime abstractions.
- Any future eval tool requires an ADR and must not create a permanent parallel quality gate.

---

## Implementation Plan / Migration Plan

1. Add Pydantic Evals dependency through the Python dependency graph after verifying current package naming/version.
2. Create Python-native eval suite structure for KB Extraction, Rewrite Selection, and Preference Analysis.
3. Define reusable evaluator contracts for qualitative rubric scoring, structured output validity, prompt safety, and span attribute checks.
4. Migrate existing promptfoo cases into Pydantic Evals datasets/cases where applicable.
5. Remove promptfoo configuration, Node dependency usage, CI jobs, and docs references.
6. Connect eval reporting to CI artifacts and OpenTelemetry spans; Logfire remains optional and unused for core execution.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | Evals exercise agents/model registry, not direct provider SDKs. |
| RULE-02 | ✅ | Prompt content enters through `PromptComposer` and capability mechanisms. |
| RULE-03 | ✅ | Shared evaluator services require contracts before implementation. |
| RULE-07 | ✅ | Evals depend on public core/API contracts; production modules do not depend on evals. |
| RULE-10 | ✅ | Evals complement tests; they do not replace deterministic unit/integration coverage. |
| RULE-20 | ✅ | promptfoo is removed, not kept as a parallel stack. |
| RULE-22 | ✅ | New eval intents/cases must pass prompt semantic coherence checks. |

---

## Sustainability Check

- Correct in 3 months: yes; Pydantic Evals aligns with the accepted Pydantic-AI runtime.
- Hard-to-undo coupling: reduced by removing Node/YAML/provider-direct eval coupling.
- Simplest correct solution: yes; one eval SSOT.
- Design intent clear: yes; evals validate production runtime paths.

---

## Review Triggers

- Pydantic Evals lacks a required feature after the first three suites are implemented.
- Pydantic AI changes its evaluation/instrumentation APIs materially.
- A new eval requirement needs red-team/prompt-matrix capabilities that cannot be represented in Python-native suites.
