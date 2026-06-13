# ADR-047 — Governance Drift Automation for Review Findings and AUFG Lifecycle

> **Status:** 🔄 Proposed
> **Date:** 2026-06-13
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-028, ADR-041, ADR-045, CONSTRAINTS.md §8, AUFG-02-14, AUFG-03-11, AUFG-05-07..10

---

## Context

Review-05 found actionable release/security/observability risks that were described in
the narrative but not represented as AUFGs or accepted-risk/enhancement decisions:

- CORS and rate-limiting were not fully audited.
- CSRF token validation was not explicitly decided for state-changing endpoints.
- Secret scanning was not configured as a dedicated CI gate.
- OTel setup failures were warnings, with no explicit Health-severity policy.

This is not an isolated documentation omission. `CONSTRAINTS.md` §8 defines the SSOT
hierarchy and notes that SSOT enforcement is currently manual, with future CI drift
detection planned as AUFG-NEW-01. ADR-041 already added doc-drift, registry-drift and
checker-terminology infrastructure, but it does not enforce the lifecycle rule that every
review finding must become either an AUFG, an accepted risk, or an explicitly accepted
enhancement.

The Coordinator requested “ADR-044 Exploration”. ADR-044 is already occupied by the
Staged Multi-Agent Consistency Pipeline, so this governance-drift proposal is assigned
the next available ADR number: ADR-047.

---

## Root Cause Analysis

### Symptom

Review findings can remain in prose, checklists, or roadmap notes without an AUFG,
accepted-risk decision, owner, exit criterion, or CI-visible lifecycle.

### Why #1 — Why do findings remain only in prose?

Because Review files do not have a machine-enforced coverage gate that cross-checks
“risk/finding/open point” sections against `## Aufgaben` entries or explicit accepted
risk/enhancement tables.

### Why #2 — Why is the existing governance not enough?

Because current governance checks validate important but narrower relationships:
ADR/spec references, registry drift, current-state facts, and gate drift. They do not
model review findings as first-class lifecycle records. The SSOT hierarchy is defined,
but review-finding coverage is still manually inspected by the Architecture Specialist.

### Architectural design response

Introduce a governance lifecycle contract for review findings:

1. A finding is not “handled” until it has exactly one lifecycle state:
   `aufg`, `accepted_risk`, `accepted_enhancement`, `resolved`, or `not_applicable`.
2. AUFGs are centrally indexed with owner, priority, source review line/reference,
   acceptance criteria, dependencies, and exit evidence.
3. CI detects untracked findings and stale lifecycle entries before release governance
   claims are published.

---

## Decision Drivers

- **SSOT discipline:** `CONSTRAINTS.md` §8 remains authoritative for documentation
  hierarchy; derived docs must not silently drift.
- **No workaround governance:** A prose note is not a lifecycle. Risks need AUFG,
  accepted-risk rationale, or explicit non-applicability.
- **RULE-04/RULE-06:** New checker code must be modular by responsibility; no large
  “god checker” accumulating all governance concerns.
- **RULE-07:** Platform/governance scripts read files and structured reports; they do
  not import application runtime internals.
- **RULE-10/RULE-11:** Governance failures must be testable and visible; missing coverage
  must not fail silently.
- **ADR-041 compatibility:** Reuse doc-drift/gate-drift patterns where they fit, but do
  not overload an existing checker with unrelated review-finding lifecycle logic.
- **Incremental correctness:** Each step must be complete in itself: registry first,
  warning-only report second, blocking gate only after baseline and owner/exit metadata
  exist.

---

## Options Considered

### Option A — Status quo plus manual Architecture Review

The Architecture Specialist continues manually checking Review files and adds missing
AUFGs during handoff.

**Pros:**
- No new tooling or registry format.
- Flexible judgment for nuanced findings.

**Cons:**
- Preserves the root cause: findings can be missed until a later audit.
- No CI visibility, no baseline, no trend tracking.
- Manual review does not scale with more review files and governance documents.

### Option B — Central AUFG Registry plus Review-Finding Gate

Create a central AUFG registry and a checker that verifies every Review finding has an
AUFG/accepted-risk/enhancement lifecycle entry.

**Pros:**
- Directly addresses missing AUFG coverage.
- Provides a human-readable tracking surface for Coordinator and Specialists.
- Can start warning-only and ratchet to blocking once baseline is clean.

**Cons:**
- Does not cover SSOT and CI checker drift beyond review findings.
- Markdown parsing can be fragile unless the registry format is strict.
- Requires maintenance discipline for source line references and status updates.

### Option C — Governance Health Checker plus AUFG Registry plus SSOT Drift Checks

Add a dedicated governance-health layer that combines:

1. A central AUFG registry.
2. Review-finding coverage checks.
3. Existing SSOT/doc/gate/current-state drift check outputs.
4. Status-bearing health report for governance (`PASS`, `GOVERNED_DEBT`, `FAIL`).

**Pros:**
- Addresses the actual root cause: missing cross-validation across reviews, AUFGs,
  SSOT docs, CI gates, and checker outputs.
- Builds on ADR-041 and ADR-045 status-bearing semantics instead of inventing a separate
  governance vocabulary.
- Keeps individual checkers single-purpose while providing one coordinator-facing report.
- Allows AUFG-NEW-01 to become concrete and measurable.

**Cons:**
- More design surface than Option B.
- Requires a baseline/grace-period process before becoming blocking.
- Needs careful ownership to avoid duplicating `check_doc_drift.py`, `check_gate_drift.py`,
  and `check_current_state_facts.py`.

### Option D — Full Issue-Tracker Migration

Move all AUFGs and review findings into GitHub Issues or another issue tracker, making
the tracker the lifecycle source of truth.

**Pros:**
- Strong lifecycle UX: owners, labels, due dates, queries, notifications.
- Avoids parsing Markdown review files for task state.

**Cons:**
- Narrare currently keeps architecture governance in-repo; moving lifecycle to GitHub
  creates an external SSOT for architecture status.
- Offline/local-first workflows lose visibility without network access.
- Requires API access in CI and complicates reproducibility.
- Does not solve SSOT/doc/gate drift unless in-repo checks still exist.

---

## Decision

**We choose Option C: a Governance Health Checker plus central AUFG registry plus SSOT
drift integration.**

Option B is the minimum useful slice and should be the first implementation step, but
the long-term architecture must be Option C. Review-05’s missing AUFGs show that a task
registry alone is not enough; governance needs a cross-document health view that proves
Review findings, AUFG lifecycle, SSOT claims, and CI gates agree.

---

## Rationale

The fundamental failure mode is semantic drift across governance artifacts. ADR-041
already proved that typed/checkable drift detection is the correct pattern for adoption
registries and docs. ADR-045 introduced truthful status-bearing semantics for adoption
gates. Governance findings need the same treatment: a known debt can be governed, but it
cannot be invisible or described as complete.

Issue-tracker migration is rejected for now because it moves the governance SSOT outside
the repository. The project’s architecture constitution, ADRs, feature specs, review
files, and CI scripts are all in-repo; review-finding lifecycle must remain reproducible
from the repository as well.

---

## Consequences

**Positive:**
- Every review finding gets an explicit lifecycle state.
- Missing AUFGs become visible immediately, not in the next manual audit.
- Governance health can distinguish `PASS`, `GOVERNED_DEBT`, and `FAIL` rather than
  collapsing known debt into a green claim.
- AUFG-NEW-01 becomes concrete: not generic “future drift detection”, but a defined
  review/AUFG/SSOT/CI cross-validation system.

**Negative / Tradeoffs:**
- New governance artifacts require upkeep.
- Initial checker must run warning-only until current reviews are baselined.
- False positives are possible if review prose is too free-form; registry source links
  must be precise.

**Constraints introduced:**
- Review findings may not remain only in prose once this ADR is accepted and the baseline
  is established.
- New accepted risks require owner, rationale, compensating controls, expiry/review date,
  and source finding reference.
- New accepted enhancements require rationale and review trigger; they are not silent
  backlog items.

---

## Candidate RULE-24 Assessment

Candidate wording: **“Every review finding must be either actionable or explicitly
accepted.”**

**Decision:** Do **not** add RULE-24 yet.

**Reason:** The principle is correct, but it should first be implemented as an ADR-backed
governance policy and checker. A new RULE-XX belongs in `CONSTRAINTS.md` only after the
mechanics are proven, baseline is clean, and the user approves elevating it to the
architecture constitution. Prematurely adding RULE-24 would create another manual rule
before the automation exists.

**Review trigger for RULE-24:** Revisit after the Governance Health Checker has run for
one complete review cycle with zero untracked findings or after any release review finds
another untracked high/medium risk.

---

## AUFG-NEW-01 Integration

`CONSTRAINTS.md` §8 currently says CI drift detection between authoritative and derived
sources is planned as AUFG-NEW-01. ADR-047 **concretizes** AUFG-NEW-01 rather than
replacing ADR-041:

- ADR-041 remains the architecture for doc-drift, registry-drift and quality-metric
  checks.
- ADR-047 defines the missing review-finding lifecycle and governance-health aggregation.
- After ADR-047 is accepted, `CONSTRAINTS.md` §8 should replace the vague AUFG-NEW-01
  note with a reference to the concrete Governance Health Gate and its status.

---

## AUFG Registry Location

**Chosen location:** `docs/architecture/governance/aufg-registry.md`

**Why not `_audit/aufg-registry.md`:** `_audit/` is the source/evidence area for review
outputs. It should remain a record of what was found. The registry is a long-lived
architecture governance artifact that spans reviews, ADRs, Specs, CI gates and accepted
risk decisions. Therefore it belongs under `docs/architecture/governance/`.

**Registry requirements:**

- One entry per AUFG with ID, title, source review, source line/reference, priority,
  area, status, owner role, dependencies, acceptance criteria, Definition of Done and
  exit evidence.
- Separate tables for `accepted_risk` and `accepted_enhancement` entries.
- No duplication of full RULE-XX text; references point to `CONSTRAINTS.md` or ADRs.

---

## Implementation Plan

### Phase 1 — Registry and Baseline (Architecture + Platform)

1. Create `docs/architecture/governance/aufg-registry.md` with strict entry schema.
2. Seed it from current Review 01–05 AUFGs and accepted enhancements.
3. Mark known historical gaps as `resolved`, `not_applicable`, `accepted_risk`, or
   `accepted_enhancement` with source references.

### Phase 2 — Review-Finding Coverage Checker (Platform)

1. Add modular checker components, for example:
   - `scripts/governance/aufg_registry.py`
   - `scripts/governance/review_findings.py`
   - `scripts/governance/governance_health.py`
   - `scripts/check_governance_health.py`
2. Detect candidate findings from Review sections such as `Offene Punkte`, `Schwächen`,
   unchecked checklist items, and explicit `Risiko` statements.
3. Verify each candidate has a matching AUFG/accepted-risk/enhancement/not-applicable
   entry.
4. Output `PASS`, `GOVERNED_DEBT`, or `FAIL` with source file and line references.

### Phase 3 — SSOT/Gate Aggregation (Platform + Docs)

1. Aggregate outputs from:
   - `scripts/check_doc_drift.py`
   - `scripts/check_gate_drift.py`
   - `scripts/check_current_state_facts.py`
   - `scripts/check_registry_drift.py`
   - new review-finding coverage checker.
2. Add a concise governance health summary for CI and Coordinator handoff.
3. Keep individual checkers single-purpose; the aggregator must not duplicate their
   internal logic.

### Phase 4 — CI Ratchet and Documentation Gate (Platform + Docs)

1. Run warning-only for one baseline cycle.
2. Require owner/exit/review-date metadata for all governed debt.
3. Make new untracked high/medium findings blocking.
4. Update `CONSTRAINTS.md` §8 only after user approval and ADR acceptance.

---

## Affected Files and Checkers

**New proposed artifacts:**

- `docs/architecture/governance/aufg-registry.md`
- `scripts/governance/aufg_registry.py`
- `scripts/governance/review_findings.py`
- `scripts/governance/governance_health.py`
- `scripts/check_governance_health.py`

**Existing artifacts to integrate:**

- `_audit/results/technical-review/review-*.md`
- `docs/_shared/CONSTRAINTS.md` §8
- `docs/_shared/CURRENT_STATE.md`
- `docs/architecture/decisions/INDEX.md`
- `.github/workflows/ci.yml`
- `scripts/check_doc_drift.py`
- `scripts/check_gate_drift.py`
- `scripts/check_current_state_facts.py`
- `scripts/check_registry_drift.py`

---

## Review Trigger

- After the next full technical review cycle.
- When any Review file introduces a High/Medium risk without AUFG or accepted-risk entry.
- When `CONSTRAINTS.md` §8 is updated from manual/future enforcement to CI-backed
  enforcement.
- When AUFG count exceeds what is maintainable in Markdown tables, reconsider a typed
  YAML/JSON registry.

---

## Compliance Checklist

- [x] Root cause documented with at least two “Why” steps.
- [x] Minimum three options evaluated.
- [x] No workaround or “track later” without lifecycle state.
- [x] RULE-04/RULE-06 considered for checker modularization.
- [x] RULE-07 preserved: governance scripts read files/reports, not runtime internals.
- [x] CONSTRAINTS.md §8 remains SSOT; this ADR does not redefine the hierarchy.
- [x] New RULE-24 assessed but not introduced without user approval.
- [x] AUFG-NEW-01 concretized into an implementation path.
