# CR-08 Remediation — Configuration/Effect Drift Specification

> **Status:** historically closed 2026-06-20 as P0–P4 complete — ⚠️ the
> matrix/checker enforcement that backed this was later removed in `f8abb42c`
> (ADR-047/051/061/062 ⛔ Superseded). P0–P4 value-level work (per-value regression
> tests, token profiles, calibration, governed defaults) remains on disk; RULE-18b
> is now enforced via per-value regression tests + ADR-045 + ad-hoc audits. The
> matrix/checker artifacts cited below as enforcement evidence are deleted — see
> FIND-014 / CR-AUFG-08-15; read them as historical record.
> **Date:** 2026-06-18 (reconciled 2026-06-20 on ADR-051 acceptance; enforcement-removal annotated 2026-07-15)
> **Author:** Architecture Specialist
> **ADR:** [ADR-051](../../architecture/decisions/ADR-051-configuration-effect-adoption-contract.md) (⛔ Superseded — its matrix/checker enforcement was removed in `f8abb42c`; RULE-18b survives in CONSTRAINTS.md, enforced via per-value regression tests + ADR-045 Runtime Adoption Enforcement)
> **Source Audit:** [`_audit/results/content-review/cr-08-hardcoded-values.md`](../../../_audit/results/content-review/cr-08-hardcoded-values.md)
> **Formal Findings:** FIND-001, FIND-012, FIND-013 (FIND-014 / CR-AUFG-08-15 records the subsequent matrix/checker removal)
>
> ⚠️ **Enforcement-artifact caveat:** Several artifacts referenced in the body —
> `configuration-adoption-matrix.yaml`, `scripts/check_configuration_matrix.py`,
> `scripts/governance/`, and `tests/unit/scripts/governance/test_configuration_matrix_review_gate.py` —
> were deliberately removed in `f8abb42c` (ADR-047/051/061/062 ⛔ Superseded; see
> FIND-014 / CR-AUFG-08-15). Treat all matrix/checker references below as historical
> record. RULE-18b enforcement now runs via per-value regression tests + ADR-045 +
> ad-hoc audits (review file as SSOT).

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

**Design (historical, 2026-06-20):** ADR-051 was the contract: every material
configuration value needs a Configuration Adoption Matrix row or an explicit
governed-default classification with tests and rationale. **That design was
subsequently superseded** — ADR-051 is ⛔ Superseded and its matrix/checker were
removed in `f8abb42c` (ADR-047/051/061/062 ⛔ Superseded). The CR-08 value-level
work (per-value regression tests, token profiles, calibration, governed defaults)
remains on disk; RULE-18b is enforced via per-value regression tests + ADR-045 +
ad-hoc audits. The phase evidence recorded below should be read as historical
record (the matrix/checker artifacts are deleted; see FIND-014 / CR-AUFG-08-15).

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
**Implementation policy:** [`CR-08 P1 Policy — Token Profiles, Model Limits, and Suitability`](../../architecture/governance/cr-08-p1-token-limits-and-suitability-policy.md).

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-03 | Core + Backend + Frontend | Unify token profile vocabulary (`quick`, `balanced`, `long_texts`, `comprehensive`, `custom`) and remove/stabilize stale `conservative`. | One typed profile enum/contract; backend schemas and frontend types match; `custom` maps to raw output limit semantics; contract tests prove parity. |
| CR-AUFG-08-10 / FIND-013 | Backend + Frontend + Platform | Token Settings UI/API contract parity: slider max, profile visibility, custom semantics. | UI hard caps match backend/core or are explicitly labelled UX-protective; tests compare API schema/profile vocabulary to frontend types/constants. |
| CR-AUFG-08-07 | Core + Backend + Frontend | Model-limit calibration with `models.dev`/cache metadata. | Known too-high limits cap or reject per policy; too-low/unknown/offline states produce warning labels/evidence; no UI implies calibration when source is stale/offline. |
| CR-AUFG-08-11 | Architecture + Backend + Frontend | Model suitability policy: advisory vs warning vs hard block. | Policy table exists per intent tier; UI/API expose warnings; hard blocks limited to impossible/unsafe calls; tests cover unknown/offline/provider-too-small cases. |

#### P1 Architecture Decisions

- **Token profile vocabulary:** The public vocabulary is exactly `quick`, `balanced`,
  `long_texts`, `comprehensive`, `custom`. The authoritative contract lives in Core
  (`packages/core/narrare_core/llm/token_profiles.py`) and is consumed by Backend;
  Frontend constants/types must prove parity through contract tests.
- **`conservative`:** Removed from the public contract. New writes are invalid;
  existing persisted values are normalized to `balanced` at the Backend compatibility
  boundary and must never be emitted to clients.
- **`custom`:** Manual raw `output_limit` mode. It has no preset output limit entry;
  runtime calibration still caps to known provider ceilings.
- **Slider/API max:** `131072` is the absolute API hard max. `16000` is only the
  UX recommended slider range (`comprehensive`) and may remain only with explicit
  labelling plus a custom input path up to the effective hard/model max.
- **Calibration:** Known model ceilings cap at runtime and surface effective-limit
  warnings. Stale/offline/unknown metadata states must be labelled and must not imply
  calibration.
- **Suitability:** Advisory/warning/hard-block severity is evaluated per intent
  profile. Hard blocks are limited to impossible/unsafe calls: unusable provider/model,
  non-text model, known output ceiling below the minimum viable floor, or insufficient
  context for required input plus minimum output.

#### P1 Implementation-Ready Handoff

| Layer | Required work | Evidence required before P1 closure |
|---|---|---|
| Core | Add `packages/core/narrare_core/llm/token_profiles.py`; refactor `packages/core/narrare_core/llm/model_config.py`, `packages/core/narrare_core/llm/run_limits.py`, and `packages/core/narrare_core/llm/intent_profiles.py` to consume it; add typed calibration result and suitability evaluator. | Unit tests for exact vocabulary/presets, custom raw semantics, conservative legacy normalization, calibration statuses, suitability severities. |
| Backend | Derive token-limit schemas from Core vocabulary; reject new `conservative`; normalize persisted legacy values; expose profile/cap/calibration/suitability metadata through service/API responses. | Schema tests, service tests, API integration tests for profile parity, custom semantics, warnings, and provider-too-small cases. |
| Frontend | Remove `conservative`; consume/prove metadata parity; display custom raw limit controls and calibration/suitability warnings; remove 16k-as-hard-max semantics. | UI tests for exact profile options, >16k custom path, stale/offline/unknown warnings, provider-too-small warning/block display. |
| Platform | Add cross-layer contract tests comparing Core/Backend/Frontend profile and cap metadata; keep matrix findings open until evidence exists. | CI-blocking tests fail on independent profile/cap drift and on missing warning/block evidence. |
| Docs | Update user/developer status only after implementation evidence. | P1 tasks are marked resolved only with implementation-on-disk, enforcement tests, and cross-layer evidence. |

#### P1 Implementation Evidence (2026-06-20)

P1 is implementation-evidence complete across Core, Backend, Frontend, and Platform.
ADR-051 was subsequently accepted on 2026-06-20; this P1 evidence now contributes
to the resolved CR-08 AUFG set. Later P2/P3/P4 evidence is recorded in the
sections below.

| Task | Status | Evidence |
|---|---|---|
| CR-AUFG-08-03 | Implemented + enforced | Core vocabulary in `packages/core/narrare_core/llm/token_profiles.py`; Backend validators derive from Core and reject new `conservative` while normalizing legacy reads; Frontend `packages/web/lib/token-profiles.ts` removes `conservative`. Evidence: `tests/unit/core/llm/test_token_profiles.py`, `tests/unit/api/settings/test_cr08_p1_token_profile_contract.py`, `tests/unit/api/settings/test_cr08_p1_cross_layer_contract.py`, `packages/web/lib/__tests__/token-profiles.test.ts`. |
| CR-AUFG-08-10 / FIND-013 | Implemented + enforced | Backend metadata exposes public profiles, preset limits, absolute max `131072`, and UX recommended max `16000`; Frontend labels the 16k slider as recommended and supports custom values above 16k. Evidence: `tests/unit/api/settings/test_cr08_p1_token_limit_metadata.py`, `tests/unit/api/settings/test_cr08_p1_cross_layer_contract.py`, `packages/web/components/studio/settings/__tests__/AiTab.test.tsx`, `packages/web/components/studio/editor/__tests__/TokenSettings.test.tsx`. |
| CR-AUFG-08-07 | Implemented + enforced | Core typed calibration statuses (`known_fresh`, `known_stale`, `unknown_model`, `offline_no_cache`, `invalid_metadata`) feed Backend metadata and Frontend warnings. Evidence: `packages/core/narrare_core/llm/model_calibration.py`, `tests/unit/core/llm/test_model_limit_calibration.py`, `tests/unit/api/settings/test_cr08_p1_token_limit_metadata.py`, `packages/web/components/studio/settings/__tests__/TokenMetadataWarnings.test.tsx`. |
| CR-AUFG-08-11 | Implemented + enforced | Core suitability evaluator produces advisory/warning/hard-block severities; Backend exposes suitability metadata; Frontend renders the messages. Evidence: `packages/core/narrare_core/llm/model_suitability.py`, `tests/unit/core/llm/test_model_suitability.py`, `tests/unit/api/settings/test_cr08_p1_token_limit_metadata.py`, `packages/web/components/studio/settings/__tests__/TokenMetadataWarnings.test.tsx`. |
| P1 Platform gate | Implemented + enforced | Configuration matrix P1 rows contain concrete enforcement and cross-layer evidence; Platform parity tests fail on independent vocabulary/cap drift. Evidence: `tests/unit/scripts/governance/test_configuration_matrix_p1.py`; reported gate results: targeted P1 suite PASS and `just check` PASS after security dependency updates. |

#### P0 Commit Evidence

P0 is committed as `5769eaf2`. That slice delivered the Configuration Adoption
Matrix baseline plus runtime evidence for FIND-001/CR-AUFG-08-01 and
FIND-012/CR-AUFG-08-02. Do not use the commit alone as closure proof; the durable
closure evidence is the matrix row evidence and the tests referenced there.

### P2 — Operator Defaults, Catalog Governance, and System Resolvers

**Owner order:** Architecture → Core → Backend → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-04 | Backend + Core | Replace inline suggest raw `60` with named low-latency cap or immutable UX cap. | No raw dependency-factory `max_tokens=60`; cap has named resolver/default and tests, or immutable governed-default rationale with tests. |
| CR-AUFG-08-05 | Architecture + Backend + Frontend | Decide consistency caps layer. | Caps are either user/project settings with API/UI parity or operator-only settings with no misleading UI/API implication; tests verify chosen layer. |
| CR-AUFG-08-06 | Backend + Core | Setup fallback catalogs/Ollama defaults behind catalog/settings abstraction. | Fallback list has source/freshness labels; Ollama default URL sourced once; setup UI/API marks stale/offline fallback explicitly. |
| CR-AUFG-08-08 | Backend + Core | Named system/background model resolver for wiki/background tasks. | `build_system_default_config` or successor uses typed system-model resolver; no two-branch category string logic as the policy boundary; background tasks have tests. |
| CR-AUFG-08-12 | Platform + Backend + Core | Operator/default governance for catalog timeout, OpenRouter cap, `models.dev` TTL, wiki retry delays, cost fallback staleness. | Operator defaults are centralized, documented, and tested as operator defaults or governed code defaults with review triggers. |

#### P2 Implementation Evidence (2026-06-20)

P2 is implementation/enforcement complete; the per-value code work and
fail-if-changed tests below are real and survive. (The evidence rows also cite
"Matrix entry" identifiers — the Configuration Adoption Matrix itself was removed
in `f8abb42c`; treat those identifiers as historical labels, see the header
caveat.) Evidence landed across commits `138307c7` and `1aafad08`:

| Task | Status | Evidence |
|---|---|---|
| CR-AUFG-08-04 | Implemented + enforced | Inline suggest cap is a named governed default (`SUGGEST_MAX_TOKENS = 60`) with latency rationale and fail-if-changed tests. Matrix entry: `inline_suggest_cap`. |
| CR-AUFG-08-05 | Implemented + enforced | Consistency caps are classified as operator defaults; `max_selection_words` is removed from the API response so the UI/API no longer implies user control. Matrix entry: `consistency_caps`. |
| CR-AUFG-08-06 | Implemented + enforced | Ollama default URL is centralized at `apps/api/narrare/setup/constants.py`; setup call sites consume the constant. Matrix entry: `setup_fallback_catalogs`. |
| CR-AUFG-08-08 | Implemented + enforced | `SystemModelCategory` replaces raw category string branching for background/system defaults, with resolver tests. Matrix entry: `system_background_model_defaults`. |
| CR-AUFG-08-12 | Implemented + enforced | Operator defaults for catalog timeout, catalog cap, models.dev cache/fetch, retry delays, and cost fallback rates are named and covered by fail-if-changed tests. Matrix entry: `operator_default_governance`. |

### P3 — Governed Defaults Manifest and Long-Tail Defaults

**Owner order:** Architecture → Core → Backend → Frontend → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-13 | Architecture + Platform | Governed defaults manifest for long-tail defaults. | Embedding thresholds/limits, name dedup caps, SSE/connect retry defaults, WebSocket reconnect defaults, and test-only defaults are classified with owner, rationale, tests, review trigger. |
| Long-tail implementation | Layer owners | Add/adjust tests only where defaults are intentionally retained. | A retained default has a failing-if-changed-without-review test or explicit contract test proving override path exists. |

#### P3 Implementation Evidence (2026-06-20)

P3 is implementation/enforcement complete with the governed-defaults manifest and
matrix rows synchronized. Evidence landed across commits `138307c7` and `1aafad08`:

| Task | Status | Evidence |
|---|---|---|
| CR-AUFG-08-13 | Implemented + enforced | `docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md` classifies embedding search defaults, name dedup context caps, and SSE/connect/retry defaults with owners, rationale, review triggers, override paths, discovery paths, and concrete test paths. Matrix entries: `governed_defaults_manifest`, `embedding_threshold_search_limit`, `name_dedup_context_cap`, `sse_connect_retry_defaults`. |

### P4 — Documentation, Status Taxonomy, and Audit Template Hardening

**Owner order:** Architecture → Platform → Docs.

| Task | Owner | Scope | Definition of Done |
|---|---|---|---|
| CR-AUFG-08-14 | Docs + Platform | Status/doc taxonomy corrections. | SET-005 and CURRENT_STATE distinguish cascade/storage from runtime-effect adoption; no “every setting takes effect” wording remains until evidence exists. |
| Audit-template gate | Platform + Docs | Update review/audit templates and governance health. | Future content reviews must include classification for every material value; unclassified P0/P1 findings fail governance health once baseline is set. |

#### P4 Implementation Evidence (2026-06-20)

P4 was implementation/enforcement complete for status taxonomy and future-audit
hardening (2026-06-20). ⚠️ The ADR-051 matrix/checker enforcement that closed P4
was subsequently removed in `f8abb42c` (ADR-047/051/061/062 ⛔ Superseded; see
FIND-014 / CR-AUFG-08-15) — see the table rows below. The status-taxonomy and
audit-template reconciliation itself stands; ongoing RULE-18b enforcement runs via
per-value regression tests + ADR-045 + ad-hoc audits:

| Task | Status | Evidence |
|---|---|---|
| CR-AUFG-08-14 | Historically implemented; enforcement since removed | SET-005, CURRENT_STATE, the AUFG registry, this remediation spec, testing standards, and the CR-08 audit prompt template record phase-complete runtime-effect evidence. ⚠️ The `configuration-adoption-matrix.yaml` and ADR-051 enforcement backing this row were removed in `f8abb42c` (ADR-047/051/061/062 ⛔ Superseded); RULE-18b now runs via per-value regression tests + ADR-045 + ad-hoc audits. |
| Audit-template gate | Historically implemented; checker since removed | ⚠️ The checker artifacts cited here — `scripts/check_configuration_matrix.py`, `scripts/governance/configuration_matrix.py`, `scripts/governance/_matrix_review_gate.py`, and `tests/unit/scripts/governance/test_configuration_matrix_review_gate.py` — were deleted in `f8abb42c` (ADR-047/051/061/062 ⛔ Superseded; see FIND-014 / CR-AUFG-08-15). The structured-marker convention survives in the CR-08 content-review prompt as a recommended (no longer checker-gated) convention. |

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

No CR-08 item was left unclassified at the original 2026-06-20 closure. (The
Configuration Adoption Matrix referenced above was removed in `f8abb42c`; new
material values are now governed by per-value regression tests + ADR-045 + ad-hoc
audits, not a matrix row — see the header caveat.)

---

## Module Boundaries

| Layer | Files / modules | Responsibility |
|---|---|---|
| Architecture | Candidate ADR-051; this spec | Policy, lifecycle, classification, handoff. |
| Core | `packages/core/narrare_core/llm/`, `packages/core/narrare_core/ai_invocation/`, `packages/core/narrare_core/writing/context_assembler.py`, `packages/core/narrare_core/context/budget.py` | Runtime limit enforcement, output/profile types, tier budget application; no app imports. |
| Backend | `apps/api/narrare/settings/`, `apps/api/narrare/writing/`, `apps/api/narrare/consistency/`, `apps/api/narrare/setup/`, `apps/api/narrare/_app/settings_model.py` | Settings persistence/resolution, DI wiring, API schemas, system resolver, setup catalog abstraction. |
| Frontend | `packages/web/components/studio/settings/`, settings API types/constants | User controls, labels, warnings, profile/cap parity; no independent config vocabulary. |
| Platform | `scripts/architecture/`, `scripts/governance/`, tests | Matrix/checker, contract tests, governance health integration. |
| Docs | `docs/_shared/CURRENT_STATE.md`, SET-005, testing standards, audit templates | Truthful status and future audit coverage. |

---

## RULE-XX Compliance

| Rule | Status | Evidence required by this spec |
|---|---|---|
| RULE-01b | ✅ | LLM limit enforcement occurs at approved agent/ModelRegistry boundary. |
| RULE-02/02a/02b | ✅ | No prompt fallback changes in this spec; PromptComposer boundaries remain intact. |
| RULE-03 | ✅ | ADR-051 (accepted) and this spec define the contracts before implementation; resolution is complete with implementation + enforcement + cross-layer evidence. |
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
  FIND-013 closed with UI/API/core parity evidence; model calibration and suitability
  warning/block policy tested. Documentation-only policy does not close P1.
- **P2:** Complete — operator defaults and setup catalogs have named/default governance
  evidence and tests; system/background resolver removes local category-string policy
  branches. See matrix P2 entries and commits `138307c7` / `1aafad08`.
- **P3:** Complete — long-tail defaults are governed defaults with rationale/tests/review
  triggers or implemented settings; no tracked P3 default remains unclassified. See
  matrix P3 entries and the governed-defaults manifest.
- **P4:** Complete — SET-005/CURRENT_STATE/testing/audit docs use truthful status
  taxonomy; governance health detects future structured, unclassified P0/P1
  configuration/effect findings.

**Lifecycle resolution (updated 2026-07-15):** ADR-051 was accepted on 2026-06-20
and RULE-18b (Configuration Effect Integrity) was elevated to CONSTRAINTS.md.
**ADR-051 and its matrix/checker enforcement were subsequently superseded and
removed in `f8abb42c`** (ADR-047/051/061/062 ⛔ Superseded; see FIND-014 /
CR-AUFG-08-15). The CR-08 value-level implementation (per-value regression tests,
token profiles, calibration, governed defaults) remains on disk. RULE-18b survives
in CONSTRAINTS.md and is enforced via per-value regression tests + ADR-045
(Runtime Adoption Enforcement) + ad-hoc audits (review file as SSOT). The earlier
"resolved / in effect / ongoing enforcement" framing is superseded by this update.
