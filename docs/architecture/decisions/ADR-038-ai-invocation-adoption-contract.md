# ADR-038 — AI Invocation Adoption Contract

> **Status:** ✅ Implemented (P0–P5; ADR-045 completes runtime enforcement)
> **Date:** 2026-06-05
> **Deciders:** User, Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-025, ADR-026, ADR-032, ADR-037, ADR-045, INFRA-013, CONSTRAINTS.md RULE-02/RULE-03/RULE-20/RULE-21/RULE-22

---

## Context

CR-03 found that Narrare's feature-adoption checks can report acceptable static
coverage while runtime AI invocations still miss the context that the adoption claim
depends on. The concrete symptoms are:

- `PromptComposer` accepts an optional `PreferenceProvider`, but the API singleton
  currently receives `None`; preferences may therefore be present in templates or
  registry metadata without being delivered to the request.
- `scripts/adoption/scorer.py` primarily scores prompt/template and registry
  evidence; it does not prove that a production feature invocation supplied
  preferences, KB context, output budgets, or final validation evidence.
- `ContextAssembler` exists as an abstraction, but the invocation boundary does not
  yet have one contract that connects feature services, enrichers, `PromptContext`,
  `PromptComposer`, agents/gateway routing, validators, and audit evidence.
- `kb_suggested` and other graph-derived context can exist in templates or assemblers
  while runtime delivery remains unproven.

Root-cause chain:

1. **Symptom:** Adoption registry/templates can pass while runtime AI calls still
   omit preference enrichment, KB suggestions, or intent-specific output budgets.
2. **Why #1:** Existing adoption evidence is mostly static. It verifies that a prompt
   surface can express a variable or requirement, not that production invocation code
   supplied and validated it for a concrete request.
3. **Why #2:** Narrare lacks a dedicated invocation contract between feature services
   and the prompt/agent runtime. Responsibility is split across service code,
   `ContextAssembler`, `PromptContext`, `PromptComposer`, agent deps, model routing,
   static checkers, and content-review audit files.
4. **Design:** Add an AI Invocation Adoption Contract: runtime enrichers, validators,
   output-budget resolution, and evidence sinks become mandatory for adoption claims.

---

## Decision Drivers

- RULE-02/RULE-02a: keep customizable feature prompts in `core/prompts/`, guaranteed
  content in ADR-026 capabilities, and dynamic data in `PromptContext`/Deps.
- RULE-03: define invocation contracts before production implementation.
- RULE-20: static registry compliance without runtime delivery is a half-adoption.
- RULE-21: material changes to invocation boundaries require architecture re-review.
- RULE-22: shared preference, KB, KG, prompt-variable, output-language, and budget
  semantics require cross-feature coherence.
- ADR-037 already governs prompt-surface routeability; this ADR governs the runtime
  path that feeds that surface.

---

## Options Considered

### Option A — Static checker only

Extend adoption registry/scorer rules and prompt-template checks, but keep runtime
invocation unchanged.

**Pros:**
- Smallest platform-only change.
- Keeps adoption results deterministic and cheap.

**Cons:**
- Preserves the root cause: no runtime proof.
- Cannot prove preferences, KB suggestions, final prompt validation, or output budgets
  reached a production request.
- Encourages false “adopted” claims based on template presence.

### Option B — PromptComposer as all-in-one enforcement point

Move preference lookup, KB suggestion retrieval, output-budget selection, and final
prompt validation into `PromptComposer`.

**Pros:**
- Single runtime choke point for prompt assembly.
- Existing services already depend on the composer for feature prompt content.

**Cons:**
- Violates separation of concerns: the composer would become context retrieval,
  policy, validation, budget, and audit infrastructure at once.
- Pulls service/request/user/project concerns into the core prompt builder.
- Makes mode-specific output budgets and evidence persistence hard to test without
  bloating `core/prompts/`.

### Option C — Dedicated invocation contract with enrichers, validators, and evidence

Create a contract that feature services use before every AI call:
`Feature Service → ContextAssembler/Enricher → PromptContext → PromptComposer → NarrareAgent/Gateway → Model`.
Runtime enrichers supply preferences/KB/profile data; validators block missing or
unsafe final prompts; budget resolution is intent/mode-specific; evidence records
prove adoption claims.

**Pros:**
- Directly addresses the root cause by joining static and runtime evidence.
- Keeps `PromptComposer` focused on prompt assembly and cascade behavior.
- Makes preference enrichment explicit: either before composer or through a documented
  manual-injection contract.
- Enables Platform gates without making Platform a runtime dependency.

**Cons:**
- Requires new contracts and tests across Core, Backend, and Platform.
- Runtime evidence must be privacy-safe and bounded.

---

## Decision

**We choose Option C — a dedicated AI Invocation Adoption Contract with enrichers,
validators, budget resolution, and evidence.**

An AI feature may claim adoption only when both conditions hold:

1. **Static contract evidence** exists: ADR-037 prompt-surface manifest, adoption
   registry, prompt-variable registration, and docs/spec entries are consistent.
2. **Runtime invocation evidence** exists: a production invocation path enriches or
   explicitly injects required context, builds the prompt through `PromptComposer`,
   blocks invalid final prompts, resolves an intent/mode-specific output budget, and
   emits privacy-safe evidence to a configured sink or test harness.

Static adoption is necessary but not sufficient.

---

## Rationale

The missing abstraction is not another prompt template or another registry column. It
is the boundary where a feature request becomes a model invocation. That boundary is
where static promises must become runtime facts: preferences are loaded or explicitly
omitted with a reason, KB suggestions are included or budget-rejected, output budgets
are resolved for the intent/mode, and the final prompt is validated before any model
call.

This keeps ADR-026's mechanisms intact: guaranteed content remains in capabilities,
customizable prompt content remains in `PromptComposer`, and dynamic per-invocation
data remains in `PromptContext`/Deps. The invocation contract coordinates those
mechanisms without collapsing them into one god object.

Accepted tradeoff: runtime evidence adds implementation and test surfaces. That is
the correct tradeoff because an adoption gate that cannot prove runtime delivery is
not a gate; it is a static lint report.

---

## Runtime Contract Flow

```text
Feature Service
  → ContextAssembler / ContextEnricher chain
  → PromptInvocationContext
  → PromptContext
  → PromptComposer.build(intent, context)
  → FinalPromptValidator
  → IntentOutputBudgetResolver
  → NarrareAgent / Gateway / ModelRegistry
  → Model
  → FeatureInvocationEvidenceSink
```

Key rules for the flow:

- Preference enrichment happens before `PromptComposer` unless the feature spec
  documents an explicit manual-injection contract with equivalent runtime evidence.
- `PromptComposer` remains the only builder for customizable feature prompt content.
- Final prompt validation is blocking: invalid variables, missing required context,
  unsafe XML boundaries, missing output-language controls, or forbidden fallback
  behavior stop the invocation before the model call.
- Output token budgets are resolved by intent/mode, not by a global default alone.
- Runtime evidence is privacy-safe: it records identifiers, modes, booleans,
  budget decisions, validation outcomes, and hashes/counts where needed; it does not
  persist raw prompt text or user prose by default.

---

## Proposed Contracts Before Implementation

The following interfaces are the required design surface for INFRA-013. Names and
exact module placement may be refined in the feature spec, but production code must
not begin without equivalent contracts.

> **Note:** These contracts are now implemented in
> `packages/core/narrare_core/ai_invocation/`.

```python
class PromptInvocationContext:
    """Request-scoped data needed to build and run one AI invocation."""

    feature_id: str
    intent: LLMIntent
    mode: str | None
    user_id: UUID | None
    project_id: UUID | None
    language: str
    output_language: str | None
    prompt_context: PromptContext
    request_metadata: Mapping[str, str]
```

```python
class ContextEnricher(Protocol):
    """Adds runtime context before PromptComposer runs."""

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext: ...


class PreferenceContextEnricher(ContextEnricher, Protocol):
    """Loads compact memory/preferences for the user/project pair."""

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext: ...
```

```python
class RuntimeVariableValidator(Protocol):
    """Validates variables against the prompt-surface and adoption contracts."""

    def validate(self, context: PromptInvocationContext) -> ValidationResult: ...


class FinalPromptValidator(Protocol):
    """Validates composed prompts before the model call."""

    def validate(self, prompt: ComposedPrompt, context: PromptInvocationContext) -> ValidationResult: ...
```

```python
class IntentOutputBudgetResolver(Protocol):
    """Resolves output-token settings for one intent/mode invocation."""

    async def resolve(self, context: PromptInvocationContext) -> OutputBudgetDecision: ...
```

```python
class FeatureInvocationEvidence:
    """Privacy-safe proof that an invocation satisfied adoption requirements."""

    feature_id: str
    intent: str
    mode: str | None
    prompt_route: str
    preference_status: Literal["provided", "manual", "not_applicable", "missing"]
    kb_suggested_status: Literal["provided", "budget_rejected", "not_applicable", "missing"]
    output_budget_profile: str
    final_prompt_validated: bool
    validation_errors: tuple[str, ...]
    audit_state: str


class FeatureInvocationEvidenceSink(Protocol):
    """Receives runtime evidence in tests, CI probes, or observability."""

    async def record(self, evidence: FeatureInvocationEvidence) -> None: ...
```

---

## Audit Lifecycle States

Adoption/audit items move through these states:

| State | Meaning | Exit criteria |
|-------|---------|---------------|
| `identified` | Audit found a possible adoption gap. | Spec assigns owner, scope, and required evidence. |
| `specified` | ADR/feature spec defines the contract. | Contracts are accepted for implementation. |
| `static_verified` | Registry/manifest/template checks pass. | Runtime evidence tests are written and pass. |
| `runtime_verified` | Production invocation path emits valid evidence in tests/probes. | Audit owner approves adoption claim. |
| `adopted` | Static and runtime gates both pass. | Normal ratchet/no-regression gates monitor drift. |
| `ratcheted_debt` | Legacy gap remains with owner and target, but new regressions fail. | Debt is resolved or ADR-approved exception exists. |
| `blocked` | Contract cannot be satisfied without new architecture. | New ADR/spec or explicit user decision. |

CR-03 is not resolved by creating this ADR. It moves to `specified` for the P0–P3
work described in INFRA-013.

**ADR-045 refinement:** ADR-045 makes these lifecycle terms status-bearing. A mode is
`runtime_verified` only when correlated invocation evidence proves the prepared context,
prompt, budget decision, model-call marker, and evidence record belong to the same
invocation. `adopted` requires both static verification and that runtime evidence.

---

## Consequences

**Positive:**
- Adoption claims require runtime proof, not only template/registry presence.
- Preference delivery, KB suggestion use, final prompt validation, and output budgets
  become explicit gates.
- Static Platform checks and runtime evidence use one vocabulary.
- The distinction between UI i18n, prompt instruction language, and output/writing
  language remains visible at the invocation boundary.

**Negative / Tradeoffs:**
- New protocols and tests are required before CR-03 can be closed.
- Runtime evidence must be carefully redacted to avoid storing prompt/user content.
- Legacy adoption scores may need reclassification because some current PASS/WARN
  results are only static.

**Constraints introduced:**
- A feature cannot claim AI-infrastructure adoption without runtime invocation
  evidence for the relevant path.
- Static checkers must distinguish `static_verified` from `runtime_verified` and
  `adopted`.
- Mode-specific adoption registry entries are required where one feature category
  has different runtime obligations per mode.
- Material changes to the invocation contract require architecture re-review.

---

## Implementation Notes

The implementation contract and migration plan live in
[`INFRA-013 — AI Invocation Adoption Contract`](../../features/infra/INFRA-013-ai-invocation-adoption-contract.md).

Core module: `packages/core/narrare_core/ai_invocation/`.

Minimum implementation surfaces:

- Core: invocation context/contracts, enrichers, validators, output-budget resolver,
  `PromptContext`/`PromptComposer` integration tests.
- Backend: DI/service wiring so feature services provide user/project/request data
  and do not rely on a singleton composer silently lacking preferences.
- Platform: adoption registry/scorer/checker updates that separate static and runtime
  evidence.
- Docs: audit lifecycle and prompt-language wording stay consistent with ADR-026,
  ADR-037, and CONSTRAINTS.md §8.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Invocation still uses approved NarrareAgent/Gateway/ModelRegistry paths. |
| RULE-02/02a | ✅ | PromptComposer remains for customizable prompt content; capabilities and dynamic context stay separate. |
| RULE-03 | ✅ | This ADR and INFRA-013 define contracts before implementation. |
| RULE-04 | ✅ | Contracts, enrichers, validators, budget resolver, and evidence sink are separate responsibilities. |
| RULE-05 | ✅ | Core owns contracts/runtime abstractions; Backend owns request DI; Platform owns checks. |
| RULE-06 | ✅ | PromptComposer is not expanded into context retrieval, budget policy, and audit storage. |
| RULE-07 | ✅ | Core does not import `apps/` or `scripts/`; Platform inspects runtime evidence indirectly. |
| RULE-08 | ✅ | Memory/preference access remains behind existing memory/provider contracts. |
| RULE-09 | ✅ | Proposed public interfaces require full type annotations. |
| RULE-10 | ✅ | INFRA-013 requires unit, integration, checker, and runtime-evidence tests. |
| RULE-11 | ✅ | Validation failures block explicitly; no silent preference/fallback success claims. |
| RULE-12 | ✅ | Service layer remains the public API for WebUI/MCP/A2A/CLI clients. |
| RULE-13 | ✅ | Streaming and non-streaming AI operations share the same invocation contract. |
| RULE-16 | ✅ | UI i18n is unaffected and remains separate from prompt/output language. |
| RULE-17 | ✅ | Any API evidence or budget schema exposed to clients requires matching frontend contracts. |
| RULE-18 | ✅ | Output budgets and provider/model choices resolve through settings/routing, not router constants. |
| RULE-20 | ✅ | Static-only adoption is no longer considered complete. |
| RULE-21 | ✅ | Material changes to invocation boundaries require re-review. |
| RULE-22 | ✅ | Cross-feature preference, KB, KG, variable, budget, and language semantics are explicit. |

---

## Sustainability Check

- **Correct in 3 months:** yes; new AI features must produce the same static and
  runtime evidence before adoption claims are accepted.
- **Hard-to-undo coupling:** reduced; runtime contracts live in Core/Backend while
  Platform consumes evidence/check results rather than becoming a runtime dependency.
- **Simplest correct solution:** yes; a dedicated invocation boundary is narrower
  than turning `PromptComposer` into a god object and stronger than static linting.
- **Design intent clear:** yes; reviewers can distinguish prompt-surface compliance,
  runtime delivery, validation, budget decisions, and audit state.

---

## Review Trigger

- CR-03 P0 implementation changes any proposed contract name, owner, or dependency
  direction materially.
- A feature cannot emit runtime evidence without storing prompt/user content.
- A new AI invocation mode cannot fit the `PromptInvocationContext` shape.
- Project Writing Profile or voice-profile SSOT specs introduce durable context
  sources that alter context precedence.
- Pydantic-AI changes agent/capability/runtime invocation semantics materially.
