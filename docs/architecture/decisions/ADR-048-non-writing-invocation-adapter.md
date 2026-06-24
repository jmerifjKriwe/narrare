# ADR-048 — Non-Writing Invocation Adapter (Domain-Agnostic Pipeline Composition)

> **Status:** ✅ Accepted
> **Date:** 2026-06-24 (accepted; originally proposed 2026-06-14)
> **Deciders:** Architecture Specialist, User
> **Related:** ADR-038 (AI Invocation Adoption Contract), ADR-045 (Runtime Adoption Enforcement, Decision 7), ADR-026 (Capability-Based Prompt Injection), ADR-046 (Prompt-Path Compliance), INFRA-013
> **Supersedes:** None (elaborates ADR-045 Decision 7 — "Direct-agent path standard")
> **Implements:** ADR-045 Slice 1 (partial — prompt-context merge) and Slice 5 (direct-agent audit/adapter)

---

## Context

ADR-045 mandates that **ALL** LLM/agent invocations go through the `InvocationPipeline`
(prepare → compose → finalize) with correlated privacy-safe evidence. The writing domain
has `build_and_validate_prompt()` in `packages/core/narrare_core/writing/_invocation_adapter.py`
which does the prepare→compose→finalize cycle — but non-writing domains (analysis, kb,
planning, chat) currently use `safe_record_evidence()` in `apps/api/narrare/_app/invocation_context.py`,
which runs prepare+finalize with a **PLACEHOLDER PROMPT** and **discards the enriched context**.

### The Two Bugs

**Bug 1 — `safe_record_evidence()` records fake evidence.**
The function (lines 133-165) creates a `ComposedPrompt(system="[analysis-kb-invocation]",
user="[direct-agent-call]")` — a placeholder that has no relationship to the real prompt the
agent receives. Evidence is recorded but is meaningless: the `prompt_fingerprint` in the
evidence record hashes a placeholder, not the actual prompt. Enrichment (preferences,
`kb_suggested`, budget) is computed by `prepare()` but **discarded** — it never reaches the
real prompt or the agent.

**Bug 2 — The writing adapter composes with the ORIGINAL context.**
`build_and_validate_prompt()` (line 140-142) explicitly states:
> `# Phase 2: Build prompt using ORIGINAL prompt_ctx. The enriched context is for
> metadata/evidence, NOT for overriding prompt assembly.`

This directly contradicts ADR-045 Decision 3: "The prompt composition step must use the
prepared context." The `prompt_context_merge.py` helper was created (ADR-045 Slice 1) to
fix this, but it is **not wired** into either the writing adapter or any non-writing path.

### The 38 Call Sites (Three Tiers)

| Tier | Count | Current state | Problem |
|------|-------|---------------|---------|
| FULL | 6 | Writing pipelines use `build_and_validate_prompt()` | Bug 2 — composes with original ctx, not merged |
| PARTIAL | 12 | Use `safe_record_evidence()` + separate `composer.build()` | Bug 1 — placeholder evidence, enrichment discarded |
| NONE | 20 | No pipeline at all — direct `agent.run()` | No evidence, no enrichment, no budget enforcement |

The 12 PARTIAL callers (identified via graph `callers_of safe_record_evidence`):
1. `BetaReaderService.analyze` / `.deep_dive` (analysis)
2. `POVService.analyze` (analysis)
3. `ReadabilityService._analyze_chapter` (analysis)
4. `KBAssistService._run_agent` (kb)
5. `KBConsistencyService.check` (kb)
6. `ExtractionService.extract_from_chapter` (kb)
7. `KBImproveService.analyze` (kb)
8. `KBMergeService.analyze_merge_candidates` (kb)
9. `WorldbuildingService.analyze` (kb)

---

## Root Cause Analysis

### Symptom
Non-writing services record invocation evidence that is decorrelated from the actual
prompt, and enrichment computed by the pipeline is discarded.

### Why #1 — Why is evidence decorrelated?
Because `safe_record_evidence()` was designed as an **evidence-recording helper**, not a
**prompt-composition helper**. It runs prepare+finalize but substitutes a placeholder
prompt because the function has no access to the service's `PromptComposer` or the real
`PromptContext`. The service composes its prompt separately, in parallel, with no
connection to the pipeline invocation.

### Why #2 — Why does the service compose separately?
Because there is **no domain-agnostic adapter** that orchestrates prepare→merge→compose→finalize
for non-writing services. The writing adapter (`build_and_validate_prompt()`) is specialized:
it lives in `writing/_invocation_adapter.py` (internal to the writing subsystem), imports
`WritingError`, and assumes a writing-specific `PromptContext`. Non-writing services cannot
import it (RULE-05 — module boundary) and it has no public contract.

### Why #3 — Why was a placeholder accepted?
Because `safe_record_evidence()` was created as a stopgap in INFRA-013 to get *some*
evidence flowing for non-writing paths while the full composition integration was deferred.
The deferral created governed debt that ADR-045 now requires resolving: PASS requires runtime
adoption, and placeholder evidence cannot satisfy runtime adoption (ADR-045 Decision 1).

### Architectural Design Response
Create a single domain-agnostic adapter in `packages/core/narrare_core/ai_invocation/` that
orchestrates the full prepare→merge→compose→finalize cycle, supports both composer-driven
and agent-internal prompt composition, and returns a result object carrying the composed
prompt, merged context, prepared/finalized state, and resolved budget. Deprecate
`safe_record_evidence()` in favor of this adapter.

---

## Decision Drivers

- **RULE-02/02a:** Feature prompts built by `PromptComposer`; dynamic data in
  `PromptContext`/Deps. The adapter must use `PromptComposer` for composer-driven modes
  and declare manual-injection exceptions for agent-internal modes.
- **RULE-03:** Contract (Protocol) before implementation. The adapter contract must be
  defined before any service migrates.
- **RULE-04/RULE-06:** One responsibility per file. The adapter is a focused orchestration
  module; it does not duplicate pipeline logic, it orchestrates it.
- **RULE-05:** Module boundaries. The adapter lives in `core/ai_invocation/` (public,
  importable by all domains). The writing adapter stays in `core/writing/` (writing-internal).
- **RULE-07:** Dependency direction. Core owns the adapter; Backend owns DI wiring and
  the `KBSuggestedProvider` concrete implementation.
- **RULE-12/RULE-13:** Service Layer is the only public API. The adapter is Core
  infrastructure consumed by the Service Layer; streaming and non-streaming share one
  adapter contract.
- **RULE-20:** Placeholder evidence is a half-implementation. It must be replaced with
  real composition.
- **ADR-045 Decision 3:** Enrichment must reach the `PromptContext` used by
  `PromptComposer` (via `merge_prepared_dynamic_inputs()`).
- **ADR-045 Decision 7:** One direct-agent invocation standard across all domains.

---

## Options Considered

### Option A — Domain-Agnostic Invocation Adapter in `core/ai_invocation/`

Create a single `compose_invocation()` function (and `InvocationAdapter` Protocol) in
`packages/core/narrare_core/ai_invocation/non_writing_adapter.py` that orchestrates
prepare→merge→compose→finalize. Each domain provides its own `PromptComposer` (for
composer-driven modes) or a `ManualInjectionDeclaration` (for agent-internal modes).

**Pros:**
- Single canonical orchestration for ALL non-writing domains (analysis, kb, planning, chat).
- Lives in Core — importable by all domains and all clients (WebUI, MCP, A2A, CLI).
- Supports both composition modes (composer-driven + agent-internal) under ONE function.
- Directly uses the existing `merge_prepared_dynamic_inputs()` helper (ADR-045 Slice 1).
- Testable: pure orchestration, all dependencies injected, no hidden state.
- The writing adapter can eventually converge by delegating composition to this function
  (while keeping its `WritingContextAssembler` specialization for KB tiering).
- Follows the existing pattern: `build_and_validate_prompt()` is also a function, not a class.
- Deprecates `safe_record_evidence()` cleanly — the new function replaces it AND fixes the
  placeholder bug in one migration.

**Cons:**
- Requires migration of 12 PARTIAL + 20 NONE call sites (the 20 NONE sites need pipeline
  injection first — a Backend DI task, not a Core task).
- The adapter must handle two modes, which adds a branch. (Acceptable: the branch is
  `composer is not None` vs `manual_injection_declaration is not None` — explicit and typed.)

### Option B — Per-Domain Adapters

Each domain (analysis, kb, planning, chat) gets its own `_invocation_adapter.py` like writing.

**Pros:**
- Each domain owns its composition path.
- Mirrors the writing pattern exactly.

**Cons:**
- **Violates RULE-06 (one responsibility) and DRY:** the prepare→merge→compose→finalize
  orchestration is identical across domains. Duplicating it 4 times creates 4 places to
  fix when the pipeline contract evolves.
- Creates import ambiguity: which adapter does a cross-domain service use?
- The ONLY domain-specific part is the `PromptComposer` and `PromptContext` construction —
  both of which are already domain-owned and simply **passed to** the adapter.
- Writing has its own adapter for a legitimate reason: `WritingContextAssembler` owns
  tiered KB context budgeting (ADR-045 Decision 5 Option B). Analysis/kb/planning/chat do
  NOT have an equivalent domain-owned assembler — they use the generic pipeline enrichers.
- This is a workaround for not having a shared abstraction. It violates
  `@no_workarounds` and `@alternatives_required`.

**Rejected because:** The orchestration is identical. Domains differ only in their
`PromptComposer` + `PromptContext`, which are already parameters. Per-domain adapters
duplicate the orchestration for no architectural benefit.

### Option C — Extend `safe_record_evidence()`

Modify `safe_record_evidence()` to optionally accept a `PromptComposer` and `PromptContext`,
compose a real prompt, and return it.

**Pros:**
- Smallest migration surface (callers already call `safe_record_evidence()`).

**Cons:**
- **Violates RULE-06 (one responsibility per function):** `safe_record_evidence()` currently
  has one job (record evidence). Adding prompt composition makes it do two jobs
  (compose prompt + record evidence), with a conditional return type
  (`None` when pipeline is None, `ComposedPrompt` when composer is provided).
- **Lives in `apps/api/` (Backend layer):** prompt composition through the pipeline is Core
  logic that MCP/A2A/CLI clients also need (RULE-12, 4-client model). Putting it in Backend
  means non-HTTP clients can't use it.
- **Overloads the null-pipeline fallback:** the function already has a `pipeline is None →
  return` no-op path. Adding composition makes it three modes: no pipeline (no-op),
  pipeline + no composer (placeholder evidence — the current bug), pipeline + composer
  (real composition). This is a conditional nightmare.
- **Does not fix the root cause:** it patches one symptom (placeholder evidence) without
  creating the canonical adapter that ADR-045 Decision 7 requires.
- The function name `safe_record_evidence` would become a lie — it would also compose
  prompts. Naming would have to change, which means migration anyway.

**Rejected because:** It violates RULE-06, lives in the wrong layer, and patches a symptom
instead of building the canonical adapter.

---

## Decision

**We choose Option A — a domain-agnostic invocation adapter in `core/ai_invocation/`.**

A single `compose_invocation()` function orchestrates the full
prepare→merge→compose→finalize cycle for all non-writing domains. It supports two
composition modes:

1. **Composer-driven mode** (Mode 1): the service provides a `PromptComposer` and
   `PromptContext`. The adapter runs prepare, merges enriched `dynamic_inputs` into the
   `PromptContext` via the existing `merge_prepared_dynamic_inputs()`, composes the real
   prompt, and finalizes with the real `ComposedPrompt`. The service receives the
   `ComposedPrompt` and passes `composed.system` / `composed.user` to the agent.

2. **Agent-internal mode** (Mode 2): the service provides a
   `ManualInjectionDeclaration` (per ADR-045 Decision 3 Option C). The adapter runs
   prepare, skips composition (the agent owns it), and finalizes with a typed
   manual-injection marker instead of a placeholder. The service passes enriched
   `dynamic_inputs` to the agent via deps.

### Why A over B and C

| Criterion | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| Correct layer (Core) | ✅ | ❌ (per-domain, but orchestration is Core logic) | ❌ (Backend) |
| RULE-06 (one responsibility) | ✅ | ✅ | ❌ (overloaded) |
| DRY (no duplicated orchestration) | ✅ | ❌ (4 copies) | ✅ |
| Fixes placeholder-evidence bug | ✅ | ✅ | ⚠️ (patches, not canonical) |
| Supports agent-internal mode | ✅ | ✅ (per-domain) | ⚠️ (conditional) |
| 4-client model (MCP/A2A/CLI) | ✅ | ⚠️ (each domain must export) | ❌ |
| Converges with writing adapter | ✅ (writing can delegate) | ❌ (diverges further) | ❌ |
| Sustainability (3 months+) | ✅ | ❌ (4 maintenance points) | ❌ |

---

## Contract (Protocol Definitions)

> RULE-03: These contracts are defined BEFORE implementation. Module placement may be
> refined, but production code must not begin without equivalent contracts.

### Location

```
packages/core/narrare_core/ai_invocation/
├── non_writing_adapter.py     ← NEW: compose_invocation() + ComposedInvocation result
├── manual_injection.py        ← NEW: ManualInjectionDeclaration model
├── prompt_context_merge.py    ← EXISTS (ADR-045 Slice 1): merge_prepared_dynamic_inputs()
├── direct_agent.py            ← EXISTS: DirectAgentInvocationStandard (checklist model)
├── pipeline.py                ← EXISTS: InvocationPipeline
├── models.py                  ← EXISTS: PromptInvocationContext, PreparedInvocation, etc.
└── contracts.py               ← EXISTS: ContextEnricher, validators, etc.
```

### Contract 1 — `ManualInjectionDeclaration`

```python
# packages/core/narrare_core/ai_invocation/manual_injection.py

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ManualInjectionDeclaration(BaseModel):
    """Declares that an agent owns prompt composition internally.

    Per ADR-045 Decision 3 Option C, features may bypass the automatic
    PromptContext merge when the agent composes its own prompt from
    deps/capabilities. This declaration is the typed evidence trail.

    Required for Mode 2 (agent-internal) invocations. Forbidden for
    Mode 1 (composer-driven) invocations.

    The declaration must be validated against the adoption registry:
    only declared, tested manual-injection exceptions are allowed.
    """

    model_config = ConfigDict(frozen=True)

    reason: str = Field(
        min_length=10,
        description="Human-readable explanation of why composition is agent-internal.",
    )
    variables: tuple[str, ...] = Field(
        min_length=1,
        description="Dynamic-input variable names the agent consumes internally.",
    )
    injection_mechanism: str = Field(
        description="How variables reach the agent: 'agent_deps', "
        "'capability_dynamic_instructions', 'agent_instructions_decorator'.",
    )
    precedence_level: str = Field(
        default="generated_suggestion",
        description="RULE-22 precedence: where this data ranks in conflict resolution.",
    )
```

### Contract 2 — `ComposedInvocation` (result type)

```python
# packages/core/narrare_core/ai_invocation/non_writing_adapter.py

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from narrare_core.ai_invocation.budgets import OutputBudgetDecision
    from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
    from narrare_core.ai_invocation.pipeline import (
        FinalizedInvocation,
        PreparedInvocation,
    )
    from narrare_core.prompts.composer import ComposedPrompt
    from narrare_core.prompts.context import PromptContext


class ComposedInvocation(BaseModel):
    """Result of composing an invocation through the pipeline.

    Carries everything the service needs to call the agent:
    - The composed prompt (Mode 1) or None (Mode 2 — agent owns composition).
    - The merged PromptContext (enrichment applied) — useful for agent deps.
    - The prepared invocation (enriched context, budget, validation).
    - The finalized invocation (final validation, evidence state).
    - The resolved output budget — for run-limit enforcement (ADR-045 Decision 4).
    """

    model_config = ConfigDict(frozen=True)

    composed_prompt: ComposedPrompt | None
    merged_context: PromptContext
    prepared: PreparedInvocation
    finalized: FinalizedInvocation
    budget: OutputBudgetDecision | None = None
    manual_injection: ManualInjectionDeclaration | None = None

    @property
    def is_composer_driven(self) -> bool:
        """True when Mode 1 (prompt composed by PromptComposer)."""
        return self.composed_prompt is not None

    @property
    def is_agent_internal(self) -> bool:
        """True when Mode 2 (prompt composed by the agent internally)."""
        return self.manual_injection is not None
```

### Contract 3 — `compose_invocation()` function

```python
# packages/core/narrare_core/ai_invocation/non_writing_adapter.py

from __future__ import annotations

from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext


# Mode 1: composer-driven (composer + prompt_context + intent required)
@overload
async def compose_invocation(
    *,
    invocation_pipeline: InvocationPipeline | None,
    invocation_context: PromptInvocationContext,
    composer: PromptComposer,
    prompt_context: PromptContext,
    intent: LLMIntent,
    manual_injection: None = None,
) -> ComposedInvocation: ...


# Mode 2: agent-internal (manual_injection required, composer forbidden)
@overload
async def compose_invocation(
    *,
    invocation_pipeline: InvocationPipeline | None,
    invocation_context: PromptInvocationContext,
    composer: None = None,
    prompt_context: PromptContext | None = None,
    intent: LLMIntent | None = None,
    manual_injection: ManualInjectionDeclaration,
) -> ComposedInvocation: ...


async def compose_invocation(
    *,
    invocation_pipeline: InvocationPipeline | None,
    invocation_context: PromptInvocationContext,
    composer: PromptComposer | None = None,
    prompt_context: PromptContext | None = None,
    intent: LLMIntent | None = None,
    manual_injection: ManualInjectionDeclaration | None = None,
) -> ComposedInvocation:
    """Compose an invocation through the pipeline: prepare → merge → compose → finalize.

    This is the domain-agnostic counterpart to the writing adapter's
    ``build_and_validate_prompt()``. It serves analysis, kb, planning, chat,
    and any future non-writing domain.

    **Mode 1 — Composer-driven** (``composer`` + ``prompt_context`` + ``intent``):
        1. ``prepare()`` — validate variables, enrich (preferences, kb_suggested, etc.),
           resolve budget.
        2. Merge prepared ``dynamic_inputs`` into ``prompt_context`` via
           ``merge_prepared_dynamic_inputs()`` (ADR-045 Decision 3).
        3. Compose the real prompt via ``composer.build(intent, merged_context)``.
        4. ``finalize()`` — validate the REAL composed prompt, record correlated evidence.
        5. Return ``ComposedInvocation`` with ``composed_prompt`` set.

    **Mode 2 — Agent-internal** (``manual_injection`` declaration, no composer):
        1. ``prepare()`` — validate, enrich, resolve budget.
        2. Merge prepared ``dynamic_inputs`` into ``prompt_context`` (if provided) so
           the service can pass enrichment to agent deps.
        3. Skip composition — the agent owns it.
        4. ``finalize()`` — record evidence with a typed manual-injection marker
           (NOT a placeholder prompt). The marker carries the declared variable names
           and injection mechanism.
        5. Return ``ComposedInvocation`` with ``composed_prompt=None``,
           ``manual_injection`` set.

    **Backward compatibility** — ``invocation_pipeline is None``:
        Mode 1: falls back to ``composer.build(intent, prompt_context)`` directly
        (no merge, no finalize). This preserves the pre-pipeline behavior.
        Mode 2: returns a minimal ``ComposedInvocation`` with no-op prepared/finalized.

    Args:
        invocation_pipeline: The InvocationPipeline, or None for backward-compatible
            fallback (no enrichment, no evidence).
        invocation_context: Typed request-scoped context (feature_id, intent, user_id,
            project_id, language, etc.). Built by the service or via
            ``build_invocation_context()``.
        composer: PromptComposer for Mode 1. Must be None for Mode 2.
        prompt_context: PromptContext for Mode 1. Optional for Mode 2 (used only to
            carry merged enrichment to agent deps).
        intent: LLMIntent for Mode 1 (passed to composer). Inferred from
            invocation_context for Mode 2.
        manual_injection: ManualInjectionDeclaration for Mode 2. Must be None for Mode 1.

    Returns:
        ComposedInvocation carrying the composed prompt (Mode 1), merged context,
        prepared/finalized state, and resolved budget.

    Raises:
        InvocationValidationError: If pre-composition or final validation fails
            (Mode 1, when pipeline is provided and validation is FAIL).
        ValueError: If both composer and manual_injection are provided, or neither.
    """
    ...
```

### Contract 4 — `KBSuggestedProvider` (existing — confirmed as the canonical contract)

The `KBSuggestedProvider` Protocol already exists in
`packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py` (lines 38-68).
It is the correct contract. This ADR confirms it and defines the **concrete
implementation requirements**:

```python
# Already defined in core/ai_invocation/enrichers/kb_suggested.py — DO NOT change.

class KBSuggestedProvider(Protocol):
    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> str: ...
```

**Concrete implementation requirements (Backend DI):**

| Requirement | Detail |
|-------------|--------|
| Location | `apps/api/narrare/_app/dependencies_pipeline.py` (or a dedicated provider module) |
| Queries | KB repository for entities relevant to the intent/mode |
| Privacy | Returns formatted KB context text (entity summaries), not raw entries |
| Error handling | Returns empty string on failure (graceful degradation — RULE-11) |
| Injection | Wired into `KBSuggestedContextEnricher(kb_provider=real_provider)` via DI |

The current DI in `dependencies_pipeline.py` (line 56) wires
`KBSuggestedContextEnricher(kb_provider=None)` — the no-provider path. Migration:
provide a real `KBSuggestedProvider` implementation backed by the KB repository.

---

## How Edge Cases Are Handled

### 1. Agent-Internal Prompt Composition (Mode 2)

**Scenario:** `KBConsistencyService.check()` delegates to `KBConsistencyAnalyzer` and
`WorldbuildingAnalyzer`, which build their own prompts internally from `WorldbuildingDeps`
(entity summaries, template structures, relationships). There is no `PromptComposer` call
at the service level.

**How the adapter handles it:**
```python
# KBConsistencyService.check() after migration:
from narrare_core.ai_invocation.non_writing_adapter import compose_invocation
from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration

result = await compose_invocation(
    invocation_pipeline=self._invocation_pipeline,
    invocation_context=build_invocation_context(
        feature_id="kb_consistency",
        intent=LLMIntent.KB_CONSISTENCY,
        project_id=novel_id,
    ),
    manual_injection=ManualInjectionDeclaration(
        reason="KBConsistencyAnalyzer and WorldbuildingAnalyzer compose prompts "
               "internally from WorldbuildingDeps (entity summaries, templates, "
               "relationships). See ADR-044 staged consistency pipeline.",
        variables=("entity_summaries", "template_structures",
                   "existing_relationships"),
        injection_mechanism="agent_deps",
    ),
)
# Enrichment is in result.prepared.context.dynamic_inputs — pass to deps if needed.
# The agent runs with its own internal composition.
```

**Reconciliation with prepare→compose→finalize:**
The pipeline's prepare→compose→finalize model is designed for PromptComposer-driven
composition. For agent-internal composition, the "compose" step is delegated to the agent.
The adapter explicitly models this as a **manual-injection exception** (ADR-045 Decision 3
Option C): prepare runs (enrichment happens), finalize runs (evidence recorded with the
manual-injection marker), but compose is skipped. The evidence record carries
`manual_injection_exception` with the declared variable names and mechanism — this is
privacy-safe and auditable.

**Constraint:** Manual-injection declarations must be registered in the adoption registry
(ADR-045 Decision 3). A service cannot silently use Mode 2 — it must declare it.

### 2. Structured-Output Agents (`output_type=SomeModel`)

**Scenario:** An agent like `registry.run(prompt=..., output_type=ConsistencyReport)`
expects structured output, not text. How does the pipeline handle this?

**Answer:** The adapter does NOT need to know about output types. The pipeline's
`finalize()` validates the composed prompt (a `ComposedPrompt` with system/user strings) —
the output type is orthogonal to prompt composition. The output type affects:

1. **Budget resolution:** Structured output may require more tokens for formatting. The
   `IntentOutputBudgetResolver` is intent/mode-specific and can account for the expected
   output structure. No adapter change needed — the resolver handles it.

2. **Agent construction:** The `output_type` is set on the agent at construction time,
   independent of the pipeline. The service receives the `ComposedPrompt` from the adapter
   and passes `composed.system` / `composed.user` to the agent. The agent's output parsing
   is transparent to the adapter.

3. **Run-limit enforcement:** Per ADR-045 Decision 4, `ResolvedRunLimits` are applied at
   `agent.run()` / `agent.run_stream()`. The budget profile is resolved by the pipeline
   (in `prepared.budget`) and passed to the run-limit resolver. No adapter change needed.

**Conclusion:** Structured-output agents need no special adapter treatment. They use Mode 1
(composer-driven) or Mode 2 (agent-internal) like any other agent.

### 3. Streaming Paths (`run_stream`)

**Scenario:** A service streams output via `agent.run_stream()`. How does the adapter
handle streaming?

**Answer:** The adapter is **identical** for streaming and non-streaming. The
`PromptInvocationContext.streaming` field (already present, line 148 of models.py) signals
to the pipeline that this is a streaming invocation. The adapter:

1. Runs prepare → compose → finalize exactly as in non-streaming.
2. The service receives `ComposedInvocation` with the composed prompt and budget.
3. The service calls `agent.run_stream(prompt=..., deps=..., usage_limits=resolved_limits)`.
4. Evidence is recorded by `finalize()` BEFORE the stream starts — the `model_call_marker`
   is set when the stream begins/ends (per ADR-045 Decision 2, this is a Backend concern,
   not an adapter concern).

**RULE-13 compliance:** Streaming and non-streaming share the same adapter contract. There
is no `compose_invocation_stream()` — one function, one interface.

### 4. Services That Don't Own Their Prompt Composition

**Scenario:** A service like `KBConsistencyService` delegates to `WorldbuildingAnalyzer`,
which uses `PromptRegistry.resolve()` directly (a drift path identified in ADR-046
CR-AUFG-02-05). The service doesn't compose a prompt — the analyzer does, internally.

**How the adapter handles it:**
This is Mode 2 (agent-internal). But note the interaction with **ADR-046**:

- ADR-046 fixes the prompt RESOLUTION path (WorldbuildingAnalyzer must use PromptComposer
  instead of direct PromptRegistry access).
- This ADR (ADR-048) fixes the INVOCATION path (the service must route through the pipeline
  with real composition evidence).

**Order of operations:**
1. ADR-046 migration: `WorldbuildingAnalyzer` is refactored to use `PromptComposer` (or a
   capability-based path). After this, the analyzer either (a) accepts a composed system
   prompt from the service, or (b) composes internally from deps but via PromptComposer.
2. ADR-048 migration: `KBConsistencyService` migrates from `safe_record_evidence()` to
   `compose_invocation()`.

If (a): the service uses Mode 1 — it composes the prompt and passes it to the analyzer.
If (b): the service uses Mode 2 — manual-injection declaration, because the analyzer owns
composition (even if it uses PromptComposer internally, the composition happens inside the
agent call, not at the service level).

**The two ADRs are complementary, not conflicting.** ADR-046 governs HOW prompts are
resolved (PromptComposer vs. f-string/registry). ADR-048 governs HOW invocations are routed
through the pipeline (real composition vs. placeholder evidence).

---

## `safe_record_evidence()` Deprecation and Migration

### Deprecation Path

1. **Phase 1 (this ADR):** Add `compose_invocation()` to `core/ai_invocation/`.
   Mark `safe_record_evidence()` and `record_invocation_evidence()` with a
   `DeprecationWarning` pointing to `compose_invocation()`. Do NOT remove them yet.

2. **Phase 2 (per-domain migration):** Migrate each of the 12 PARTIAL callers to
   `compose_invocation()`. Each migration replaces:
   ```python
   # BEFORE (decorrelated):
   composed = await self._composer.build(LLMIntent.BETA_READ, ctx)
   await safe_record_evidence(self._invocation_pipeline, feature_id=..., ...)
   agent = BetaReaderAgent(model=model, system_prompt=composed.system)
   ```
   with:
   ```python
   # AFTER (correlated):
   result = await compose_invocation(
       invocation_pipeline=self._invocation_pipeline,
       invocation_context=build_invocation_context(...),
       composer=self._composer,
       prompt_context=ctx,
       intent=LLMIntent.BETA_READ,
   )
   agent = BetaReaderAgent(model=model, system_prompt=result.composed_prompt.system)
   ```

3. **Phase 3 (cleanup):** Once all 12 callers are migrated, remove
   `safe_record_evidence()` and `record_invocation_evidence()` from
   `apps/api/narrare/_app/invocation_context.py`. The `build_invocation_context()`
   helper stays (it's still useful for constructing `PromptInvocationContext`).

### What Replaces `safe_record_evidence()`

| Old function | Replacement | Mode |
|-------------|-------------|------|
| `safe_record_evidence()` + separate `composer.build()` | `compose_invocation(composer=...)` | Mode 1 |
| `safe_record_evidence()` (agent-internal, no composer) | `compose_invocation(manual_injection=...)` | Mode 2 |
| `safe_record_evidence()` (pipeline is None) | `compose_invocation(invocation_pipeline=None, composer=...)` | Backward-compat fallback |
| `record_invocation_evidence()` | `compose_invocation()` (finalize step is integrated) | Either mode |

### Backward Compatibility

- **Existing evidence files:** Unaffected. The evidence schema is the same; the new adapter
  records the same `FeatureInvocationEvidence` with better correlation (real prompt
  fingerprint instead of placeholder hash).
- **Existing tests:** Tests that assert `safe_record_evidence()` was called will break.
  They must be updated to assert `compose_invocation()` was called with the expected mode.
- **The `invocation_context.py` module:** Stays during deprecation. `build_invocation_context()`
  remains permanently (it's the context factory, not the evidence recorder).

---

## Writing Adapter Convergence

The writing adapter `build_and_validate_prompt()` had Bug 2 (composes with original ctx).
ADR-045 Decision 3 mandates fixing this. The fix path:

1. **Done (ADR-045 Slice 1 / ADR-048 Slice E):** `build_and_validate_prompt()` now calls
   `merge_prepared_dynamic_inputs(prompt_ctx, prepared.context)` before composing. Bug 2
   is fixed.

2. **Decided (Q2, 2026-06-24):** The writing adapter WILL delegate to
   `compose_invocation()` for the full prepare→merge→compose→finalize orchestration,
   keeping only its `WritingContextAssembler` specialization for KB tiering as
   pre-processing. This is no longer a "future optimization" — it is a decided
   refactoring with a full Architecture Spec and Retrofit-Plan (see
   §Architecture Spec — Q2: Writing-Adapter Full Delegation below). The writing
   adapter stays in `core/writing/` because it imports `WritingError` and owns
   writing-specific context assembly.

**Constraint:** The writing adapter must NOT be imported by non-writing domains (RULE-05).
The existence of the generic `compose_invocation()` ensures non-writing domains have their
own canonical path.

---

## Migration Plan

### Tier Ordering (which tier first)

**Tier 1 — Core adapter (this ADR's deliverable):**
1. Create `manual_injection.py` with `ManualInjectionDeclaration`.
2. Create `non_writing_adapter.py` with `ComposedInvocation` + `compose_invocation()`.
3. Write unit tests for both modes (Mode 1 with merge, Mode 2 with manual injection).
4. Add `DeprecationWarning` to `safe_record_evidence()` and `record_invocation_evidence()`.
5. Export `compose_invocation`, `ComposedInvocation`, `ManualInjectionDeclaration` from
   `ai_invocation/__init__.py`.

**Tier 2 — PARTIAL callers with composer (Mode 1 migration, ~8 sites):**
These services already have `_composer` injected and already call `composer.build()`.
Migration is mechanical: replace `composer.build()` + `safe_record_evidence()` with a single
`compose_invocation()` call.
- `BetaReaderService.analyze` / `.deep_dive`
- `POVService.analyze`
- `ExtractionService.extract_from_chapter`
- `KBImproveService.analyze`
- `WorldbuildingService.analyze`
- `KBMergeService.analyze_merge_candidates`
- `ReadabilityService._analyze_chapter`

**Tier 3 — PARTIAL callers without composer (Mode 2 migration, ~4 sites):**
These services delegate to analyzers/agents that compose internally. Migration requires
a `ManualInjectionDeclaration` per service, registered in the adoption registry.
- `KBConsistencyService.check` (delegates to `KBConsistencyAnalyzer` + `WorldbuildingAnalyzer`)
- `KBAssistService._run_agent` (delegates to KB agent)
- (others identified during audit)

**Tier 4 — NONE callers (no pipeline at all, 20 sites):**
These services have no `_invocation_pipeline` injected. Migration requires Backend DI work:
inject the pipeline, then use `compose_invocation()`. This is the largest migration and is
tracked separately (ADR-045 Slice 5).

**Tier 5 — Writing adapter fix (Bug 2):**
Wire `merge_prepared_dynamic_inputs()` into `build_and_validate_prompt()`. One-line fix,
ADR-045 Slice 1.

**Tier 6 — `safe_record_evidence()` removal:**
After all callers migrated, remove the deprecated functions.

### Adapter Contract per Tier

| Tier | Mode | `composer` | `manual_injection` | Evidence quality |
|------|------|-----------|-------------------|-----------------|
| 2 | Mode 1 | Provided | None | Real prompt fingerprint |
| 3 | Mode 2 | None | Provided | Manual-injection marker |
| 4 | Mode 1 or 2 | Per service | Per service | Depends on service |
| 5 | N/A (writing) | N/A | N/A | Fixed merge → real fingerprint |

---

## Implementation Sequence

### Slice A — Core adapter (implements this ADR)
**Specialist:** Core Specialist
1. `packages/core/narrare_core/ai_invocation/manual_injection.py` — `ManualInjectionDeclaration`.
2. `packages/core/narrare_core/ai_invocation/non_writing_adapter.py` — `ComposedInvocation`
   + `compose_invocation()` with both modes.
3. `packages/core/narrare_core/ai_invocation/__init__.py` — export new types.
4. `tests/unit/core/ai_invocation/test_non_writing_adapter.py`:
   - Mode 1: enrichment reaches merged context and composed prompt.
   - Mode 1: real prompt fingerprint in evidence (not placeholder).
   - Mode 2: manual-injection marker in evidence.
   - Mode 2: enrichment still runs (prepare happens).
   - Backward-compat: `pipeline=None` falls back to `composer.build()`.
   - Error: both composer and manual_injection provided → ValueError.
   - Error: neither provided → ValueError.

### Slice B — Deprecation + first migration (Backend)
**Specialist:** Backend Specialist
1. Add `DeprecationWarning` to `safe_record_evidence()` and `record_invocation_evidence()`.
2. Migrate `BetaReaderService` (Mode 1) as the reference implementation.
3. Update tests for `BetaReaderService` to assert `compose_invocation()` usage.
4. Verify evidence correlation: `prompt_fingerprint` matches real prompt, not placeholder.

### Slice C — Remaining Mode 1 migrations (Backend)
Migrate Tier 2 services (POVService, ExtractionService, KBImproveService, etc.).

### Slice D — Mode 2 migrations + registry (Backend + Platform)
1. Register `ManualInjectionDeclaration`s in the adoption registry for each Mode 2 service.
2. Migrate Tier 3 services.
3. Platform: adoption checker validates that Mode 2 services have a registered declaration.

### Slice E — Writing adapter fix (Core)
Wire `merge_prepared_dynamic_inputs()` into `build_and_validate_prompt()`.
Update `tests/unit/core/writing/test_invocation_adapter.py`.

### Slice F — `safe_record_evidence()` removal
After all callers migrated. Remove deprecated functions + their tests.

---

## Regression Tests Required

### Core
- `tests/unit/core/ai_invocation/test_non_writing_adapter.py`:
  - Mode 1: `merge_prepared_dynamic_inputs()` output feeds `composer.build()`.
  - Mode 1: enrichment `user_preferences` reaches the composed prompt when field was empty.
  - Mode 1: higher-precedence existing values are preserved (RULE-22).
  - Mode 1: `finalize()` receives the REAL composed prompt (fingerprint matches).
  - Mode 2: `prepare()` runs (enrichment happens, budget resolved).
  - Mode 2: `finalize()` records evidence with `manual_injection_exception` marker.
  - Mode 2: `composed_prompt` is None; `merged_context` carries enrichment for deps.
  - Backward-compat: `pipeline=None` → direct `composer.build()`, no evidence.
  - Error: `ValueError` when both `composer` and `manual_injection` provided.
  - Error: `ValueError` when neither provided (and pipeline is not None).
- `tests/unit/core/ai_invocation/test_manual_injection.py`:
  - `ManualInjectionDeclaration` validation (min lengths, required fields).
  - Immutability (frozen model).

### Backend
- Per-service migration tests asserting `compose_invocation()` is called with the correct mode.
- Evidence correlation tests: `prompt_fingerprint` in evidence matches the real composed
  prompt for Mode 1, or carries the manual-injection marker for Mode 2.
- `safe_record_evidence()` deprecation warning is emitted when called.

### Platform
- Adoption checker: Mode 2 services must have a registered `ManualInjectionDeclaration`.
- Adoption checker: placeholder evidence (`prompt_fingerprint` matches the known placeholder
  hash) cannot satisfy runtime adoption for any mode.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Agents/models remain through approved paths; adapter orchestrates pipeline, does not call models. |
| RULE-02/02a | ✅ | Mode 1 uses PromptComposer; Mode 2 declares manual-injection per ADR-045 Decision 3 Option C. |
| RULE-03 | ✅ | This ADR defines `ManualInjectionDeclaration`, `ComposedInvocation`, `compose_invocation()` contracts before implementation. |
| RULE-04 | ✅ | Adapter is a focused module (~120 lines target); manual_injection.py is separate (~40 lines). |
| RULE-05 | ✅ | Adapter lives in `core/ai_invocation/` (public); writing adapter stays in `core/writing/` (internal). Non-writing domains import from the public package, not from writing. |
| RULE-06 | ✅ | `non_writing_adapter.py` has one responsibility (orchestrate prepare→merge→compose→finalize). `manual_injection.py` has one responsibility (declare agent-internal composition). `safe_record_evidence()` deprecation removes a RULE-06 violation (overloaded function). |
| RULE-07 | ✅ | Core owns adapter + contracts; Backend owns DI wiring + KBSuggestedProvider concrete impl. No Core import from apps/. |
| RULE-08 | ✅ | KBSuggestedProvider remains behind Protocol; concrete impl in Backend. |
| RULE-09 | ✅ | All new contracts fully typed; `@overload` discriminates Mode 1/Mode 2; no `Any` in public signatures. |
| RULE-10 | ✅ | Unit tests for both modes; per-service migration tests; evidence correlation tests. |
| RULE-11 | ✅ | Validation failures raise typed errors (Mode 1) or are recorded as evidence (Mode 2). No silent failures. |
| RULE-12 | ✅ | Adapter is Core infrastructure; consumable by WebUI, MCP, A2A, CLI via the Service Layer. |
| RULE-13 | ✅ | One `compose_invocation()` for streaming and non-streaming; `streaming` flag in context signals mode. |
| RULE-20 | ✅ | Replaces placeholder evidence (half-implementation) with real composition. |
| RULE-22 | ✅ | Merge uses existing `merge_prepared_dynamic_inputs()` with RULE-22 precedence (caller > enricher). |
| RULE-23 | ✅ | No type suppressions in new code; fakes must implement Protocols. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. The adapter is the canonical non-writing invocation path.
   New non-writing domains (e.g., a future "research" domain) use it without modification.
2. **Hard-to-undo coupling?** No. The adapter is pure orchestration with injected
   dependencies. It can be replaced or extended without touching domain services (services
   call `compose_invocation()`, which is a stable function signature).
3. **Simplest correct solution?** Yes. One function, two modes, no duplication. Option B
   (4 adapters) is more complex; Option C (overloaded function) is less correct.
4. **Design intent clear?** Yes. Mode 1 = "I have a composer." Mode 2 = "My agent composes
   internally, here's why." The `ComposedInvocation` result carries everything needed for
   the agent call. A new developer can read the docstring and know which mode to use.

---

## Open Questions (Resolved 2026-06-24)

### Q1 — Should Mode 2 (agent-internal) services eventually migrate to Mode 1?

**Decision: (b) — Mode 2 is an exception, not a default.**

Mode 2 (agent-internal) services should be audited for Mode 1 migration potential.
Each Mode 2 declaration must be reviewed: can the service compose the prompt instead
of delegating to an internal agent composition? If yes, migrate to Mode 1. Mode 2
remains valid only for true multi-step/agent-internal paths that cannot be refactored
(e.g., agents that compose different prompts per step from deps/capabilities).

**Enforcement:** The adoption registry must validate that Mode 2 declarations are
audited. When more than 5 Mode 2 declarations exist (per the Review Trigger), an
audit is triggered to check whether they are legitimate exceptions or missed Mode 1
opportunities.

### Q2 — Should the writing adapter delegate to `compose_invocation()`?

**Decision: (b) full delegation — `build_and_validate_prompt()` delegates pipeline
orchestration to `compose_invocation()` Mode 1, keeping only
`WritingContextAssembler` KB-tiering as pre-processing.**

The writing adapter's `build_and_validate_prompt()` will be refactored to delegate
the prepare→merge→compose→finalize cycle to `compose_invocation()` (Mode 1,
composer-driven). The only writing-specific logic that remains in the writing
adapter is the `WritingContextAssembler` KB-tiering pre-processing, which assembles
KB context into the `PromptContext` before the delegated call.

See **§Architecture Spec — Q2: Writing-Adapter Full Delegation** below for the full
specification and Retrofit-Plan.

### Q3 — Should `KBSuggestedProvider` return structured data instead of a string?

**Decision: Structured return — `KBSuggestedProvider.get_suggested_context()` returns
a new `KBSuggestionResult` model instead of `str`.**

The `KBSuggestedProvider` Protocol return type changes from `str` to
`KBSuggestionResult`, carrying an entity list with provenance, token count, and
confidence score. The `KBSuggestedContextEnricher` adapts by receiving structured
data and formatting it into prompt text (the str→text conversion happens in the
enricher, not the provider). This enables precise budget decisions and improves
evidence correlation quality.

This is a Protocol-breaking change. See **§ADR-048 Amendment — Q3:
KBSuggestedProvider Structured Return** below for the full contract definition and
Retrofit-Plan.

---

## Review Triggers

- When a non-writing domain needs a THIRD composition mode (beyond composer-driven and
  agent-internal) — re-evaluate the adapter contract.
- When `compose_invocation()` exceeds 150 lines — split by mode (RULE-04).
- When pydantic-ai changes agent/instructions/capability composition semantics materially.
- When the adoption registry cannot validate `ManualInjectionDeclaration`s without runtime
  introspection — revisit the declaration model.
- When more than 5 Mode 2 declarations exist — audit whether they are legitimate exceptions
  or missed Mode 1 opportunities (per Open Question Q1).

---

## Specialist Handoff

### Core Specialist
**Tasks:**
1. Create `manual_injection.py` with `ManualInjectionDeclaration`.
2. Create `non_writing_adapter.py` with `ComposedInvocation` + `compose_invocation()`.
3. Export from `ai_invocation/__init__.py`.
4. Unit tests for both modes + backward-compat + error cases.

**Critical constraints:**
- RULE-03/RULE-04/RULE-06/RULE-07.
- Must use existing `merge_prepared_dynamic_inputs()` — do NOT reimplement merge.
- Must use existing `InvocationPipeline.prepare()` / `.finalize()` — do NOT reimplement.
- No `Any` in public signatures (RULE-09).

**Definition of Done:**
- `compose_invocation()` Mode 1 composes with merged context (not original).
- Mode 1 evidence fingerprint matches the real prompt.
- Mode 2 records manual-injection marker (not placeholder).
- All unit tests pass.

### Backend Specialist
**Tasks:**
1. Add `DeprecationWarning` to `safe_record_evidence()` / `record_invocation_evidence()`.
2. Migrate `BetaReaderService` as reference Mode 1 implementation.
3. Migrate remaining Tier 2 services (Mode 1).
4. Register `ManualInjectionDeclaration`s for Tier 3 services.
5. Migrate Tier 3 services (Mode 2).
6. Wire real `KBSuggestedProvider` in `dependencies_pipeline.py`.

**Critical constraints:**
- RULE-04/RULE-06: modularize; do not compress service files during migration.
- RULE-12/RULE-13: streaming and non-streaming share the adapter.
- Evidence correlation must be tested: real prompt fingerprint for Mode 1.

**Definition of Done:**
- `safe_record_evidence()` has zero production callers (only tests).
- `BetaReaderService` uses `compose_invocation()` Mode 1.
- At least one Mode 2 service migrated with registered declaration.
- `KBSuggestedContextEnricher` receives a real provider via DI.

### Platform Specialist
**Tasks:**
1. Adoption checker: validate Mode 2 services have registered `ManualInjectionDeclaration`s.
2. Adoption checker: placeholder evidence cannot satisfy runtime adoption.

**Critical constraints:**
- RULE-07: Platform reads evidence, does not import Core runtime internals.

**Definition of Done:**
- Adoption gate rejects placeholder-evidence paths.
- Mode 2 declarations are validated against the registry.

---

## ADR-048 Amendment — Q3: KBSuggestedProvider Structured Return

> **Amendment Date:** 2026-06-24
> **Amends:** Contract 4 — `KBSuggestedProvider` Protocol (return type change)
> **Trigger:** adr-process.md D.4 Retrofit-Plan mandatory (changes prompt enrichment mechanics)

### Motivation

The current `KBSuggestedProvider.get_suggested_context()` returns `str` — a
pre-formatted text blob. This has three architectural limitations:

1. **Budget imprecision:** The budget resolver cannot make informed token-budget
   decisions because it receives a flat string, not per-entity token counts. It
   cannot selectively include/exclude entities based on remaining budget.

2. **Evidence quality:** The evidence record carries a formatted string with no
   structured provenance. When auditing which KB entities influenced a prompt,
   there is no machine-readable correlation — only a text blob.

3. **Enricher coupling:** The provider both queries KB data AND formats it into
   prompt text. This violates RULE-06 (one responsibility): the provider should
   provide data; the enricher should format it for prompt injection.

### Root Cause Analysis

**Symptom:** Budget decisions for KB-suggested context are imprecise; evidence
correlation is text-only.

**Why #1:** Because the provider returns a pre-formatted string, losing entity-level
structure before it reaches the budget resolver.

**Why #2:** Because the Protocol was designed as a quick text-injection mechanism
(ADR-038/ADR-039), not as a structured data provider. The formatting responsibility
was placed in the provider to minimize enricher complexity.

**Architectural design response:** Separate data provision from text formatting.
The provider returns structured data (`KBSuggestionResult`); the enricher formats
it into prompt text and populates `dynamic_inputs["kb_suggested"]`.

### Contract Change

#### New Model: `KBSuggestionResult`

```python
# packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KBSuggestedEntity(BaseModel):
    """A single KB entity suggested for context injection.

    Carries structured provenance so the enricher and evidence system
    can correlate which entities influenced the prompt.
    """

    model_config = ConfigDict(frozen=True)

    entity_id: str = Field(description="Stable identifier for the KB entity.")
    name: str = Field(description="Display name of the entity.")
    entity_type: str = Field(description="Entity type (character, location, faction, etc.).")
    summary: str = Field(description="Short summary/description of the entity.")
    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="Relevance/confidence score in [0.0, 1.0]. "
        "Derived from usage_count or semantic relevance.",
    )
    token_count: int = Field(
        ge=0,
        description="Approximate token count of the formatted entity representation. "
        "Enables per-entity budget decisions.",
    )
    provenance: str = Field(
        description="Provenance source identifier (e.g., 'kb_repository', "
        "'wiki_cache'). Used for evidence correlation.",
    )


class KBSuggestionResult(BaseModel):
    """Structured result from KBSuggestedProvider.get_suggested_context().

    Replaces the previous ``str`` return type. Carries an entity list with
    per-entity token counts and provenance, plus an aggregate token count
    for budget resolution.

    The enricher formats this into prompt text; the budget resolver uses
    per-entity token counts for precise budget decisions.
    """

    model_config = ConfigDict(frozen=True)

    entities: tuple[KBSuggestedEntity, ...] = Field(
        default=(),
        description="Suggested KB entities, ordered by relevance (descending).",
    )
    total_token_count: int = Field(
        ge=0,
        description="Sum of all entity token_counts. Pre-computed for budget "
        "resolver convenience.",
    )
    source: str = Field(
        description="Provider source identifier (e.g., 'kb_repository').",
    )
    query_metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional metadata about the query (e.g., total_entries_found, "
        "query_intent). Used for observability/evidence.",
    )
```

#### Updated Protocol: `KBSuggestedProvider`

```python
class KBSuggestedProvider(Protocol):
    """Provides KB-suggested context for an AI invocation.

    Implementations query the knowledge base for relevant context
    (characters, locations, factions, plot threads, etc.) based on
    the invocation parameters.

    Returns structured data (KBSuggestionResult); the enricher formats
    it into prompt text.
    """

    async def get_suggested_context(
        self,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
        intent: str | None = None,
        mode: str | None = None,
    ) -> KBSuggestionResult:
        """Return structured KB-suggested context for the given parameters.

        Args:
            user_id: The user identifier, or None.
            project_id: The project identifier, or None.
            intent: The invocation intent value, or None.
            mode: The invocation mode, or None.

        Returns:
            KBSuggestionResult with entity list, token counts, and provenance.
            Returns an empty result (no entities) when no KB entries are found
            or the project_id is unresolvable.
        """
        ...
```

#### Updated Enricher: `KBSuggestedContextEnricher`

The enricher gains a new responsibility: formatting structured data into prompt
text. This is the str→text conversion point.

```python
class KBSuggestedContextEnricher:
    """Adds KB-suggested context to the invocation context.

    Receives structured KBSuggestionResult from the provider, formats it
    into prompt text, and injects into dynamic_inputs["kb_suggested"].

    The formatted text is what reaches the PromptComposer via merge.
    The structured result is stored in dynamic_inputs["kb_suggested_structured"]
    for budget resolver and evidence use.
    """

    def __init__(self, kb_provider: KBSuggestedProvider | None = None) -> None:
        self._provider = kb_provider

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        # ... existing adoption-policy check ...
        result = await self._provider.get_suggested_context(...)
        if not result.entities:
            return context  # graceful degradation

        formatted_text = self._format_entities(result)
        return context.model_copy(update={
            "dynamic_inputs": {
                **context.dynamic_inputs,
                KB_SOURCE_KEY: formatted_text,
                f"{KB_SOURCE_KEY}_structured": result,  # for budget resolver + evidence
            },
        })

    @staticmethod
    def _format_entities(result: KBSuggestionResult) -> str:
        """Format structured entities into prompt-ready text.

        This is the single str→text conversion point. The format mirrors
        the previous provider output for backward-compatible prompt content.
        """
        lines = []
        for entity in result.entities:
            lines.append(
                f"{entity.name} ({entity.entity_type}), "
                f"relevance: {entity.relevance_score:.2f}"
            )
        return "\n".join(lines)
```

#### Budget-Resolver Integration

The budget resolver can now use `kb_suggested_structured` from `dynamic_inputs`
to make per-entity budget decisions:

- If total token budget for KB context is exceeded, the resolver can select the
  top-N entities by relevance that fit within the budget.
- Per-entity `token_count` enables precise truncation rather than whole-string
  truncation.

This integration is a follow-up to the contract change; the initial migration
keeps the existing budget resolver behavior (using the formatted text) and adds
structured data alongside it.

#### Evidence Quality

The evidence record can now carry structured provenance:
- `kb_suggested_structured` in `dynamic_inputs` provides entity-level correlation.
- The `provenance` field on each entity enables audit trails: "which KB entities
  influenced this prompt?"

### Retrofit-Plan (adr-process.md D.4)

#### 1. Inventory of Affected Paths

| Path | File | Symbol | Current State |
|------|------|--------|---------------|
| `KBSuggestedProvider` Protocol | `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py` | `KBSuggestedProvider.get_suggested_context()` | Returns `str` |
| `KBSuggestedContextEnricher` | `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py` | `KBSuggestedContextEnricher.enrich()` | Receives `str`, injects into `dynamic_inputs` |
| `KBSuggestedProviderImpl` | `apps/api/narrare/kb/kb_suggested_provider.py` | `KBSuggestedProviderImpl.get_suggested_context()` | Returns formatted `str` |
| DI wiring | `apps/api/narrare/_app/dependencies_pipeline.py` | `KBSuggestedContextEnricher(kb_provider=...)` | Wires `KBSuggestedProviderImpl` |
| Budget resolver | `packages/core/narrare_core/ai_invocation/budgets/` | IntentOutputBudgetResolver | Uses `dynamic_inputs["kb_suggested"]` as text |
| All services using kb_suggested enrichment | (via pipeline `prepare()`) | — | Receive formatted text in `dynamic_inputs` |

#### 2. Migration Steps Per Path

**Step 1 — Core: Define `KBSuggestionResult` + `KBSuggestedEntity` models**
- File: `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py`
- Add `KBSuggestedEntity` and `KBSuggestionResult` Pydantic models (contract above).
- Export from `ai_invocation/__init__.py`.
- Specialist: Core Specialist
- Atomic: models compile, no behavior change yet.

**Step 2 — Core: Update `KBSuggestedProvider` Protocol return type**
- File: `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py`
- Change `get_suggested_context() -> str` to `-> KBSuggestionResult`.
- Specialist: Core Specialist
- Atomic: Protocol change. All implementations must be updated in the same migration
  (breaking change — see assessment below).

**Step 3 — Core: Update `KBSuggestedContextEnricher`**
- File: `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py`
- Add `_format_entities()` static method.
- Update `enrich()` to receive `KBSuggestionResult`, format it, and inject both
  `kb_suggested` (formatted text) and `kb_suggested_structured` (structured data)
  into `dynamic_inputs`.
- Specialist: Core Specialist
- Atomic: enricher compiles with new Protocol. Tests must be updated (Step 6).

**Step 4 — Backend: Update `KBSuggestedProviderImpl`**
- File: `apps/api/narrare/kb/kb_suggested_provider.py`
- Change `get_suggested_context()` to return `KBSuggestionResult`.
- Build `KBSuggestedEntity` objects from KB entries with `entity_id`, `name`,
  `entity_type`, `summary`, `relevance_score`, `token_count`, `provenance`.
- Compute `total_token_count` and `query_metadata`.
- Specialist: Backend Specialist
- Atomic: implementation returns structured data. DI wiring unchanged (same class).

**Step 5 — Backend: Verify DI wiring**
- File: `apps/api/narrare/_app/dependencies_pipeline.py`
- No change needed — `KBSuggestedProviderImpl` still satisfies the Protocol
  (structural typing). Verify the wiring still works.
- Specialist: Backend Specialist
- Atomic: integration test passes.

**Step 6 — Core: Update enricher unit tests**
- File: `tests/unit/core/ai_invocation/test_kb_suggested_enricher.py` (or equivalent)
- Update test fakes to return `KBSuggestionResult` instead of `str`.
- Assert `dynamic_inputs["kb_suggested"]` contains formatted text.
- Assert `dynamic_inputs["kb_suggested_structured"]` contains the structured result.
- Assert graceful degradation with empty `KBSuggestionResult`.
- Specialist: Testing Specialist
- Atomic: tests pass with new contract.

**Step 7 — Backend: Update provider tests**
- File: `tests/unit/api/kb/test_kb_suggested_provider.py` (or equivalent)
- Assert `get_suggested_context()` returns `KBSuggestionResult`.
- Assert entity fields are populated correctly.
- Assert empty result when no entries / unresolvable project_id.
- Specialist: Testing Specialist
- Atomic: tests pass.

#### 3. Breaking-Change Assessment

**This is a Protocol-breaking change.** The `KBSuggestedProvider` Protocol return
type changes from `str` to `KBSuggestionResult`. All implementations and all
consumers must be updated in the same migration.

**Affected implementations:**
- `KBSuggestedProviderImpl` (production) — updated in Step 4.
- Test fakes/mocks implementing `KBSuggestedProvider` — updated in Step 6.

**Affected consumers:**
- `KBSuggestedContextEnricher.enrich()` — updated in Step 3.
- Budget resolver (reads `dynamic_inputs["kb_suggested"]`) — no change needed;
  the enricher still injects formatted text under the same key. The structured
  data is additive (`kb_suggested_structured`).

**Backward compatibility strategy:** Hard cutover. The Protocol is internal to
the invocation pipeline; there are no external API consumers. All implementations
and consumers are in-repo and updated atomically. A deprecation period is not
meaningful for an internal Protocol with a single production implementation.

**Deps/Protocol/schema changes:**
- `KBSuggestedProvider` Protocol: return type change (breaking).
- `KBSuggestedContextEnricher`: new `_format_entities()` method, new
  `kb_suggested_structured` key in `dynamic_inputs`.
- No `Deps` changes (enrichment is pipeline-internal, not agent-deps-facing).

#### 4. Checker Update Plan

- `scripts/check_architecture.py`: No change needed — the Protocol is internal
  and the enricher still injects text under `kb_suggested`.
- Adoption checker (`scripts/adoption/`): No change needed — the adoption
  policy for `kb_suggested` is unchanged; the enricher still populates the
  same `dynamic_inputs` key.
- Future: A checker can be added to verify that `kb_suggested_structured` is
  present when `kb_suggested` is populated (consistency check). This is optional
  and tracked as a follow-up.

#### 5. Test Update Plan

**Existing tests to update:**
- `tests/unit/core/ai_invocation/test_kb_suggested_enricher.py` — fakes return
  `KBSuggestionResult`, assertions check both `kb_suggested` and
  `kb_suggested_structured`.
- `tests/unit/api/kb/test_kb_suggested_provider.py` — assertions check
  `KBSuggestionResult` fields.
- Any test that mocks `KBSuggestedProvider.get_suggested_context()` return value.

**New tests to add:**
- `KBSuggestedEntity` model validation (frozen, field constraints).
- `KBSuggestionResult` model validation (frozen, `total_token_count` consistency).
- Enricher `_format_entities()` output format matches previous provider output
  (backward-compatible prompt content).
- Budget resolver integration test: structured data available for budget decisions
  (follow-up, not blocking initial migration).

**Currently-untested paths gaining coverage:**
- `KBSuggestedEntity` and `KBSuggestionResult` model validation (new models).
- Enricher formatting logic (previously in provider, now in enricher).

---

## Architecture Spec — Q2: Writing-Adapter Full Delegation

> **Spec Date:** 2026-06-24
> **Spec Type:** Architecture Spec (refactoring specification)
> **Trigger:** adr-process.md D.4 Retrofit-Plan mandatory (changes prompt composition mechanics in the writing adapter)

### Refactoring Goal

`build_and_validate_prompt()` in `packages/core/narrare_core/writing/_invocation_adapter.py`
currently implements its own prepare→merge→compose→finalize cycle (lines 130-174).
This duplicates the orchestration logic in `compose_invocation()` (ADR-048).

The refactoring goal: **delegate the pipeline orchestration to
`compose_invocation()` Mode 1 (composer-driven), keeping only
`WritingContextAssembler` KB-tiering as pre-processing.**

After refactoring, `build_and_validate_prompt()` becomes a thin wrapper:
1. Assemble KB context via `WritingContextAssembler` (existing, stays).
2. Build `PromptContext` with assembled KB context (existing, stays).
3. Call `compose_invocation(composer=..., prompt_context=assembled_ctx, ...)` (NEW).
4. Wrap `InvocationValidationError` as `WritingError` (writing-specific error handling).
5. Return `result.composed_prompt`.

### Root Cause Analysis

**Symptom:** The writing adapter duplicates the prepare→merge→compose→finalize
orchestration that `compose_invocation()` already provides.

**Why #1:** Because the writing adapter was created before `compose_invocation()`
existed (ADR-038/INFRA-013 era). When ADR-048 created the domain-agnostic adapter,
the writing adapter was left independent to avoid disrupting the writing pipeline.

**Why #2:** Because the writing adapter has a legitimate specialization
(`WritingContextAssembler` KB-tiering) that was conflated with the pipeline
orchestration. The specialization and the orchestration were in the same function.

**Architectural design response:** Separate the specialization from the orchestration.
The writing adapter keeps its specialization (KB-tiering pre-processing) and
delegates the orchestration to the canonical `compose_invocation()`.

### Alternatives Considered

#### Alternative A — Full delegation (chosen)

`build_and_validate_prompt()` delegates to `compose_invocation()` Mode 1, keeping
only `WritingContextAssembler` pre-processing and `WritingError` wrapping.

**Pros:**
- Single canonical orchestration path for ALL domains (writing + non-writing).
- DRY: no duplicated prepare→merge→compose→finalize logic.
- Future pipeline changes (new enrichers, new validators) automatically apply to
  writing without adapter changes.
- The writing adapter becomes ~40 lines (thin wrapper) instead of ~176 lines.
- `ComposedInvocation` result is available to writing callers (budget, merged
  context, prepared/finalized state) — currently discarded.

**Cons:**
- The writing adapter's return type changes from `ComposedPrompt` to
  `ComposedInvocation` (breaking for callers that expect `ComposedPrompt`).
- Mitigation: the wrapper extracts `result.composed_prompt` and returns it,
  preserving the `ComposedPrompt` return type. Callers that want the full
  `ComposedInvocation` can be migrated separately.

#### Alternative B — Keep independent (rejected)

The writing adapter stays independent with its own orchestration, as it is now.

**Pros:**
- No migration needed.
- Writing adapter has full control over the pipeline cycle.

**Cons:**
- Violates DRY: two copies of prepare→merge→compose→finalize orchestration.
- Future pipeline changes must be applied in two places.
- The writing adapter is 176 lines; the delegation version would be ~40 lines.
- Violates `@no_workarounds`: keeping a duplicate "just because" is a workaround
  for not doing the refactoring.
- Violates `@sustainability_check`: in 3 months, the two copies will have drifted.

**Rejected because:** The orchestration is identical. The only writing-specific
part is `WritingContextAssembler` pre-processing, which is already separate
(`context_assembler.py`). Duplicating the orchestration has no architectural benefit.

#### Alternative C — Move writing adapter into `core/ai_invocation/` (rejected)

Merge the writing adapter into `compose_invocation()` entirely, making
`WritingContextAssembler` a pipeline enricher.

**Pros:**
- Single adapter, zero duplication.

**Cons:**
- Violates RULE-05: `WritingContextAssembler` is writing-domain logic that belongs
  in `core/writing/`. Moving it to `core/ai_invocation/` couples the invocation
  module to the writing domain.
- `WritingContextAssembler` is not a `ContextEnricher` — it's a `ContextAssembler`
  with 5-tier budgeting, a different abstraction level.
- The writing adapter imports `WritingError` (writing-specific error type).
  Moving it to `core/ai_invocation/` would require `ai_invocation` to import
  from `writing`, violating dependency direction (RULE-07).

**Rejected because:** Violates RULE-05 and RULE-07. The writing specialization
must stay in `core/writing/`.

### New Structure

```
build_and_validate_prompt(composer, pipeline, intent, prompt_ctx, ...):
    1. [Writing-specific] WritingContextAssembler assembles KB context
       → This happens BEFORE build_and_validate_prompt is called (existing).
       prompt_ctx already carries assembled KB context.
    2. [Delegated] compose_invocation(
           invocation_pipeline=pipeline,
           invocation_context=ctx,  # auto-created or provided
           composer=composer,
           prompt_context=prompt_ctx,
           intent=intent,
       ) → ComposedInvocation
    3. [Writing-specific] Wrap InvocationValidationError as WritingError
    4. Return result.composed_prompt
```

### Contract: Delegated Call

```python
# packages/core/narrare_core/writing/_invocation_adapter.py (refactored)

async def build_and_validate_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    intent: LLMIntent,
    prompt_ctx: PromptContext,
    invocation_context: PromptInvocationContext | None = None,
    *,
    user_id: object | None = None,
    project_id: object | None = None,
) -> ComposedPrompt:
    """Build a writing prompt, delegating pipeline orchestration to compose_invocation().

    Writing-specific responsibilities:
    - Auto-create PromptInvocationContext when not provided (writing convenience).
    - Wrap InvocationValidationError as WritingError (writing error contract).

    Delegated to compose_invocation() (ADR-048):
    - prepare → merge → compose → finalize cycle.
    - Enrichment (preferences, kb_suggested, budget resolution).
    - Evidence recording with real prompt fingerprint.

    The WritingContextAssembler KB-tiering happens BEFORE this function is called
    (in the WritingPipeline / caller). The assembled KB context is already in
    prompt_ctx. This function does NOT own KB-tiering.

    Args:
        composer: PromptComposer instance for building prompts.
        invocation_pipeline: Optional InvocationPipeline for validation/evidence.
        intent: LLM intent determining the prompt template.
        prompt_ctx: Prompt context with template variables (KB context already assembled).
        invocation_context: Optional typed context for the invocation.
        user_id: Optional user identifier for the invocation context.
        project_id: Optional project identifier for the invocation context.

    Returns:
        ComposedPrompt ready for LLM consumption.

    Raises:
        WritingError: If pre-composition or final validation fails (wraps
            InvocationValidationError from compose_invocation).
    """
    # Auto-create context when pipeline is wired but context was not provided.
    ctx = invocation_context or _create_minimal_invocation_context(
        intent,
        prompt_ctx,
        user_id=user_id,
        project_id=project_id,
    )

    try:
        result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=ctx,
            composer=composer,
            prompt_context=prompt_ctx,
            intent=intent,
        )
    except InvocationValidationError as exc:
        raise WritingError(
            str(exc),
            code=exc.code if hasattr(exc, "code") else "INVOCATION_VALIDATION_FAILED",
        ) from exc

    return result.composed_prompt
```

**Key design decisions:**

1. **Return type stays `ComposedPrompt`:** The wrapper extracts
   `result.composed_prompt` and returns it. This preserves backward compatibility
   for all 26 callers. Callers that need the full `ComposedInvocation` (budget,
   merged context) can be migrated to call `compose_invocation()` directly in a
   follow-up.

2. **`WritingError` wrapping:** `compose_invocation()` raises
   `InvocationValidationError` (Core error type). The writing adapter wraps it
   as `WritingError` (writing-domain error type) to preserve the writing error
   contract that callers expect.

3. **`pipeline=None` fallback:** `compose_invocation()` already handles
   `invocation_pipeline=None` by falling back to `composer.build()` directly.
   The writing adapter no longer needs its own `pipeline is None` branch — it
   delegates to `compose_invocation()` which handles it.

4. **`_create_minimal_invocation_context` stays:** This is writing-specific
   convenience (derives `feature_id` from intent, sets `streaming=True`). It
   stays in the writing adapter.

5. **`WritingContextAssembler` is NOT in this function:** KB-tiering happens
   in the caller (WritingPipeline, InterviewDraftGenerator, WritingTurnService)
   BEFORE `build_and_validate_prompt()` is called. The assembled KB context is
   already in `prompt_ctx`. This function receives the assembled context and
   delegates composition.

### Migration Strategy for 26 Callers

#### Production Callers (3)

| Caller | File | Line | Current Call | After Migration |
|--------|------|------|-------------|----------------|
| `WritingPipeline._build_and_validate_prompt` | `packages/core/narrare_core/writing/pipeline.py` | 357 | Delegates to `build_and_validate_prompt()` | No change — wrapper signature unchanged |
| `InterviewDraftGenerator.stream_draft` | `apps/api/narrare/writing/_interview_draft.py` | 143 | Calls `build_and_validate_prompt()` | No change — wrapper signature unchanged |
| `WritingTurnService.stream_turn` | `apps/api/narrare/writing/ws_turn_service.py` | 135 | Calls `build_and_validate_prompt()` | No change — wrapper signature unchanged |

**All 3 production callers are unaffected** because the wrapper's public
signature (`build_and_validate_prompt(composer, pipeline, intent, prompt_ctx, ...)`)
and return type (`ComposedPrompt`) are unchanged. The refactoring is internal to
the function body.

The 5 pipeline modules that call `WritingPipeline._build_and_validate_prompt`
(`pipeline_extend.py`, `pipeline_interview.py`, `pipeline_scene.py`,
`pipeline_coauthor.py`, `pipeline_rewrite.py`) are also unaffected — they call
the method, which delegates to the function.

#### Test Callers (23)

| Test File | Call Count | Impact |
|-----------|-----------|--------|
| `tests/unit/core/writing/test_invocation_adapter.py` | 10 | Tests call `build_and_validate_prompt()` directly. Signature unchanged. Tests should pass. |
| `tests/unit/core/writing/test_invocation_adapter_correlation.py` | 1 | Same — signature unchanged. |
| `tests/unit/core/writing/test_invocation_auto_context.py` | 7 | Same — signature unchanged. |
| `tests/unit/core/writing/test_invocation_adapter_merge.py` | 2 | Tests merge behavior. Must verify that `compose_invocation()` applies the same merge (it does — same `merge_prepared_dynamic_inputs()`). |
| `tests/unit/core/writing/test_invocation_adapter_context.py` | 3 | Same — signature unchanged. |
| `tests/unit/api/writing/test_ws_turn_service.py` | 1 (test name) | Tests that turn uses `build_and_validate_prompt`. No change. |
| `tests/unit/api/writing/test_interview_draft_contract.py` | 1 (reference) | Tests composer called through adapter. No change. |

**Test compatibility:** All 23 test callers use the same public signature and
return type. The refactoring is internal. Tests that assert specific internal
behavior (e.g., "prepare is called before compose") will still pass because
`compose_invocation()` calls `prepare()` → `merge()` → `compose()` → `finalize()`
in the same order.

**One test class to watch:** `test_invocation_adapter_merge.py` — it verifies
that `build_and_validate_prompt()` Phase 2 composes from the merged context.
After delegation, the merge happens inside `compose_invocation()`. The test
should still pass because `compose_invocation()` uses the same
`merge_prepared_dynamic_inputs()` helper. If the test asserts internal phase
ordering, it may need a minor assertion update (assert merge result is used,
not assert "Phase 2" label).

### Retrofit-Plan (adr-process.md D.4)

#### 1. Inventory of Affected Paths

| Path | File | Symbol | Current State |
|------|------|--------|---------------|
| Writing adapter function | `packages/core/narrare_core/writing/_invocation_adapter.py` | `build_and_validate_prompt()` | 176 lines, own prepare→merge→compose→finalize |
| Pipeline wrapper | `packages/core/narrare_core/writing/pipeline.py` | `WritingPipeline._build_and_validate_prompt()` | Delegates to adapter (line 357) |
| Interview draft | `apps/api/narrare/writing/_interview_draft.py` | `InterviewDraftGenerator.stream_draft()` | Calls adapter (line 143) |
| Turn service | `apps/api/narrare/writing/ws_turn_service.py` | `WritingTurnService.stream_turn()` | Calls adapter (line 135) |
| Pipeline modules (5) | `pipeline_extend.py`, `pipeline_interview.py`, `pipeline_scene.py`, `pipeline_coauthor.py`, `pipeline_rewrite.py` | `pipeline._build_and_validate_prompt()` | Call pipeline wrapper |
| Adapter tests (5 files) | `tests/unit/core/writing/test_invocation_adapter*.py`, `test_invocation_auto_context.py` | 23 test calls | Call `build_and_validate_prompt()` directly |
| Service tests (2 files) | `tests/unit/api/writing/test_ws_turn_service.py`, `test_interview_draft_contract.py` | 2 test references | Assert adapter is used |

#### 2. Migration Steps Per Path

**Step 1 — Core: Refactor `build_and_validate_prompt()` to delegate**
- File: `packages/core/narrare_core/writing/_invocation_adapter.py`
- Replace the prepare→merge→compose→finalize body (lines 130-174) with a
  `compose_invocation()` call.
- Add `from narrare_core.ai_invocation.non_writing_adapter import compose_invocation`
  and `from narrare_core.shared.errors import InvocationValidationError` imports.
- Keep `_create_minimal_invocation_context()` (writing-specific convenience).
- Keep `WritingError` wrapping.
- Remove the `pipeline is None` early return — `compose_invocation()` handles it.
- Specialist: Core Specialist
- Atomic: function compiles, delegates to `compose_invocation()`. Tests must pass.

**Step 2 — Core: Verify merge test compatibility**
- File: `tests/unit/core/writing/test_invocation_adapter_merge.py`
- Run tests. If merge assertions fail, update assertions to verify the merged
  context is used (not internal phase labels).
- Specialist: Testing Specialist
- Atomic: merge tests pass with delegated composition.

**Step 3 — Core: Run full writing adapter test suite**
- Files: all `tests/unit/core/writing/test_invocation_adapter*.py`,
  `test_invocation_auto_context.py`
- Run `pytest tests/unit/core/writing/test_invocation_adapter*.py
  tests/unit/core/writing/test_invocation_auto_context.py`
- All tests should pass (signature unchanged, behavior identical).
- Specialist: Testing Specialist
- Atomic: full test suite green.

**Step 4 — Backend: Run service tests**
- Files: `tests/unit/api/writing/test_ws_turn_service.py`,
  `tests/unit/api/writing/test_interview_draft_contract.py`
- Run `pytest tests/unit/api/writing/test_ws_turn_service.py
  tests/unit/api/writing/test_interview_draft_contract.py`
- All tests should pass (callers unchanged).
- Specialist: Testing Specialist
- Atomic: service tests green.

**Step 5 — Core: Run pipeline module tests**
- Files: tests for `pipeline_extend.py`, `pipeline_interview.py`, etc.
- Run relevant pipeline tests.
- Specialist: Testing Specialist
- Atomic: pipeline tests green.

**Step 6 — Platform: Run architecture checker**
- Run `python scripts/check_architecture.py`
- Verify no new violations (the writing adapter still imports from
  `core/ai_invocation/` — correct direction per RULE-07).
- Specialist: Platform Specialist
- Atomic: checker passes.

#### 3. Breaking-Change Assessment

**Public API impact:** None. The function signature
`build_and_validate_prompt(composer, pipeline, intent, prompt_ctx, ...) -> ComposedPrompt`
is unchanged. All 26 callers (3 production + 23 test) use the same signature and
return type.

**Internal behavior change:** The prepare→merge→compose→finalize cycle now runs
inside `compose_invocation()` instead of inline in `build_and_validate_prompt()`.
The behavior is identical (same `InvocationPipeline.prepare()`, same
`merge_prepared_dynamic_inputs()`, same `composer.build()`, same
`InvocationPipeline.finalize()`).

**Error type change:** `build_and_validate_prompt()` currently raises `WritingError`
directly for validation failures. After delegation, `compose_invocation()` raises
`InvocationValidationError`, which the wrapper catches and re-raises as
`WritingError`. The error type seen by callers is unchanged (`WritingError`).

**Deps/Protocol/schema changes:** None. No Protocol changes, no Deps changes,
no schema changes.

**Backward compatibility:** Fully backward compatible. No deprecation period
needed. The refactoring is internal to the function body.

#### 4. Checker Update Plan

- `scripts/check_architecture.py`: No change needed. The writing adapter
  (`core/writing/_invocation_adapter.py`) imports from `core/ai_invocation/`
  (correct direction per RULE-07). The import was already present for
  `merge_prepared_dynamic_inputs()`; it now also imports `compose_invocation`.
- Adoption checker: No change needed. The adoption policy for writing invocations
  is unchanged.
- File-size checker: The writing adapter shrinks from 176 lines to ~80 lines
  (well within RULE-04 limits). No new violations.

#### 5. Test Update Plan

**Existing tests to update:**
- `tests/unit/core/writing/test_invocation_adapter_merge.py` — verify merge
  assertions still hold with delegated composition. If assertions reference
  internal phase labels ("Phase 2"), update to assert merged context is used.
- All other adapter tests — no changes expected (signature and behavior unchanged).

**New tests to add:**
- Test that `build_and_validate_prompt()` delegates to `compose_invocation()`
  (assert `compose_invocation` is called, not inline prepare/finalize).
- Test that `InvocationValidationError` from `compose_invocation()` is wrapped
  as `WritingError`.
- Test that `pipeline=None` fallback still works (delegated to
  `compose_invocation()` backward-compat path).

**Currently-untested paths gaining coverage:**
- Error wrapping behavior (`InvocationValidationError` → `WritingError`).
- Delegation verification (compose_invocation is the canonical path).
