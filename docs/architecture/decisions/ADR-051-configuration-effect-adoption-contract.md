# ADR-051 — Configuration Effect Adoption Contract

> **Status:** ⏸ Superseded (governance toolchain removed 2026-07-08)
> **Date:** 2026-06-18
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-038, ADR-041, ADR-045, ADR-047, SET-005, CR-08, FIND-001, FIND-012, FIND-013, CONSTRAINTS.md RULE-03/RULE-04/RULE-06/RULE-07/RULE-10/RULE-11/RULE-12/RULE-13/RULE-18/RULE-18b/RULE-20/RULE-22

---

## Context

CR-08 found that Narrare has much of the right configuration vocabulary: user/project
model routing, `TokenLimitsService`, provider catalog/cache paths, model-limit metadata,
and PromptComposer/agent boundaries. The remaining problem is not ordinary “hardcoded
strings in routers”. It is **configuration/effect drift**: a value can be exposed,
stored, resolved, or documented in one layer while the runtime boundary that users expect
to affect still consumes a default, a stale vocabulary entry, or an uncalibrated fallback.

This is wider than the current RULE-18 text, which focuses on router/provider/model
hardcoding. CR-08 requires a system-level adoption contract for configuration values.

---

## Root Cause Analysis

### Symptom

Controls and settings can look implemented because UI/API/storage/resolver surfaces exist,
while production AI calls or context assembly do not consume the resolved value.

### Why #1 — Why did false controls exist despite documentation?

Because implementation evidence was accepted at the source/resolver layer. A setting being
stored or returned from an API was treated as equivalent to the runtime effect being
applied.

### Why #2 — Why did gates not prevent this?

Because existing gates check narrower slices: RULE-18 tests inspect router factories for
hardcoded provider/model strings, adoption checks prove prompt/invocation artifacts, and
feature docs describe intended cascades. No blocking gate requires a **source → resolver →
runtime consumer → enforcement test** chain for every user-facing or operator-facing
configuration value.

### Design response

Configuration is not “implemented” until its effect is adopted at the runtime boundary and
protected by regression evidence. Documentation may describe intent, but adoption requires
implementation-on-disk, enforcement, and cross-feature integration evidence.

---

## Decision Drivers

- **RULE-03:** Resolver and runtime-consumer contracts must be specified before changes.
- **RULE-04/RULE-06:** Remediation must modularize settings/gateway/catalog/checker code;
  no cosmetic line squeezing.
- **RULE-07:** Core remains HTTP/DB agnostic; Backend owns settings persistence/DI;
  Platform reads manifests/evidence without importing runtime internals.
- **RULE-10/RULE-11:** Missing, unknown, stale, too-low, or too-high configuration states
  require tests and explicit warnings/errors; never silent success.
- **RULE-12/RULE-13:** WebUI, MCP, A2A, CLI, REST, SSE, and WebSocket must share service
  layer configuration semantics.
- **RULE-18:** Must evolve from “no hardcoded router config” to configuration-effect
  integrity across all runtime boundaries.
- **RULE-20:** UI/API controls that do not affect runtime are half-implementations.
- **RULE-22:** Settings shared by writing, consistency, setup, model routing, catalog,
  memory, and frontend require cross-feature coherence.

---

## Options Considered

### Option A — Patch each CR-08 constant locally

Fix output limits, tier percentages, setup catalogs, and UI sliders with local code changes
and targeted tests.

**Pros:** Smallest apparent scope; quick per-finding progress.

**Cons:** Preserves the root cause. Each setting can drift again because no shared adoption
definition or gate requires runtime-effect proof.

### Option B — Move every configurable value into user/project settings

Expose every numeric/string default in the UI/API and treat configurability as solved.

**Pros:** Maximum user control; simple mental model.

**Cons:** Category error. Operator/platform values such as catalog timeouts, cache TTLs,
fallback freshness labels, and retry backoff are not ordinary author preferences. This
would bloat UI and still would not prove runtime consumption.

### Option C — Configuration Effect Adoption Contract plus governed defaults

Require every material configuration value to be classified and, when applicable, listed
in a Configuration Adoption Matrix: source, resolver/service, runtime consumer, effect
semantics, fallback/diagnostic behavior, and regression evidence. Remaining code defaults
are acceptable only when classified as governed defaults with tests and rationale.

**Pros:** Directly fixes configuration/effect drift; strengthens existing cascades;
separates user/project/operator/default layers; creates a reusable gate for future work.

**Cons:** Requires a new governance artifact, checker/test work, and status cleanup.

**Decision:** Choose **Option C**.

---

## Decision

Narrare adopts a **Configuration Effect Adoption Contract** for all material settings,
defaults, and derived configuration values.

A configuration value may be called implemented only when it has exactly one lifecycle
classification:

| State | Meaning |
|---|---|
| `adopted` | Source, resolver, runtime consumer, fallback semantics, and regression evidence exist. |
| `governed_default` | Code default is intentionally not user/project configurable; rationale, owner, tests, and review trigger exist. |
| `operator_default` | Deployment/operator value lives in `Settings`/env/catalog abstraction and has freshness/diagnostic semantics where stale/unknown. |
| `formal_finding` | Material false-control or cross-layer drift requires tracked remediation. |
| `covered_by_existing` | Explicitly delegated to another ADR/AUFG/FIND with no duplicate task. |
| `not_applicable` | Configuration-effect concern does not apply; rationale recorded. |

Every user-facing or operator-facing configurable value must appear in a Configuration
Adoption Matrix before it can be marked resolved.

---

## Configuration Adoption Matrix Contract

Each row must record:

| Field | Required meaning |
|---|---|
| `setting_id` | Stable name used by docs, tests, and evidence. |
| `classification` | `user`, `project`, `operator`, `runtime-derived`, `governed_default`, or `test-only`. |
| `source` | UI/API/DB/env/catalog/code default path. |
| `resolver/service` | Single resolver that normalizes the value. |
| `runtime_consumer` | Function/class that applies the value to model call, context assembly, catalog fetch, retry, streaming, etc. |
| `effect_semantics` | What observable runtime behavior changes when the value changes. |
| `fallback_policy` | Fail-fast, warning, cap, offline/unknown label, or last-resort default. |
| `enforcement_evidence` | Unit/integration/contract/checker evidence that blocks regressions. |
| `cross_layer_evidence` | Proof that frontend/backend/core/platform vocabulary agrees when applicable. |

---

## RULE-18b · Configuration Effect Integrity (Elevated)

On acceptance of this ADR (2026-06-20), the candidate sub-rule was elevated to
the authoritative constraints as **RULE-18b** in `docs/_shared/CONSTRAINTS.md`:

> **Configuration Effect Integrity.** A configurable value must not be exposed, stored,
> resolved, or documented as user/project/operator-controllable unless the resolved value
> is consumed at the runtime boundary it claims to affect and regression evidence proves
> that changing the value changes the effect or emits the documented warning/error.

The elevation review trigger is satisfied: CR-08 P0/P1 are complete, the
configuration-adoption checker (`scripts/check_configuration_matrix.py`) was at
acceptance a CI-blocking gate (`.github/workflows/ci.yml` architecture job,
`just check-configuration-matrix`, `scripts/run_checks.py`), and no CR-08 value
was unclassified (25/25 matrix `expected_setting_ids`, 0 violations — verified
PASS). *(Historical — that checker and matrix were removed in `f8abb42c`; see
the Acceptance Record superseded note below.)* Derived context
(`constraints/rules.md`, `standards/architecture-rules.md`,
`standards/tier1-compact-rules.md`) was synced to reference RULE-18b without
reproducing it, per the SSOT hierarchy (CONSTRAINTS.md §8).

---

## Implementation Notes

The implementation-ready remediation spec is
[`docs/features/remediation/cr-08-configuration-effect-drift.md`](../../features/remediation/cr-08-configuration-effect-drift.md).

The implementation must strengthen existing components rather than add local
special-case constants:

- `TokenLimitsService` remains the user/project/operator token-limit resolver.
- `ModelRoutingResolverImpl` remains the model routing cascade for user-facing calls.
- Provider catalog/cache code owns model freshness/source labels and offline states.
- `PromptComposer`/agent/LLM boundaries remain the AI invocation boundary; output budgets
  are enforced through the Core LLM runtime contracts from ADR-045.
- Platform gates consume manifests/evidence and do not import application runtime modules.

---

## Sustainability and Regression Gates

This remains correct in three months because every new configurable value must either:

1. enter the Configuration Adoption Matrix with runtime-effect tests,
2. be classified as a governed default with tests/rationale/review trigger, or
3. be rejected as a false control.

Required gates after implementation:

- Configuration adoption checker: no user/operator-facing value without matrix coverage.
- Runtime-effect regression tests for output limits, tier percentages, model calibration,
  catalog fallback labels, and UI/API vocabulary parity.
- Contract tests for frontend/backend/core token-profile vocabulary.
- Governance health integration so unclassified CR-08 findings cannot remain prose-only.
- Doc-drift check that status claims distinguish “cascade exists” from “runtime effect
  adopted”.

---

## Acceptance Record

> **⛔ Superseded (2026-07-08).** This acceptance record describes the state at
> acceptance (2026-06-20) and is retained as accurate history. The
> Configuration Adoption Matrix, `scripts/check_configuration_matrix.py`,
> `scripts/governance/` (including `_matrix_review_gate.py`), and the associated
> CI gates were **deliberately removed** in commit `f8abb42c`. The artifacts
> cited as evidence below **no longer exist on disk**; the `check-configuration-matrix`
> / review-finding-coverage gates do not run. ADR-051's *decisions* remain
> superseded — RULE-18b the principle survives in `CONSTRAINTS.md`, now enforced
> via per-value regression tests + ADR-045 + ad-hoc audits (see CONSTRAINTS.md
> RULE-18b "Enforcement boundary"). Do not treat the evidence table below as live.

**Accepted: 2026-06-20** — promoted from Proposed based on implementation +
enforcement evidence on disk, not documentation alone. Per
`architectural-discipline.md` §7 ("documented ≠ implemented"; a `resolved` /
`Accepted` claim requires implementation **and** enforcement), acceptance was
blocked until both existed. They now do.

### Implementation and Enforcement Evidence

| Requirement | Evidence |
|---|---|
| Configuration Adoption Matrix | `docs/architecture/governance/configuration-adoption-matrix.yaml` — 25 expected `setting_ids`, 25 entries, 0 violations. |
| CI-blocking checker | `scripts/check_configuration_matrix.py`, wired in `.github/workflows/ci.yml` (architecture job), `just check-configuration-matrix`, and `scripts/run_checks.py`. Verified PASS (exit 0) on acceptance. |
| Review-finding coverage gate | `scripts/governance/_matrix_review_gate.py` (`validate_review_finding_matrix_coverage`) — enforces that future structured material P0/P1 `[category: configuration-effect]` findings are referenced by a matrix entry. |
| P0 evidence | Commit `5769eaf2` — FIND-001 / CR-AUFG-08-01 output-limit enforcement at the model boundary; FIND-012 / CR-AUFG-08-02 `tier_percentages` consumption; matrix baseline CR-AUFG-08-09. |
| P1 evidence | Core/Backend/Frontend/Platform evidence for CR-AUFG-08-03/07/10/11 (token-profile vocabulary, model-limit calibration, model-suitability policy, UI/API parity — FIND-013). |
| P2/P3 evidence | Commits `138307c7`, `1aafad08` — operator defaults, setup-catalog/Ollama-URL centralization, typed `SystemModelCategory`, governed-defaults manifest. |
| P4 evidence | Commit `c49d971f` — review-classification gate + docs/audit-template reconciliation. |
| RULE-18b elevation | Candidate sub-rule elevated to `CONSTRAINTS.md` RULE-18b on acceptance; derived context synced. |

### Why Accept (not Supersede)

Option C directly addresses the CR-08 root cause (configuration/effect drift: a
value exposed/resolved without runtime-effect proof). The contract, the matrix,
and the blocking gate are all implemented and enforced. No architectural flaw in
the Option C design was found that would warrant a superseding contract;
supersession is reserved for decisions that prove wrong in practice.

---

## Review Trigger

> **2026-06-20 — Accepted.** The first trigger fired: CR-08 P0–P4 remediation is
> complete with implementation/enforcement evidence on disk, and Platform
> implemented the configuration-adoption checker (`scripts/check_configuration_matrix.py`,
> CI-blocking). RULE-18b was elevated to `CONSTRAINTS.md` on acceptance. The
> remaining triggers below stay in force for future re-review.

- When CR-08 P0/P1 remediation is complete and Platform implements the first
  configuration-adoption checker. *(fired 2026-06-20 — ADR accepted)*
- When RULE-18 is next amended. *(RULE-18b sub-rule added 2026-06-20 on acceptance)*
- When a future audit finds a user-visible setting whose runtime effect is not proven.
- When new provider/catalog/model-limit sources are added.
