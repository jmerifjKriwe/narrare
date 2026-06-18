# CR-08 Remediation — Configuration/Effect Drift Specification

> **Status:** planned — remediation specification ready; candidate ADR-051 remains proposed
> **Date:** 2026-06-18
> **Author:** Architecture Specialist
> **Candidate ADR:** [ADR-051](../../architecture/decisions/ADR-051-configuration-effect-adoption-contract.md) (Proposed; must be accepted or superseded before CR-AUFG-08 tasks can be resolved)
> **Source Audit:** [`_audit/results/content-review/cr-08-hardcoded-values.md`](../../../_audit/results/content-review/cr-08-hardcoded-values.md)
> **Formal Findings:** FIND-001, FIND-012, FIND-013

---

## Scope

### In Scope

- Close CR-08 without preserving false controls or silent technical debt.
- Define P0–P4 implementation phases and owners in layer order.
- Classify every CR-08 item as formal finding, implementation task, governed default,
  covered-by-existing, not-applicable, or accepted risk with owner/exit criteria.
- Add the Configuration Adoption Matrix requirement for settings/defaults.
- Correct status language around SET-005 until runtime effect adoption is proven.

### Out of Scope

- Production code implementation by Architecture.
- Running tests or modifying runtime code in this slice.
- New external dependencies.

---

## Root Cause

**Symptom:** Configuration values are exposed, documented, or resolved in one layer while
the runtime boundary continues using a different default or cannot prove the effect.

**Why #1:** Feature completion was assessed at the storage/API/resolver layer, not at the
effect boundary. “The setting exists” was allowed to imply “the model/context/catalog call
uses it.”

**Why #2:** Gates were too narrow. RULE-18 and testing guidance caught router provider/model
hardcoding, but not cross-layer configuration adoption. Existing adoption/evidence gates
tracked AI invocation surfaces, not every setting source → resolver → consumer chain.

**Design:** Use candidate ADR-051 as the proposed contract: every material
configuration value needs a Configuration Adoption Matrix row or an explicit
governed-default classification with tests and rationale. This spec does not make
ADR-051 accepted or in effect; task closure still requires ADR-051 to be accepted
or superseded by an equivalent contract.

---

## Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|---|---|---|---|---|
| A | Patch each constant locally | Fast per symptom | Recreates drift; no common prevention gate | Rejected |
| B | Expose every default in UI/API | Maximum configurability | Misclassifies operator/platform defaults as user settings; does not prove runtime effect | Rejected |
| C | Configuration Adoption Matrix + governed defaults | Fixes root cause; strengthens existing cascades; no false controls | Requires Platform/docs governance work | **Chosen** |

---

## Phase Plan and Owners

### P0 — Configuration Adoption Gate and Existing High-Risk False Controls

**Owner order:** Architecture → Core → Backend → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-09 | Architecture + Platform | Create Configuration Adoption Matrix schema/checker baseline. | Matrix exists; all CR-08 values classified; checker/test fixture fails on an exposed setting without runtime consumer/evidence. |
| CR-AUFG-08-01 | Core | Enforce resolved output limits at `ModelRegistry.run()`/`stream()`/agent boundary. | `run` and `stream` pass effective limits to pydantic-ai/provider settings; tests prove changed profile/custom limit changes model-call settings; evidence joins same invocation. |
| CR-AUFG-08-02 | Core + Backend | Wire `TokenLimitOverrides.tier_percentages` into `WritingContextAssembler`. | Changing `kb_suggested`/`immediate` setting changes emitted tier budgets/context metadata; API factories pass resolved settings; tests cover defaults and override. |

### P1 — Cross-Layer Vocabulary, UI/API Drift, and Model Suitability

**Owner order:** Architecture → Core → Backend → Frontend → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-03 | Core + Backend + Frontend | Unify token profile vocabulary (`quick`, `balanced`, `long_texts`, `comprehensive`, `custom`) and remove/stabilize stale `conservative`. | One typed profile enum/contract; backend schemas and frontend types match; `custom` maps to raw output limit semantics; contract tests prove parity. |
| CR-AUFG-08-10 / FIND-013 | Backend + Frontend + Platform | Token Settings UI/API contract parity: slider max, profile visibility, custom semantics. | UI hard caps match backend/core or are explicitly labelled UX-protective; tests compare API schema/profile vocabulary to frontend types/constants. |
| CR-AUFG-08-07 | Core + Backend + Frontend | Model-limit calibration with `models.dev`/cache metadata. | Known too-high limits cap or reject per policy; too-low/unknown/offline states produce warning labels/evidence; no UI implies calibration when source is stale/offline. |
| CR-AUFG-08-11 | Architecture + Backend + Frontend | Model suitability policy: advisory vs warning vs hard block. | Policy table exists per intent tier; UI/API expose warnings; hard blocks limited to impossible/unsafe calls; tests cover unknown/offline/provider-too-small cases. |

### P2 — Operator Defaults, Catalog Governance, and System Resolvers

**Owner order:** Architecture → Core → Backend → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-04 | Backend + Core | Replace inline suggest raw `60` with named low-latency cap or immutable UX cap. | No raw dependency-factory `max_tokens=60`; cap has named resolver/default and tests, or immutable governed-default rationale with tests. |
| CR-AUFG-08-05 | Architecture + Backend + Frontend | Decide consistency caps layer. | Caps are either user/project settings with API/UI parity or operator-only settings with no misleading UI/API implication; tests verify chosen layer. |
| CR-AUFG-08-06 | Backend + Core | Setup fallback catalogs/Ollama defaults behind catalog/settings abstraction. | Fallback list has source/freshness labels; Ollama default URL sourced once; setup UI/API marks stale/offline fallback explicitly. |
| CR-AUFG-08-08 | Backend + Core | Named system/background model resolver for wiki/background tasks. | `build_system_default_config` or successor uses typed system-model resolver; no two-branch category string logic as the policy boundary; background tasks have tests. |
| CR-AUFG-08-12 | Platform + Backend + Core | Operator/default governance for catalog timeout, OpenRouter cap, `models.dev` TTL, wiki retry delays, cost fallback staleness. | Operator defaults are centralized, documented, and tested as operator defaults or governed code defaults with review triggers. |

### P3 — Governed Defaults Manifest and Long-Tail Defaults

**Owner order:** Architecture → Core → Backend → Frontend → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-13 | Architecture + Platform | Governed defaults manifest for long-tail defaults. | Embedding thresholds/limits, name dedup caps, SSE/connect retry defaults, WebSocket reconnect defaults, and test-only defaults are classified with owner, rationale, tests, review trigger. |
| Long-tail implementation | Layer owners | Add/adjust tests only where defaults are intentionally retained. | A retained default has a failing-if-changed-without-review test or explicit contract test proving override path exists. |

### P4 — Documentation, Status Taxonomy, and Audit Template Hardening

**Owner order:** Architecture → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-14 | Docs + Platform | Status/doc taxonomy corrections. | SET-005 and CURRENT_STATE distinguish cascade/storage from runtime-effect adoption; no “every setting takes effect” wording remains until evidence exists. |
| Audit-template gate | Platform + Docs | Update review/audit templates and governance health. | Future content reviews must include classification for every material value; unclassified P0/P1 findings fail governance health once baseline is set. |

---

## Classification of CR-08 Items

| CR-08 item | Classification | Lifecycle |
|---|---|---|
| Output limits not enforced at model boundary | Formal finding | FIND-001 + CR-AUFG-08-01 (P0) |
| `tier_percentages` exposed but not consumed | Formal finding | FIND-012 + CR-AUFG-08-02 (P0) |
| Token profile vocabulary drift (`custom`, `comprehensive`, `conservative`) | Implementation task | CR-AUFG-08-03 (P1) |
| Inline suggest `max_tokens=60` | Implementation task or governed default | CR-AUFG-08-04 (P2); must choose named cap or immutable UX cap with tests |
| Consistency caps (`max_chapter_tokens`, `max_kb_entries`, `max_selection_words`) | Implementation task | CR-AUFG-08-05 (P2) |
| Setup fallback model catalogs and repeated Ollama URL | Implementation task | CR-AUFG-08-06 (P2) |
| Model-limit calibration/warnings | Implementation task | CR-AUFG-08-07 + CR-AUFG-08-11 (P1) |
| System/background model defaults | Implementation task | CR-AUFG-08-08 (P2) |
| Configuration Adoption Matrix | Implementation task / prevention gate | CR-AUFG-08-09 (P0) |
| Token Settings UI slider/API/profile drift | Formal finding | FIND-013 + CR-AUFG-08-10 (P1) |
| Model suitability advisory-only behavior | Implementation task | CR-AUFG-08-11 (P1) |
| Catalog timeout `10.0`, OpenRouter cap `30`, models.dev TTL `86400`, wiki retry delays | Operator/governed defaults | CR-AUFG-08-12 (P2); not user settings unless future spec proves need |
| `PROFILE_OUTPUT_LIMITS` numeric defaults | Governed defaults | Keep as code defaults only after profile contract tests and provider-ceiling calibration |
| `ResolvedModelConfig.max_tokens=4096` fallback | Operator/default fallback | Covered by CR-AUFG-08-01/07; must not be only enforcement path |
| Provider inference prefixes | Governed default utility | Accept only for dev/debug inference; runtime resolver must use explicit provider |
| Cost-rate fallback defaults | Operator/default fallback | Covered by CR-AUFG-08-12; source/freshness labels required |
| Embedding threshold `0.7`, search limit `20` | Governed default with override path | CR-AUFG-08-13; method-parameter overrides are acceptable if tested |
| Name dedup page size/context cap | Governed default pending scale trigger | CR-AUFG-08-13; add scale review trigger and tests for cap behavior |
| SSE/connect timeout and AI operation retry defaults | Governed UI/runtime defaults | CR-AUFG-08-13; hook option override and UX rationale tests required |
| WebSocket idle timeout/retry cascade | Adopted / covered existing | Keep adopted only if matrix row points to Settings → service → handler tests |
| Default model per user-facing feature | Adopted / covered existing | `ModelRoutingResolverImpl` cascade; model suitability warnings still P1 |
| mem0 defaults | Operator/default fallback | Covered by Settings/mem0 config; freshness/suitability only if provider model list changes |
| Feature flags/kill switches listed in CR-08 | Mostly covered existing | Retain per current config paths; inline fallback prompt paths are governed by CR-02/CR-04, not CR-08 duplicate |

No CR-08 item is left unclassified. If implementation discovers a new material value, it
must be added to the matrix before the phase can close.

---

## Module Boundaries

| Layer | Files / modules | Responsibility |
|---|---|---|
| Architecture | Candidate ADR-051; this spec; `docs/architecture/governance/aufg-registry.md` | Policy, lifecycle, classification, handoff. |
| Core | `packages/core/narrare_core/llm/`, `ai_invocation/`, `writing/context_assembler.py`, `context/budget.py` | Runtime limit enforcement, output/profile types, tier budget application; no app imports. |
| Backend | `apps/api/narrare/settings/`, `writing/`, `consistency/`, `setup/`, `_app/settings_model.py` | Settings persistence/resolution, DI wiring, API schemas, system resolver, setup catalog abstraction. |
| Frontend | `packages/web/components/studio/settings/`, settings API types/constants | User controls, labels, warnings, profile/cap parity; no independent config vocabulary. |
| Platform | `scripts/architecture/`, `scripts/governance/`, tests | Matrix/checker, contract tests, governance health integration. |
| Docs | `docs/_shared/CURRENT_STATE.md`, SET-005, testing standards, audit templates | Truthful status and future audit coverage. |

---

## RULE-XX Compliance

| Rule | Status | Evidence required by this spec |
|---|---|---|
| RULE-01b | ✅ | LLM limit enforcement occurs at approved agent/ModelRegistry boundary. |
| RULE-02/02a/02b | ✅ | No prompt fallback changes in this spec; PromptComposer boundaries remain intact. |
| RULE-03 | ✅ | Candidate ADR-051 and this spec define proposed contracts before implementation; resolution requires ADR acceptance or supersession. |
| RULE-04 | ✅ | Gateway/settings/catalog/checker changes must split by responsibility, not compress. |
| RULE-05/RULE-06 | ✅ | Module boundaries table assigns one responsibility per file/module. |
| RULE-07 | ✅ | Core has no Backend/Frontend/Platform imports; Platform reads artifacts/evidence. |
| RULE-08 | ✅ | Provider/model catalogs are adapters/abstractions, not direct scattered SDK calls. |
| RULE-09 | ✅ | Public contracts/enums typed; no `Any` in public settings/profile APIs. |
| RULE-10 | ✅ | Each phase requires unit/integration/contract/checker evidence. |
| RULE-11 | ✅ | Unknown/stale/offline config states warn or fail; no silent calibrated claims. |
| RULE-12 | ✅ | Service layer remains only public API; WebUI/MCP/A2A/CLI share semantics. |
| RULE-13 | ✅ | Run/stream limit enforcement shares one contract. |
| RULE-17 | ✅ | Frontend/backend profile and schema parity enforced in P1. |
| RULE-18 | ✅ | Existing router focus is preserved; ADR-051 proposes broader effect-integrity gate. |
| RULE-20 | ✅ | False controls are prohibited; documentation alone cannot close tasks. |
| RULE-22 | ✅ | Cross-feature settings vocabulary and model-limit semantics are checked. |

---

## Definition of Done by Phase

- **P0:** Matrix/gate baseline exists; FIND-001 and FIND-012 have implementation-on-disk,
  enforcement, and cross-feature evidence; no “resolved” claim without runtime tests.
- **P1:** Core/backend/frontend token profile contract is single-source and tested;
  FIND-013 closed with UI/API/core parity evidence; model suitability warnings policy tested.
- **P2:** Operator defaults and setup catalogs have resolver/freshness/source labels and
  tests; system/background resolver removes local category-string policy branches.
- **P3:** Long-tail defaults are all governed defaults with rationale/tests/review triggers
  or implemented settings; no untracked default remains.
- **P4:** SET-005/CURRENT_STATE/testing/audit docs use truthful status taxonomy; governance
  health detects future unclassified configuration/effect findings.
