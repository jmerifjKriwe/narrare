# ADR-045 — Runtime Adoption Enforcement and Invocation Evidence Correlation

> **Status:** ✅ Accepted
> **Date:** 2026-06-13
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-025, ADR-038, ADR-040, ADR-041, ADR-042, ADR-043, CONSTRAINTS.md RULE-01b/RULE-02/RULE-03/RULE-04/RULE-06/RULE-07/RULE-10/RULE-11/RULE-12/RULE-13/RULE-20/RULE-22

---

## Context

CR-03 re-audited the feature-adoption infrastructure after INFRA-013 P0–P5. The
project now has the right vocabulary and most structural components:

- `InvocationPipeline`, `ContextEnricher`, validators, `IntentOutputBudgetResolver`,
  `FeatureInvocationEvidenceSink`, `FileEvidenceSink`, and `PersistentEvidenceSink`.
- Adoption registry modes, runtime requirement declarations, drift checks, and
  `.evidence/` probe artifacts.
- Writing prompt/context infrastructure with `WritingContextAssembler`,
  `PromptContext`, `PromptComposer`, and token-budget tiers.

The remaining CR-03 findings are not “missing docs”. They are semantic alignment
gaps where evidence says “the infrastructure exists” but production execution can
still bypass, ignore, or fail to enforce that infrastructure.

Observed examples:

1. `writing/_invocation_adapter.py::build_and_validate_prompt()` runs
   `InvocationPipeline.prepare(ctx)` but then composes with the original
   `PromptContext`. Enriched `prepared.context.dynamic_inputs` do not reach the
   prompt unless an independent/manual path already supplied them.
2. `llm/gateway.py::ModelRegistry.get_model()` computes token-profile
   `UsageLimits` but returns only the model; `ModelRegistry.stream()` does not
   accept or pass usage limits to `agent.run_stream()`.
3. `apps/api/narrare/writing/ws_handler.py::WritingSessionHandler._handle_direction()`
   builds a minimal prompt directly and streams through `ModelRegistry.stream()`;
   it does not use the writing context assembler or invocation pipeline and the file
   is close to the Python hard limit.
4. `KBSuggestedContextEnricher` can no-op without a provider; writing may still
   supply `kb_suggested` via `WritingContextAssembler`, so evidence must identify
   the canonical adoption path instead of treating “enricher exists” as adoption.
5. `scripts/check_adoption.py` declares `--evidence-repo` but does not pass it into
   `compute_adoption_report()`. The default `just check-adoption` path does not load
   runtime evidence.
6. `scripts/adoption/scorer.py` computes PASS from static category scores; mode
   `runtime_verified`, `adopted`, and `runtime_evidence_gap_count` are visible but do
   not cap the overall status.

---

## Root Cause Analysis

### Symptom

The feature-adoption gate can report PASS while required runtime modes have zero
runtime-verified/adopted paths, and some production AI calls can bypass or ignore
the context, validation, budget, and evidence contracts that the adoption registry
claims are present.

### Why #1 — Why can PASS happen with missing runtime adoption?

Because category status is still computed from static registry/template scores.
Runtime mode facts are collected and displayed, but they are not status-bearing for
the overall gate. Runtime evidence is treated as an annotation, not as part of the
PASS contract.

### Why #2 — Why did runtime evidence become an annotation instead of the contract?

Because INFRA-013 introduced runtime components incrementally without a single
correlation contract that binds `prepare()` → `PromptComposer` output → final
validation → model/agent call → evidence record. Each component can produce proof of
its own existence, but the system does not yet prove that the same invocation carried
the enriched prompt and enforced budget into the actual model call.

### Why #3 — Why did extensive docs fail to prevent this?

The docs documented desired architecture and status vocabulary, but did not define a
blocking semantic contract and machine gate for adoption status. This created three
drift vectors:

1. **Terminology drift:** “Infrastructure complete” was allowed to read like
   “runtime adopted”. The current state correctly notes 27/27 static adoption but
   still lists INFRA-013 as complete, which hides the distinction unless readers
   inspect runtime gap counts.
2. **Evidence drift:** Probe files, placeholder invocation records, and persistent
   evidence are not required to correlate to the production prompt/model call.
3. **Gate drift:** CI enforced the existence of registry/static artifacts more
   strongly than runtime adoption semantics.

### Architectural design response

Adoption becomes a runtime semantic contract, not a documentation claim:

- Required runtime modes cannot return PASS unless all required runtime evidence is
  adopted or explicitly marked `not_applicable` by policy.
- Every runtime evidence record is correlated privacy-safely to one invocation and
  its model/agent call.
- Enrichment must alter the `PromptContext` used by `PromptComposer`, unless a
  feature declares and evidences a manual-injection exception.
- Output budgets must be converted into pydantic-ai run/stream enforcement at the
  agent/gateway boundary.

---

## Decision Drivers

- **RULE-01b:** Agents are the way to use LLMs; model/provider objects come from
  `ModelRegistry`.
- **RULE-02/RULE-02a:** User-customizable feature prompts are built by
  `PromptComposer`; dynamic per-invocation content flows through `PromptContext` or
  agent deps/instructions, not ad-hoc strings.
- **RULE-03:** New semantic boundaries require executable `Protocol`/typed contracts
  before implementation.
- **RULE-04/RULE-06:** `ws_handler.py`, gateway, scorer, and pipeline changes must
  modularize by responsibility; no line-squeezing.
- **RULE-07:** Core stays DB/HTTP-agnostic; Backend owns persistent evidence storage;
  Platform consumes structured evidence without importing runtime internals.
- **RULE-10:** Regression tests and machine gates are part of the architecture, not
  optional validation after the fact.
- **RULE-11:** Missing evidence, unavailable providers, and unenforceable limits must
  be surfaced as typed failures or governed debt, never silently ignored.
- **RULE-12/RULE-13:** WebSocket, REST/SSE, MCP, A2A, and CLI clients must share the
  Service Layer invocation contract; streaming and non-streaming use one policy.
- **RULE-20:** Static-only adoption is a half-implementation.
- **RULE-22:** Preferences, KB, KG, prompt variables, memory, and generated
  suggestions must respect cross-feature precedence.

---

## Options Considered

### Runtime gate semantics

#### Option A — Keep static score as PASS and print runtime gaps

**Pros:** Minimal platform change; preserves current green CI behavior.

**Cons:** Preserves CR-03 root cause. A user can see PASS while `0 adopted` is
reported. This is a misleading gate, not a controlled adoption state.

#### Option B — Make runtime gaps cap status but allow governed baseline debt

The scoring output distinguishes:

- `PASS`: static score passes and required runtime modes have zero unapproved gaps.
- `GOVERNED_DEBT`/`WARN`: static score passes but existing, baseline-approved runtime
  gaps remain.
- `FAIL`: new or unapproved runtime gap, missing evidence source for required runtime
  modes, or static score failure.

**Pros:** Blocks false PASS while preserving ratcheted governance for known debt.
Makes status terminology truthful.

**Cons:** Requires reporter, baseline, and docs updates. CI behavior must be explicit
about whether WARN is allowed in a given job.

#### Option C — Immediate hard FAIL for any required runtime gap

**Pros:** Strongest enforcement and simplest status model.

**Cons:** Breaks current CI until all legacy/runtime gaps are remediated. It removes
the ratchet mechanism already accepted for governed legacy debt.

**Decision:** Choose **Option B**. PASS must mean runtime adopted. Existing runtime debt
may be tracked as governed debt, but it cannot be called PASS.

### Evidence correlation

#### Option A — Continue separate probe files per requirement

**Pros:** Simple; current implementation exists.

**Cons:** A preference probe, final-validation probe, budget probe, and model call can
refer to the same mode without proving they are the same invocation.

#### Option B — Store raw prompt/model payloads for perfect correlation

**Pros:** Easy forensic debugging.

**Cons:** Violates privacy expectations and ADR-038’s evidence guarantee. Raw user prose
and prompts must not become default adoption evidence.

#### Option C — Correlated privacy-safe invocation trace

Every invocation receives an `invocation_id`. Evidence stores fingerprints and markers:
prepared-context fingerprint, composed prompt fingerprint, final-validation result,
budget decision, and model-call marker. Fingerprints are salted hashes or structured
counts/statuses — no raw user prose.

**Pros:** Proves continuity without storing content. Works for run and stream. Fits
ADR-042 persistent evidence.

**Cons:** Requires model/evidence schema migration and test fixtures that assert
correlation.

**Decision:** Choose **Option C**.

### Enrichment-to-PromptContext delivery

#### Option A — Enrichers are evidence-only metadata

**Pros:** Minimal change.

**Cons:** Invalidates the adoption claim: enrichment evidence can exist without prompt
delivery.

#### Option B — `InvocationPipeline.prepare()` returns the canonical prompt context

`PreparedInvocation` becomes the source of the `PromptContext` passed to
`PromptComposer`. Enriched `dynamic_inputs` are merged into `PromptContext` using
documented precedence.

**Pros:** Directly fixes the gap. `prepare()` now has functional effect.

**Cons:** Requires a merge contract and tests for precedence/conflicts.

#### Option C — Feature-owned manual injection with declared exceptions

Features can bypass automatic merge only when the registry/spec declares the manual
injection variables and runtime evidence proves those variables reached the composed
prompt for the same `invocation_id`.

**Pros:** Supports legitimate agent-deps or assembler paths such as writing KB context.

**Cons:** More policy surface; exceptions must be tightly governed.

**Decision:** Choose **Option B** as the default and **Option C** only for declared,
tested exceptions. Option A is rejected.

### Output budget enforcement

#### Option A — Keep budgets as adoption evidence only

**Pros:** No runtime API changes.

**Cons:** Budget evidence can exist while `agent.run()`/`run_stream()` has no enforced
limit. This is the CR-03 FIND-001 root cause.

#### Option B — Enforce only in `ModelRegistry.run()` / `stream()`

**Pros:** Covers convenience paths, including current WebSocket path.

**Cons:** Does not cover first-class `NarrareAgent` usages that call
`agent.run()`/`run_stream()` directly after `get_model()`.

#### Option C — Shared run-limit resolver used by `ModelRegistry` and first-class agents

Create a typed `ResolvedRunLimits`/adapter contract in Core LLM runtime. It converts
`OutputBudgetDecision` + provider/model ceilings into pydantic-ai `UsageLimits` and
provider `ModelSettings` where needed. Both `ModelRegistry.run()/stream()` and
first-class agent service paths receive/pass the resolved limits.

**Pros:** One policy for run and stream, convenience and first-class agents. Provider
ceilings can be handled centrally.

**Cons:** Requires contract and API updates across several services.

**Decision:** Choose **Option C**.

### `kb_suggested` adoption path

#### Option A — Require `KBSuggestedContextEnricher` with a real provider for every mode

**Pros:** Single obvious runtime evidence source.

**Cons:** Over-constrains writing, where `WritingContextAssembler` already owns tiered
KB context assembly and budgeting. It also makes low-latency modes carry unnecessary
KG retrieval cost.

#### Option B — Make `WritingContextAssembler` the canonical writing path and the
enricher the canonical non-writing path

Writing modes adopt `kb_suggested` when assembler evidence proves generated candidates
were considered, included, or budget-rejected with provenance. Analysis/planning/KB
direct-agent modes adopt it through a real provider/enricher only when their policy
declares it required.

**Pros:** Respects existing writing architecture and preserves low-latency modes.

**Cons:** Evidence must carry `kb_suggested_source` to avoid ambiguity.

#### Option C — Remove `kb_suggested` from runtime adoption requirements

**Pros:** Simplest.

**Cons:** Hides the feature-adoption concern CR-03 identified.

**Decision:** Choose **Option B**.

### WebSocket writing remediation

#### Option A — Patch `_handle_direction()` to call `build_and_validate_prompt()`

**Pros:** Smallest code change.

**Cons:** Leaves `ws_handler.py` near the hard limit, still bypasses assembler/session
context, and does not create a reusable Service Layer contract.

#### Option B — Extract a WebSocket turn service/module using the standard invocation
contract

Move prompt/context/model streaming logic out of `ws_handler.py` into focused modules:
message routing remains in the handler; turn orchestration uses the writing service
contract, assembler, invocation pipeline, budget enforcement, and evidence.

**Pros:** Fixes CR-03 and RULE-04/RULE-06 together. Supports future MCP/A2A adapters
through the same service boundary.

**Cons:** Requires backend modularization and tests.

**Decision:** Choose **Option B**.

### Direct-agent paths for analysis/kb/planning/chat

#### Option A — Keep service-specific proof patterns

**Pros:** Minimal changes per feature.

**Cons:** Recreates parallel adoption semantics and makes audits mode-specific.

#### Option B — One direct-agent invocation standard

Any service that calls a first-class `NarrareAgent` must either use the shared
invocation adapter or perform the equivalent steps: prepare canonical context,
compose/attach feature prompt through the approved channel, finalize, resolve/apply
run limits, and record correlated evidence.

**Pros:** One policy across analysis, KB, planning, chat, writing, run, and stream.

**Cons:** Requires targeted audits and service updates.

**Decision:** Choose **Option B**.

### mem0 learning events

#### Option A — Continue storing only generic accept/reject/modify feedback

**Pros:** Existing contracts exist.

**Cons:** Misses repeated steering, KB interview style, and analysis calibration; current
feedback text can over-capture raw suggestion/prose.

#### Option B — Typed learning events with precedence and privacy boundaries

Define learning event kinds for accepted/rejected/modified suggestions, repeated
steering, KB interview style, and analysis calibration. Persist an audit event and send
compact, structured preference summaries to mem0. Preferences always rank below current
author instructions, explicit project/profile settings, scene/story/timeline context,
and curated KB.

**Pros:** Uses mem0 where it adds value while preventing preferences from overriding
objective/curated sources.

**Cons:** Requires memory model/protocol evolution and migration tests if DB schemas
change.

**Decision:** Choose **Option B**.

### `comprehensive` token profile exposure

#### Option A — Leave `comprehensive` internal-only

**Pros:** No UI/API changes.

**Cons:** Cross-chapter consistency can require the profile but users/operators cannot
select/validate it consistently.

#### Option B — Expose `comprehensive` as a first-class profile with provider/model
ceiling validation

`quick`, `balanced`, `long_texts`, `comprehensive`, and `custom` are consistently
recognized in core, backend schemas, frontend settings, and adoption registry.
Resolved limits are capped or rejected against provider/model max-output metadata.

**Pros:** Aligns configuration with runtime needs and prevents invalid model calls.

**Cons:** Requires cross-layer contract tests.

**Decision:** Choose **Option B**.

---

## Decisions

### 1. Runtime adoption status contract

`PASS` is reserved for runtime-adopted features.

For every mode with `requires_runtime_evidence: true`:

- `static_verified=true` is necessary but not sufficient.
- `runtime_verified=true` requires verified evidence for every `required` runtime
  requirement, or `not_applicable` declared by policy.
- `adopted=true` requires both `static_verified` and `runtime_verified`.
- Overall/category status MUST NOT be `PASS` if `runtime_evidence_gap_count > 0`.

Status vocabulary:

| Status | Meaning |
|---|---|
| `PASS` | Static and required runtime adoption satisfied; zero required runtime gaps. |
| `GOVERNED_DEBT` / `WARN` | Existing runtime gaps are baseline-approved and ratcheted; no new gaps. This is not PASS. |
| `FAIL` | Static failure, missing required evidence source, new/unapproved runtime gap, or malformed evidence. |
| `STATIC_ONLY` | Explicitly requested static-only report; cannot be used as adoption PASS. |

`check_adoption.py` must pass `--evidence-repo` through to `compute_adoption_report()`.
Default local and CI commands must either load the intended evidence source or label the
run `STATIC_ONLY`. CI may allow governed debt only through the existing ratchet policy;
it may not print PASS while required runtime modes are missing evidence.

### 2. Correlated privacy-safe evidence contract

Extend the evidence model/schema with correlation fields. Exact storage shape may be
optimized during implementation, but these semantics are mandatory:

| Field | Required | Privacy rule | Purpose |
|---|---:|---|---|
| `invocation_id` | yes | UUID only | Joins prepare/finalize/model-call records. |
| `prepared_context_fingerprint` | yes | hash/counts only | Proves which enriched context entered composition. |
| `prompt_fingerprint` | yes | salted hash + length/variable names, no text | Proves the composed prompt validated is the prompt sent. |
| `budget_decision_fingerprint` | required when budget applies | profile/max/source only | Joins budget resolution to model call. |
| `model_call_marker` | yes | provider/model/profile/status only | Proves run/stream boundary was reached with limits. |
| `streaming` | yes | boolean | Distinguishes run vs stream path. |
| `manual_injection_exception` | conditional | variable names/status only | Explains declared non-merge path. |

Raw prompts, raw manuscript text, raw user directions, and raw suggestions are not
stored in adoption evidence.

### 3. Enrichment-to-`PromptContext` contract

`InvocationPipeline.prepare()` has functional effect. The prompt composition step must
use the prepared context.

Required merge rules:

1. `PromptInvocationContext.prompt_context` is the canonical starting point when present;
   otherwise the caller-provided `PromptContext` is attached before preparation.
2. `prepared.context.dynamic_inputs` are merged into the `PromptContext` passed to
   `PromptComposer`.
3. If a dynamic key maps to a `PromptContext` dataclass field and the field is empty,
   set that field.
4. If the field is already populated by a higher-precedence source, preserve the
   existing value and record `already_provided` evidence.
5. If the key is feature-specific, merge it into `PromptContext.extra` unless already
   present from a higher-precedence source.
6. Conflicts follow RULE-22 precedence:
   current author instruction → explicit project writing profile/manual override →
   current scene/storyboard/timeline → curated KB → learned mem0 preferences → generated
   suggestions.

Manual injection exceptions are allowed only when declared in the adoption registry or
feature spec with:

- variable names,
- injection mechanism (`agent_deps`, assembler, capability dynamic instructions, etc.),
- precedence level,
- runtime evidence fields proving delivery for the same `invocation_id`, and
- tests that fail if the variable disappears from the actual prompt/deps path.

### 4. Output budget enforcement boundary

The boundary that converts output budgets into runtime enforcement is Core LLM runtime,
not Platform and not feature services.

New/extended contracts:

```python
class ResolvedRunLimits(BaseModel):
    """Provider-safe runtime limits for one AI invocation."""

    invocation_id: UUID
    output_budget_profile: str | None
    max_output_tokens: int | None
    provider_max_output_tokens: int | None
    effective_output_tokens: int | None
    usage_limits: object | None  # pydantic_ai.usage.UsageLimits at runtime boundary
    model_settings: Mapping[str, object]
    source: str
```

```python
class RunLimitResolver(Protocol):
    def resolve(
        self,
        *,
        config: ResolvedModelConfig,
        budget: OutputBudgetDecision | None,
        invocation_id: UUID,
    ) -> ResolvedRunLimits: ...
```

Implementation guidance:

- `ModelRegistry.run()` and `ModelRegistry.stream()` accept the resolved limits or the
  inputs needed to resolve them and pass limits to `agent.run()` / `agent.run_stream()`.
- First-class `NarrareAgent` paths receive/pass the same limits via kwargs.
- `get_model()` must not compute unused limits. Either remove that computation or return
  an explicit value object consumed by run/stream callers.
- Provider/model ceilings are read from the existing model-limit mapping/cache; unknown
  ceilings degrade visibly (`provider_max_output_tokens=None`) and still enforce the
  configured budget when possible.
- If a requested profile exceeds a known provider maximum, the resolver either caps with
  evidence (`capped_to_provider_max`) or rejects before model call for modes that require
  exact minimum output capacity.

### 5. `kb_suggested` canonical adoption path

Writing modes:

- Canonical path is `WritingContextAssembler` because it owns tiered context budgeting
  and scene/KB selection.
- Adoption evidence must record `kb_suggested_source="writing_assembler"` and one of:
  `provided`, `budget_rejected`, `not_applicable`, or `missing`.
- Evidence must include count/fingerprint/provenance categories only, not candidate text.

Non-writing modes:

- Canonical path is `KBSuggestedContextEnricher` with a real provider when policy declares
  `kb_suggested` required.
- A no-provider enricher can only emit `not_applicable` if the mode policy declares it;
  it cannot satisfy `required`.

### 6. WebSocket writing contract

Interactive WebSocket writing sessions are writing invocations and must use the same
runtime adoption contract as other writing modes:

- user and project IDs are mandatory in the invocation context,
- `WritingContextAssembler` or an equivalent writing turn context provider supplies
  project/chapter/session context,
- preferences, `kb_suggested`, budget resolution, final validation, and evidence are
  executed for the same `invocation_id`,
- streaming uses the same output-budget enforcement as non-streaming,
- `ws_handler.py` is modularized rather than patched in place.

Module boundary requirement:

| File/module | Responsibility |
|---|---|
| `apps/api/narrare/writing/ws_handler.py` | WebSocket accept/loop/error transport only; below soft target after split. |
| `apps/api/narrare/writing/ws_turn_service.py` or equivalent | One turn orchestration; no transport-specific prompt assembly. |
| `apps/api/narrare/writing/ws_streaming.py` or equivalent | Stream events to WebSocket DTOs. |
| Core writing invocation adapter | Prompt/pipeline merge and validation; no FastAPI/WebSocket imports. |

### 7. Direct-agent path standard

For analysis, KB, planning, chat, and any other first-class agent mode:

1. Build or obtain `PromptInvocationContext` with user/project IDs when available.
2. Run `InvocationPipeline.prepare()`.
3. Compose feature prompt through `PromptComposer` or declare a manual-injection
   exception for agent deps/dynamic instructions.
4. Run `InvocationPipeline.finalize()` before the model call.
5. Resolve and apply `ResolvedRunLimits` at `agent.run()` or `agent.run_stream()`.
6. Record model-call marker evidence after run/stream completion or typed failure.

Chat-specific audit: verify whether any chat path still places feature/system prompt
content into the user channel. If yes, move it to the approved prompt/system channel or
agent capability/deps path; if no, record correlation evidence and close the stale item.

### 8. mem0 learning-event contract and precedence

Extend memory contracts with typed learning events before implementation. The existing
`FeedbackEvent` can be evolved or wrapped, but the public semantic contract must cover:

| Event kind | Examples | Memory precedence |
|---|---|---|
| `suggestion_accepted` | accepted co-author/inline/rewrite suggestion | Learned preference only; never overrides current instruction/curated KB. |
| `suggestion_rejected` | rejected AI prose, rejected KB candidate | Avoidance preference; never objective fact. |
| `suggestion_modified` | user edited AI suggestion before accept | Style/structure preference extracted from deltas, not raw prose by default. |
| `repeated_steering` | “shorter paragraphs”, “ask before adding lore” repeated in sessions | High-confidence style/process preference. |
| `kb_interview_style` | concise questions vs deep lore prompts | Interaction style only; never factual world data. |
| `analysis_calibration` | blunt feedback, prioritize pacing | Reviewer lens; cannot suppress evidence/confidence gates. |

Privacy and precedence boundaries:

- Default memory text is a compact preference summary with metadata
  (`kind`, `intent`, `mode`, `project_id`, confidence). Raw manuscript/prose is not stored
  by default.
- Any raw excerpt use must be deliberately bounded, local-first, and excluded from
  adoption evidence.
- Retrieved preferences populate `user_preferences`, `avoidance_patterns`, and
  `style_constraints` at the learned-memory precedence level only.
- High-impact conflicts with current instruction, project profile, scene/timeline, or
  curated KB are surfaced, not silently resolved.

### 9. `comprehensive` profile exposure and provider max mapping

`comprehensive` is a first-class output profile wherever token profiles are accepted:

- Core profile map and `OutputBudgetDecision`.
- Backend Pydantic schemas and validation.
- Frontend settings/selector where profiles are exposed.
- Adoption registry/drift checks.

Model/provider max mapping must validate the effective output budget:

- Known max output < requested profile → cap or reject with evidence.
- Unknown max output → enforce configured limit and record `provider_max_unknown`.
- UI hard limits must not be lower than supported backend/core schema unless explicitly
  documented as UX protection.

---

## Implementation Sequence and Layer Assignments

### Slice 0 — Regression tests before fixes (Platform + Core)

1. Platform tests proving current false PASS: adoption report with required runtime modes
   and no evidence must not return `PASS`.
2. Core tests proving enriched `dynamic_inputs` currently fail to reach the prompt path.
3. Core LLM tests proving run/stream pass `usage_limits` / model settings to pydantic-ai.
4. Backend tests proving WebSocket turns use user/project IDs and invocation evidence.

No production fix is accepted until these tests fail for the current behavior.

### Slice 1 — Core invocation correlation and prompt merge

- Extend `PromptInvocationContext` / `FeatureInvocationEvidence` or companion models with
  `invocation_id` and fingerprints.
- Add the `PromptContext` merge helper in Core (`core/prompts/` or `core/ai_invocation/`),
  with precedence tests.
- Update the writing invocation adapter to compose with the prepared/merged context.
- Add manual-injection exception model/validation.

### Slice 2 — Core LLM run-limit enforcement

- Add `RunLimitResolver` / `ResolvedRunLimits` contract.
- Update `ModelRegistry.run()` and `stream()` to apply limits.
- Update first-class `NarrareAgent` service paths to pass resolved limits.
- Add provider/max-output validation including `comprehensive`.

### Slice 3 — Backend WebSocket modularization

- Split `ws_handler.py` by responsibility.
- Add a WebSocket turn service that uses the writing assembler/invocation contract.
- Wire persistent/file evidence sinks through existing Backend DI.
- Preserve transport behavior and tests while changing the invocation internals.

### Slice 4 — Platform adoption gate semantics

- Pass `--evidence-repo` into `compute_adoption_report()`.
- Make runtime gap count status-bearing.
- Add `STATIC_ONLY`/governed-debt wording.
- Update `just check-adoption`/CI command to load the intended evidence source or emit
  `STATIC_ONLY`.
- Ensure scorer files remain modular under RULE-04.

### Slice 5 — Canonical `kb_suggested`, direct-agent audit, mem0 events

- Record canonical `kb_suggested_source` evidence.
- Audit analysis/KB/planning/chat paths against the direct-agent standard.
- Define and implement typed learning events with precedence/privacy tests.

### Slice 6 — Docs/status cleanup

- Update CR-03 audit task statuses.
- Update CURRENT_STATE terminology from “static adoption complete” to separate
  “Infrastructure complete” and “Runtime adopted”.
- Update quality-gates docs to reflect runtime-adoption status semantics.
- Update ADR-038/040/041/042 references if implementation changes their status wording.

### Implementation status (2026-06-19)

ADR-045 implementation phases are complete. Runtime evidence markers are in place;
`--evidence-repo` is threaded; invocation correlation fields are populated;
prepared dynamic inputs merge into `PromptContext`; run-limit enforcement is covered;
the WebSocket handler is modularized; and the learning event taxonomy is completed.
Current adoption status is `PASS 0.97`: all 29 modes are `runtime_verified` and
`adopted`. The adoption debt ratchet resolved 116 items; 1 inline-fallback baseline
item remains governed debt.

---

## Specialist Handoff

### Core Specialist

**Tasks**

1. Add/extend Core contracts for invocation correlation, prompt-context merge,
   manual-injection exceptions, and run-limit resolution.
2. Update `InvocationPipeline`/writing invocation adapter so prepared enrichment reaches
   the `PromptContext` used by `PromptComposer`.
3. Update Core LLM runtime so `OutputBudgetDecision` becomes enforced pydantic-ai
   usage/model settings for run and stream paths.
4. Audit first-class agent paths and expose a reusable direct-agent adapter/standard.
5. Extend memory models/protocols for typed learning events and precedence-safe mem0
   preference summaries.

**Critical constraints**

- RULE-01b/RULE-02/RULE-03/RULE-07/RULE-20/RULE-22.
- Core must not import FastAPI, SQLAlchemy, Backend evidence repositories, or Platform
  checkers.
- No raw user prose in adoption evidence.

**Definition of Done**

- Failing regression tests exist first and then pass.
- All new public contracts are typed Protocols/Pydantic models.
- `run()` and `run_stream()` limit enforcement is tested.
- Enrichment merge precedence is tested, including conflict handling.

### Backend Specialist

**Tasks**

1. Modularize `apps/api/narrare/writing/ws_handler.py` into transport, turn service,
   and streaming DTO responsibilities.
2. Wire WebSocket writing turns through the standard writing assembler/invocation
   contract with user/project/chapter/session IDs.
3. Persist correlated invocation evidence through existing File/Persistent sink DI.
4. Apply `comprehensive` profile validation in backend schemas/settings if exposed.
5. Add or update Alembic migration only if evidence schema columns change.

**Critical constraints**

- RULE-04/RULE-06: modularize; do not compress.
- RULE-12/RULE-13: WebSocket is a client of the same Service Layer policy; streaming
  and non-streaming share enforcement semantics.
- RULE-14 if persistent evidence schema changes.

**Definition of Done**

- `ws_handler.py` is below soft target and contains transport logic only.
- WebSocket tests prove correlated runtime evidence and enforced budgets.
- Migration/integration tests pass if DB schema changes.

### Platform Specialist

**Tasks**

1. Make runtime gaps status-bearing in adoption reports.
2. Pass `--evidence-repo` to `compute_adoption_report()`.
3. Update default/CI adoption commands to load evidence or emit `STATIC_ONLY`.
4. Reject placeholder/static-only evidence for required runtime requirements.
5. Add gate tests for PASS/GOVERNED_DEBT/FAIL/STATIC_ONLY semantics.

**Critical constraints**

- RULE-04/RULE-06: split scorer/checker code before limits are approached.
- RULE-07: Platform reads files/JSON/DB adapter output; it must not import Core runtime
  internals directly.
- RULE-11: missing evidence source is visible status, not silent PASS.

**Definition of Done**

- A report with `0 adopted` cannot print `PASS`.
- `--evidence-dir` and `--evidence-repo` paths are covered by tests.
- Baseline-governed debt is clearly not PASS.

### Docs Specialist

**Tasks**

1. Update CR-03 audit tasks/FIND-001 after implementation evidence exists.
2. Update CURRENT_STATE with separate status terminology.
3. Update quality-gates/testing docs for Gate 8 runtime semantics.
4. Add glossary entries for runtime adoption terminology if used in multiple docs.
5. Cross-link ADR-038/040/041/042 to ADR-045 where appropriate.

**Critical constraints**

- CONSTRAINTS.md remains the SSOT for RULE-XX.
- Docs must not mark runtime adoption complete before correlated evidence gates pass.

**Definition of Done**

- Docs distinguish `Infrastructure complete`, `Static verified`, `Runtime verified`,
  `Runtime adopted`, and `Governed adoption debt`.
- Doc-drift checks pass.

---

## Regression Tests and Machine Gates Required

### Core

- `tests/unit/core/ai_invocation/test_prompt_context_merge.py`
  - enriched `user_preferences` reaches `PromptComposer` when field was empty,
  - higher-precedence existing values are preserved,
  - feature-specific dynamic inputs land in `PromptContext.extra`,
  - conflicts produce evidence/warnings.
- `tests/unit/core/writing/test_invocation_adapter.py`
  - `build_and_validate_prompt()` composes with prepared context,
  - final validation evidence uses the same `invocation_id` and prompt fingerprint.
- `tests/unit/core/llm/test_run_limits.py`
  - `OutputBudgetDecision` converts to pydantic-ai usage/model settings,
  - `ModelRegistry.run()` and `stream()` pass limits,
  - provider max caps/rejections are evidenced,
  - `comprehensive` is recognized.
- Direct-agent contract tests for at least one representative analysis, KB, planning,
  and chat path.

### Backend

- WebSocket integration/unit tests:
  - session turn builds invocation context with user/project/chapter/session IDs,
  - preferences and budget evidence are emitted,
  - stream uses the same limit resolver,
  - `ws_handler.py` stays below soft target after modularization.
- Evidence repository integration tests for new correlation fields and indexes/migration
  if ADR-042 schema changes.

### Platform

- `check_adoption.py` tests:
  - required runtime modes with no evidence cannot produce `PASS`,
  - explicit static-only output is labeled `STATIC_ONLY`,
  - `--evidence-repo` reaches `compute_adoption_report()`,
  - governed debt is WARN/GOVERNED_DEBT, not PASS,
  - malformed/mismatched invocation correlation fails.
- Drift/gate tests:
  - adoption registry runtime requirements match evidence requirement names,
  - no placeholder `static_verified` evidence can satisfy runtime requirements,
  - prompt/model-call fingerprints must align for adopted modes.

### Docs gate

- Doc-drift check verifies that “Infrastructure complete” and “Runtime adopted” are not
  used interchangeably in CURRENT_STATE, quality-gates docs, and CR-03 artifacts.

---

## Docs to Update After Implementation

- `_audit/results/content-review/adoption/cr-03-feature-adoption.md` — mark
  CR-AUFG-03-01 through CR-AUFG-03-07 with implemented evidence and close FIND-001.
- `_audit/results/content-review/findings/FIND-001-output-limits-not-enforced.md` — close
  once run/stream enforcement tests pass.
- `docs/_shared/CURRENT_STATE.md` — separate:
  - **Infrastructure complete**: contracts/probes/checkers exist,
  - **Runtime adopted**: correlated production path evidence passes.
- `.opencode/context/narrare-dev/processes/quality-gates.md` *(2026-10-15 correction: that path was removed in f11eb44a and the doc anchor retired by ADR-098 — each ADR states its own completeness checklist; the gate SSOT is the ci.yml header table + CONSTRAINTS.md §6.)* and
  `docs/development/testing-standards.md` — update Gate 8 semantics.
- `docs/architecture/decisions/ADR-038-ai-invocation-adoption-contract.md` — reference
  ADR-045 for correlation/enforcement details.
- `docs/architecture/decisions/ADR-040-kg-ssot-audit-lifecycle.md` — align lifecycle
  state transitions with PASS/GOVERNED_DEBT/STATIC_ONLY semantics.
- `docs/architecture/decisions/ADR-041-typed-manifests-drift-metrics.md` — align drift
  and quality metrics with correlated invocation evidence.
- `docs/architecture/decisions/ADR-042-persistent-evidence-upgrade.md` — update schema
  if new correlation columns are added.
- `docs/_shared/GLOSSARY.md` — add/adjust `Runtime adopted`, `Infrastructure complete`,
  `Invocation evidence correlation`, and `Governed adoption debt` if terminology is
  used broadly.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|---|---|---|
| RULE-01b | ✅ | Model calls remain through `ModelRegistry` / `NarrareAgent`; no direct provider calls. |
| RULE-02/02a | ✅ | Feature prompts still built by `PromptComposer`; dynamic data enters `PromptContext`/Deps. |
| RULE-03 | ✅ | This ADR defines contracts before implementation: merge, run limits, evidence correlation, learning events. |
| RULE-04 | ✅ | Requires modularization of `ws_handler.py`, scorer/gateway split by responsibility. |
| RULE-05 | ✅ | Core owns invocation/LLM contracts; Backend owns WebSocket/persistent evidence; Platform owns gates. |
| RULE-06 | ✅ | Separate responsibilities: prompt merge, run-limit resolution, transport, scoring, memory learning. |
| RULE-07 | ✅ | Core remains DB/HTTP-agnostic; Platform consumes structured evidence; Backend owns SQLAlchemy. |
| RULE-08 | ✅ | mem0 remains behind memory adapter/protocol; no direct SDK use outside approved adapter. |
| RULE-09 | ✅ | New contracts require full type annotations; no public `Any` except adapter boundary with explicit narrowing. |
| RULE-10 | ✅ | Regression tests/gates are specified before implementation. |
| RULE-11 | ✅ | Missing evidence/providers/limits are surfaced as WARN/FAIL/typed errors, not silent success. |
| RULE-12 | ✅ | Service Layer remains the public API for WebUI/MCP/A2A/CLI; WebSocket uses same service contract. |
| RULE-13 | ✅ | Run and stream share the same limit/evidence policy. |
| RULE-20 | ✅ | Rejects static-only adoption as a half-implementation. |
| RULE-22 | ✅ | Uses precedence order for preferences, KB, KG, generated suggestions, and manual overrides. |
| RULE-23 | ✅ | Tests/fakes must implement Protocols; no suppressions as workaround. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. Runtime adoption is defined by correlated evidence,
   not by today’s specific probes.
2. **Hard-to-undo coupling?** No. Core contracts are transport/storage agnostic;
   Backend and Platform remain separate consumers/producers.
3. **Simplest correct solution?** Yes. It strengthens existing INFRA-013 boundaries
   instead of adding another prompt path or static checker.
4. **Design intent clear?** Yes. PASS means runtime adopted; infrastructure existence is
   a different state.

---

## Review Triggers

- When mode count exceeds 50 and single YAML registry becomes unwieldy.
- When pydantic-ai changes usage-limit/model-settings APIs.
- When persistent evidence stores more than correlation metadata or proposes raw prompt
  capture.
- When MCP/A2A adapters are implemented and need the same runtime adoption contract.
