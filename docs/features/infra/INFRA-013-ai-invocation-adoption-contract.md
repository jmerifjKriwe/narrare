# INFRA-013 — AI Invocation Adoption Contract

---
id: INFRA-013
title: "AI Invocation Adoption Contract"
status: in-progress
area: infra
mvp: false

ui_tooltip: "Requires runtime evidence before AI features can claim adoption."
ui_help_short: |
  Ensures AI features do not merely pass static prompt checks, but prove at runtime
  that preferences, KB context, output budgets, and prompt validation reached the
  model invocation path.
ui_help_long: |
  INFRA-013 is the CR-03 adoption-hardening contract. It connects feature services,
  context assemblers/enrichers, PromptContext, PromptComposer, Narrare agents,
  output-budget resolution, validators, and audit evidence so adoption claims are
  backed by runtime proof. It does not add a new user-facing AI feature.
ui_available_in: []

service: null
contract: docs/architecture/decisions/ADR-038-ai-invocation-adoption-contract.md
router: null
prompt: packages/core/narrare_core/prompts/_bundled/
requires: [INFRA-002, INFRA-003, INFRA-005, INFRA-011, INFRA-012, PROMPT-001, PROMPT-002]
---

## Status and Decision Summary

- **Status:** P0 implemented. Core `ai_invocation` module, InvocationPipeline,
  enrichers, validators, budget resolver, and WritingPipeline integration are in
  production. P1–P3 (Evidence Sink, Adoption Checker, User/Project IDs) remain
  outstanding.
- **Governing ADR:** [ADR-038 — AI Invocation Adoption Contract](../../architecture/decisions/ADR-038-ai-invocation-adoption-contract.md).
- **CR-03 state:** P0 implemented. CR-03 is not resolved until P1–P3 exit
  criteria and runtime evidence gates pass.

## Scope

### In Scope

1. Runtime invocation contract for AI features.
2. Preference enrichment before `PromptComposer`, or an explicit manual-injection
   contract with equivalent runtime evidence.
3. Final prompt validation that blocks model calls on missing/unsafe required data.
4. Intent/mode-specific output budget resolution.
5. Mode-specific adoption registry and checker semantics.
6. Runtime evidence records and evidence sinks for tests/CI probes/observability.
7. Audit lifecycle states for CR-03 and future adoption findings.
8. `kb_suggested` runtime verification where quality benefit outweighs token cost.

### Out of Scope

- Creating a new user-facing AI feature.
- Rewriting ADR-025, ADR-026, or ADR-037 wholesale.
- Changing prompt-language policy: bundled feature system prompts remain EN-only by
  default where output/writing language is controlled through variables, Context,
  Deps, or preferences.
- Adding hidden Project Writing Profile, voice-profile SSOT, storage, API, or UI
  work without its own spec.
- Adding external dependencies.
- Production implementation by the Architecture Specialist.

## Problem Statement

Static adoption checks currently answer: “does this category/template/registry claim
the infrastructure exists?” They do not reliably answer: “did this production AI
request receive the required preference/KB/context/budget data and pass final prompt
validation before reaching the model?”

That gap makes adoption status ambiguous. A mode can have `{{user_preferences}}` in a
template and pass registry checks while the runtime dependency path provides no
preference service, or while a service manually builds partial variables without
evidence.

## Root Cause / Motivation

**Symptom:** CR-03 reports partial runtime adoption despite useful static governance:
the adoption checker can pass overall while preference injection, `kb_suggested`, and
intent output budgets remain runtime-uncertain.

**Why #1:** The current adoption registry and scorer mostly inspect prompt files,
variables, registered categories, and heuristics. They do not model the complete
request-to-model invocation path.

**Why #2:** Responsibility for runtime data is split across feature services,
context assemblers, memory/preference providers, `PromptContext`, `PromptComposer`,
model routing, and agents without a single contract or evidence vocabulary.

**Root cause:** Narrare lacks a runtime invocation adoption boundary. The correct fix
is not more static scoring alone; it is a contract that turns static requirements
into runtime evidence.

## Goals and Non-Goals

### Goals

- Make adoption claims require both static and runtime evidence.
- Define contracts before implementation for invocation context, enrichment,
  validation, output budgets, and evidence.
- Keep `PromptComposer` focused on prompt assembly and cascade behavior.
- Ensure preference/KB/profile data is supplied before composing or documented as a
  deliberate manual injection path.
- Block invalid final prompts before model calls.
- Separate UI i18n, prompt instruction language, and output/writing language in all
  gates and evidence.
- Define complete P0–P3 increments with exit criteria.

### Non-Goals

- No prompt wording rewrite except where later implementation proves validation gaps.
- No change to ADR-026 content categories.
- No broad “all-in-one composer” refactor.
- No runtime storage of raw prompts or user prose as adoption evidence.
- No CR-03 resolved claim until runtime gates pass.

## Runtime Contract Flow

```text
Feature Service
  → ContextAssembler / ContextEnricher
  → PromptInvocationContext
  → PromptContext
  → PromptComposer
  → FinalPromptValidator
  → IntentOutputBudgetResolver
  → NarrareAgent / Gateway / ModelRegistry
  → Model
  → FeatureInvocationEvidenceSink
```

### Flow Responsibilities

| Step | Owner | Responsibility |
|------|-------|----------------|
| Feature Service | Backend/Core feature module | Owns request semantics, user/project IDs, selected intent/mode, and service-layer API. |
| ContextAssembler/Enricher | Core feature/context modules | Builds dynamic context, applies token budgets, enriches preferences/KB/profile data. |
| PromptInvocationContext | Core contract | Request-scoped carrier for feature ID, intent, mode, prompt context, metadata, and validation/evidence scope. |
| PromptContext | Core prompts | Supplies dynamic variables to `PromptComposer`. |
| PromptComposer | Core prompts | Resolves route/cascade and builds customizable feature prompts. |
| FinalPromptValidator | Core prompts/context | Blocks invalid composed prompts before model invocation. |
| IntentOutputBudgetResolver | Core LLM/settings | Resolves output budget by intent/mode and settings cascade. |
| NarrareAgent/Gateway/ModelRegistry | Core agents/LLM | Runs the approved agent/model path. |
| EvidenceSink | Tests/Platform/observability adapter | Records privacy-safe runtime evidence. |

## Architectural Decisions

### Decision 1 — Runtime evidence required for adoption claims

Static registry, manifest, and prompt checks are necessary but not sufficient. A
feature/mode reaches `adopted` only when runtime tests or probes record
`FeatureInvocationEvidence` showing enrichment, validation, budget resolution, and
model-call readiness.

### Decision 2 — Preference enrichment before PromptComposer or explicit manual contract

Default path: `PreferenceContextEnricher` resolves compact preference/avoidance data
before `PromptComposer.build()` so templates receive populated variables.

Exception path: a feature may manually inject preferences only if its feature spec
declares:

- where preferences are loaded,
- which `PromptContext` fields/extra variables are populated,
- how missing preferences are represented,
- how evidence proves the manual path ran, and
- why pre-composer enrichment is not the correct path for that feature.

Silent singleton `None` preference services cannot support an adoption claim for a
mode that requires preferences.

### Decision 3 — Final prompt validation blocks model calls

`FinalPromptValidator` runs after `PromptComposer` and before `NarrareAgent`/
Gateway/model invocation. It must fail closed for:

- missing required variables,
- unregistered feature-dynamic variables,
- unsafe user-content boundaries,
- generated suggestions not labelled as lower priority,
- output/writing language controls missing for user-facing EN-only feature prompts,
- production fallback behavior forbidden by ADR-037,
- evidence requirements missing for a mode marked runtime-required.

### Decision 4 — Intent/mode-specific output budget resolver

Output limits must resolve from intent/mode and settings/routing context. Long-form
writing modes cannot silently inherit a global balanced default if their expected
output length requires a larger profile. Resolver evidence records the selected
profile and reason.

### Decision 5 — Mode-specific adoption registry

Category-level adoption remains useful for overview scores, but runtime gates must be
mode-specific. Example: `writing/new_chapter`, `writing/extend_chapter`,
`writing/inline_suggest`, and `writing/co_author` have different output budgets,
latency tolerance, and `kb_suggested` expectations.

### Decision 6 — Audit lifecycle states

Adoption findings use these states: `identified`, `specified`, `static_verified`,
`runtime_verified`, `adopted`, `ratcheted_debt`, and `blocked`. A static PASS must
not be labelled adopted unless runtime evidence is present.

## Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|--------|-------------|------|------|----------|
| A | Static checker only | Cheap; deterministic; limited code impact | Cannot prove runtime preference/KB/budget delivery; repeats CR-03 root cause | Rejected |
| B | PromptComposer as all-in-one enforcement point | One runtime choke point | Bloats composer; mixes retrieval, validation, budget, audit, and cascade responsibilities | Rejected |
| C | Dedicated invocation contract with enrichers/validators/evidence | Runtime proof; clear module boundaries; preserves ADR-026/037 separation | Requires coordinated Core/Backend/Platform/Docs implementation | **Chosen** |

### Sustainability Rationale for Option C

- Correct in 3 months: every new AI mode can use the same evidence vocabulary.
- Coupling: Core runtime does not import Platform; Platform validates evidence and
  contracts externally.
- Simplest correct solution: narrower than an all-in-one composer and stronger than
  static checkers.
- Design intent: reviewers can see the full request-to-model path.

## Proposed Contracts / Interface Surface

### Module Boundaries

| Layer | Proposed path | Responsibility |
|-------|---------------|----------------|
| Core | `packages/core/narrare_core/ai_invocation/contracts.py` | `PromptInvocationContext`, `AdoptionPolicy`, evidence, validator/enricher/budget Protocols. |
| Core | `packages/core/narrare_core/ai_invocation/enrichers/preferences.py` | `PreferenceContextEnricher` using memory contracts. |
| Core | `packages/core/narrare_core/ai_invocation/validators/runtime.py` | `RuntimeVariableValidator` — runtime variable validation. |
| Core | `packages/core/narrare_core/ai_invocation/validators/final_prompt.py` | `FinalPromptValidator` — composed prompt validation before model call. |
| Core | `packages/core/narrare_core/ai_invocation/budgets/resolver.py` | `IntentOutputBudgetResolver` — intent/mode output budget resolver. |
| Core | `packages/core/narrare_core/ai_invocation/budgets/_types.py` | `OutputBudget`, `OutputBudgetDecision` types. |
| Backend | `apps/api/narrare/_app/dependencies.py` | DI wiring only; no business logic. |
| Backend feature modules | `apps/api/narrare/{domain}/dependencies.py` / services | Supply request IDs/settings and use service-layer contracts. |
| Platform | `scripts/architecture/adoption-registry.yaml` | Mode-specific static/runtime requirements. |
| Platform | `scripts/adoption/` and checker tests | Static-vs-runtime score/evidence gates. |
| Docs | ADR-038, INFRA-013, audit docs | SSOT links and lifecycle state documentation. |

### Contract Names Required

- `PromptInvocationContext`
- `ContextEnricher`
- `PreferenceContextEnricher`
- `RuntimeVariableValidator`
- `FinalPromptValidator`
- `IntentOutputBudgetResolver`
- `FeatureInvocationEvidence`
- `FeatureInvocationEvidenceSink`

Exact signatures are specified conceptually in ADR-038; implementation may refine
field names only through architecture re-review if module boundaries or public APIs
change materially.

## Data Model

### Pydantic Schemas

No user-facing API schema is required for P0. If runtime evidence is exposed through
an admin/debug endpoint later, that endpoint requires a separate Backend/API contract
and frontend type parity.

### SQLAlchemy Models

No DB schema is required for P0. Evidence sinks may be in-memory test sinks, structured
logs, or existing observability adapters. Persistent audit storage is P2/P3 only and
requires its own storage contract before implementation.

### Migrations Required

None for P0/P1. Any persistent evidence/audit table in P2/P3 requires an Alembic
migration and integration tests in the same implementation slice.

## Enforcement and Gates

### Static Gates

- ADR-037 prompt-surface manifest conformance remains required.
- Adoption registry entries become mode-specific where runtime obligations differ.
- New feature modes must declare static requirements and runtime evidence
  requirements in the registry/spec.
- Checkers must classify `static_verified` separately from `runtime_verified`.

### Runtime Gates

- `PreferenceContextEnricher` or approved manual-injection contract ran for modes
  requiring preferences.
- `RuntimeVariableValidator` passes before prompt composition where applicable.
- `FinalPromptValidator` passes after prompt composition and before model invocation.
- `IntentOutputBudgetResolver` returns a mode-appropriate budget decision.
- `FeatureInvocationEvidenceSink` receives evidence in tests/probes for each adopted
  feature mode.

### Audit Gates

- CR-03 items move through lifecycle states; `adopted` requires static + runtime proof.
- Ratcheted debt may not grow; each remaining item needs owner, target state, and
  target date/trigger.
- Audit files must not claim CR-03 resolved until P1–P3 exit criteria and runtime
  evidence gates pass.

### Doc Gates

- ADR-025 references ADR-038 for runtime evidence requirements.
- ADR-026 references ADR-038 for output-language/preference runtime proof while
  preserving its prompt content categories.
- Derived docs reference, not replace, CONSTRAINTS.md and ADRs.

## Migration Plan P0–P3

Each increment is complete and must pass its exit criteria before the next layer can
claim adoption progress. No increment is a skeleton.

### P0 — Runtime invocation contract and blockers

**Scope:** contracts, preference enrichment path, final prompt validation, output
budget resolver, runtime evidence sink in tests.

**Required work:**

1. Define the proposed contracts in a dedicated Core invocation module.
2. Implement/verify preference enrichment before `PromptComposer` or document
   approved manual injection per mode.
3. Add final prompt validation before model calls for targeted AI modes.
4. Add intent/mode output budget resolver for current generation/analysis intents.
5. Add runtime evidence tests for representative modes: long writing, inline
   suggest, KB interview/extract, consistency/analysis, chat.

**Exit criteria:**

- Static adoption PASS cannot be labelled adopted without runtime evidence.
- API composer DI no longer silently prevents preference adoption claims.
- Final prompt validation blocks at least missing required variables, unsafe user
  content boundaries, and missing output-language control for user-facing EN-only
  feature prompts.
- Output budget evidence records the selected intent/mode profile.

### P1 — Mode-specific registry and KB-suggested verification

**Scope:** registry/checker cleanup, ADR/docs/spec drift cleanup, `kb_suggested`
runtime proof.

**Required work:**

1. Split adoption registry requirements by mode where category-level checks hide
   runtime differences.
2. Update adoption checker output so it reports `static_verified`,
   `runtime_verified`, and `adopted` separately.
3. Verify `kb_suggested` is supplied only where quality benefit exceeds token/latency
   cost; record `provided`, `budget_rejected`, or `not_applicable` evidence.
4. Remove or reword stale documentation that implies static adoption alone is enough.

**Exit criteria:**

- Mode-level adoption report exists for AI modes with different obligations.
- `kb_suggested` has runtime evidence or explicit not-applicable rationale for each
  writing mode touched by CR-03.
- ADR-025/026/037/038 references are coherent and do not contradict prompt-language
  policy.

### P2 — KG/voice/profile SSOT and audit lifecycle hardening

**Scope:** stronger cross-feature SSOT and runtime-proof model.

**Required work:**

1. Specify Project Writing Profile and voice-profile SSOT before adding durable
   profile storage or UI.
2. Define KG/KB consistency evidence where graph traversal or voice-profile context
   is used.
3. Add audit lifecycle reporting for CR files and adoption debt.
4. Strengthen runtime proof for additional modes beyond P0 representatives.

**Exit criteria:**

- No hidden profile/voice/KG source is introduced outside an approved spec.
- Audit lifecycle state is machine-readable or deterministically reported.
- Runtime proof coverage includes every mode claiming adopted status.

### P3 — Typed manifests, generated registry, drift automation, quality metrics

**Scope:** long-term automation once P0–P2 contracts are stable.

**Required work:**

1. Introduce typed feature manifests or generated registry entries if manual registry
   maintenance becomes drift-prone.
2. Add doc-drift automation for ADR/spec/checker wording.
3. Add AI output quality metrics that connect runtime evidence to evaluation results.
4. Reassess whether evidence needs persistent storage.

**Exit criteria:**

- Registry/checker drift is automatically detected.
- Quality metrics are opt-in, privacy-safe, and tied to evaluation contracts.
- Persistent evidence, if added, has a storage/API contract and migration.

## Tests and Gates Required by Layer

### Core

- Unit tests for `PromptInvocationContext` construction and validation.
- Unit tests for `PreferenceContextEnricher` success, missing provider, missing IDs,
  and redacted evidence.
- Unit tests for `RuntimeVariableValidator` and `FinalPromptValidator` blockers.
- Unit tests for `IntentOutputBudgetResolver` per intent/mode profile.
- Agent/composer tests proving validation happens before model invocation.

### Backend

- Integration tests for DI paths that supply user/project IDs and preference provider
  data where required.
- Service tests for manual-injection exceptions if any are approved.
- Error propagation tests for validation failures; no silent success states.

### Platform

- Checker tests for static/runtime state distinction.
- Registry tests for mode-specific requirements.
- Ratchet tests proving new runtime-evidence gaps fail.
- Adoption score/report tests proving static PASS does not equal adopted.

### Docs

- Documentation review verifies ADR-025/026/037/038 and INFRA-013 use consistent
  terminology.
- Audit docs do not claim CR-03 resolved until runtime gates pass.

## Cross-Feature Coherence Analysis (RULE-22)

| Shared source | Direction | Coherence requirement |
|---------------|-----------|-----------------------|
| mem0/preferences | Memory writes → AI features read | Preference data is lower precedence than explicit author/project instructions; missing provider cannot be treated as adopted. |
| Prompt registry/templates | Prompt system writes/owns → features consume | Customizable feature prompt content stays in `core/prompts/`; runtime data is not baked into templates. |
| KB/KG context | KB/KG writes → writing/analysis/planning consume | Curated KB outranks learned memory; generated `kb_suggested` remains labelled lower priority and optional/budget-aware. |
| Project/user settings | Settings writes → invocation consumes | Output budgets, model routing, and output/writing language come from settings/context, not router constants. |
| Prompt variables | Core prompt registry owns → templates consume | New variables must be registered/classified before use; user-authored values require XML/label policy. |
| Audit registry/checkers | Platform reports → Architecture/Docs consume | Static and runtime states are separate; no docs claim adopted from static-only evidence. |

### Language Policy Coherence

- **UI i18n:** web UI strings remain en/de/fr per UI i18n rules.
- **Prompt instruction language:** new bundled feature system prompts remain EN-only by
  default per ADR-026 unless an approved localized prompt family exists.
- **Output/writing language:** controlled through `PromptContext`, Deps, settings, or
  preferences such as `writing_language`, `language`, or `explanation_language`.
- **Runtime validation:** user-facing EN-only feature prompts are valid only when
  output/writing language controls are present and validated.

### Context Precedence

When runtime sources conflict, use the established precedence: current author
instruction → explicit project writing profile/manual override → current
scene/storyboard/timeline → curated KB → learned memory/preferences → generated
suggestions. High-impact conflicts are surfaced rather than silently resolved.

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | No direct model/provider path; invocation uses approved agents/gateway/model registry. |
| RULE-02/02a | ✅ | Composer/capability/dynamic-context boundaries remain separate. |
| RULE-03 | ✅ | ADR-038 and this spec define contracts before implementation. |
| RULE-04 | ✅ | Module boundaries split contracts, enrichers, validators, budgets, evidence, and checkers. |
| RULE-05 | ✅ | Ownership table defines exact layers and proposed paths. |
| RULE-06 | ✅ | PromptComposer does not absorb unrelated responsibilities. |
| RULE-07 | ✅ | Core does not import Backend or Platform; Platform consumes reports/evidence externally. |
| RULE-08 | ✅ | Preference/memory access stays behind memory contracts. |
| RULE-09 | ✅ | Proposed public interfaces require full type annotations. |
| RULE-10 | ✅ | Layer-specific unit/integration/checker/docs gates are required. |
| RULE-11 | ✅ | Validation failures block and are recorded; silent runtime-adoption success is forbidden. |
| RULE-12 | ✅ | Service layer remains the public API for all clients. |
| RULE-13 | ✅ | Invocation contract applies to both streaming and non-streaming AI operations. |
| RULE-14 | ✅ | No DB schema change in P0/P1; P2/P3 persistence would require migration. |
| RULE-15 | ✅ | No frontend route middleware work. |
| RULE-16 | ✅ | UI i18n remains separate and unchanged. |
| RULE-17 | ✅ | Any exposed evidence/budget API requires backend/frontend contract parity. |
| RULE-18 | ✅ | Budgets/settings resolved through settings/routing context, not hardcoded router values. |
| RULE-19 | ✅ | Backend DI changes must preserve approved dependency patterns. |
| RULE-20 | ✅ | Static-only adoption is not considered complete. |
| RULE-21 | ✅ | Material implementation deviations require architecture re-review. |
| RULE-22 | ✅ | Shared preference, KB/KG, settings, variable, prompt-language, and audit semantics are explicit. |

## Definition of Done

### Architecture Gate

- [x] ADR-038 created as Proposed.
- [x] INFRA-013 spec created as planned.
- [x] ADR-025/026 cross-references updated minimally.
- [ ] User/coordinator approves implementation handoff.

### P0 Core/Backend Gate

- [ ] Contracts exist before implementation.
- [ ] Representative runtime evidence tests pass.
- [ ] Preference enrichment/manual-injection path is proven per mode.
- [ ] Final prompt validation blocks before model calls.
- [ ] Output budget resolver evidence exists.

### P1 Platform/Docs Gate

- [ ] Adoption registry/checker distinguishes mode-level static/runtime/adopted states.
- [ ] `kb_suggested` runtime delivery is verified or explicitly not applicable per mode.
- [ ] Derived docs do not imply static adoption alone is sufficient.

### P2/P3 Gate

- [ ] Profile/voice/KG SSOT specs exist before durable implementation.
- [ ] Audit lifecycle reporting is deterministic.
- [ ] Drift automation and quality metrics are privacy-safe and contract-backed.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Evidence stores raw prompt/user content | Privacy regression | Evidence schema defaults to statuses, hashes/counts, IDs, and validation outcomes only. |
| PromptComposer becomes a god object | RULE-06/RULE-02 drift | Keep enrichers, validators, and budget resolver in separate invocation modules. |
| Static PASS remains mistaken for adopted | CR-03 repeats | Checker/report vocabulary separates static/runtime/adopted states. |
| `kb_suggested` harms latency | Worse UX for inline/short modes | Mode-specific registry marks provided/budget-rejected/not-applicable with rationale. |
| Manual preference injection becomes hidden workaround | Runtime drift | Manual path requires explicit spec, tests, and evidence. |

## Open Questions

1. Should runtime evidence be test-only initially, or also emitted as structured
   observability events in P0?
2. Which component owns persistent audit state if P2/P3 requires storage: Platform
   report artifact, backend table, or observability-only timeline?
3. ~~Should `PromptInvocationContext` live under `narrare_core/invocation/` or a
    narrower `narrare_core/prompts/invocation/` package?~~ **Resolved:** Lives in
    `narrare_core/ai_invocation/` — a dedicated module, separate from both
    `prompts/` and the originally proposed `invocation/`.
4. Which writing modes should treat `kb_suggested` as quality-positive versus
   budget-rejected by default?
5. Should output-budget profiles be configured in the existing model-routing settings
   layer or a dedicated invocation budget manifest?

## Handoff Order

1. **Core** — define contracts, enrichers, validators, budget resolver, and evidence
   test sink.
2. **Backend** — wire DI/service request data and prove preference/manual injection
   path for API invocations.
3. **Platform** — update registry/scorer/checkers for mode-specific static/runtime
   states and ratchets.
4. **Docs** — update derived standards/audit lifecycle only after implementation
   details are stable.

## Status & History

- 2026-06-05 — ADR-038 and INFRA-013 created as architecture/specification for
  CR-03 AI Invocation Adoption Contract. No production implementation completed.
- 2026-06-06 — P0 implemented: Core `ai_invocation/` module with contracts,
  enrichers, validators, budget resolver, `InvocationPipeline` orchestrator,
  WritingPipeline integration (`_invocation_adapter.py`), and backend DI.
  Module path changed from spec `core/invocation/` to `core/ai_invocation/`.
  P1–P3 remain outstanding.
