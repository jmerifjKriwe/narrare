# ADR-076 — CURRENT_STATE.md Volatility Policy (SSOT-Facts Gate)

> **Status:** ✅ Accepted (active — CI-blocking + pre-commit-enforced)
> **Date:** 2026-08-03
> **Deciders:** Architecture Specialist, User
> **Supersedes:** — (does **not** supersede ADR-047; it adopts a narrow policy that pre-existed ADR-047 and survived its withdrawal — see Context)
> **Related:** ADR-047 (🗄️ Deprecated — governance toolchain withdrawn via FIND-014; this ADR carves out the one surviving checker), ADR-041 (doc/gate/registry drift checkers — sibling SSOT gates), CONSTRAINTS.md §8 (SSOT hierarchy)

---

## Context

`docs/_shared/CURRENT_STATE.md` is the human-readable handoff document for the
current session/build state. Because it is hand-authored and high-traffic, it
has a recurring failure mode: **volatile generated count claims** — numbers
that go stale the moment a test is added, an ADR is created, or the knowledge
graph is rebuilt (e.g. "8341 backend tests", "KG has 5124 nodes", "65 ADRs",
"risk score 3.2"). Such claims are false controls: they read as authoritative
but decay silently, violating the §7 finding-lifecycle lesson
("documented ≠ implemented ≠ enforced") at the documentation layer.

A checker already exists and is **actively enforced**:
`scripts/check_current_state_facts.py` — a single-file regex pass that:

- rejects volatile generated count claims (test-file counts, KG node/edge/risk
  counts, ADR/feature/question/exception inventory counts, adoption-debt/health
  scores); and
- requires links or commands for fresh authoritative facts.

**Enforcement surface (verified 2026-08-03):**

- **CI:** blocking step in the `architecture` job (`.github/workflows/ci.yml`) —
  no `continue-on-error`.
- **pre-commit:** `ssot-consistency` hook, `always_run: true`
  (`.pre-commit-config.yaml`).

### Historical note — why a new ADR

The checker **pre-existed ADR-047** (ADR-047 §"Affected Files and Checkers"
listed it under "Existing artifacts to integrate", not "New proposed
artifacts"). ADR-047's actual scope — the central AUFG registry, review-finding
coverage checker, and governance-health aggregation
(`check_governance_health.py`, `scripts/governance/`) — was **withdrawn via
FIND-014 / commit `f8abb42c` (2026-07-08)** and ADR-047 is correctly 🗄️
Deprecated. The volatility checker survived that purge (only 1 line of it
changed in `f8abb42c`), but its policy was **never formally specified in any
ADR**. The checker's docstring and several derived docs loosely attributed the
policy to "ADR-047" — a false attribution, because ADR-047 never articulated
the volatility rules. Referencing a deprecated ADR as the origin of an active,
CI-blocking gate is itself a §7 violation (enforcement exists, but its
documentation points at a withdrawn decision).

This ADR closes that gap: it gives the surviving policy a proper, active
governance home, separate from ADR-047's withdrawn toolchain.

---

## Root Cause Analysis

### Symptom

An active, CI-blocking + pre-commit-enforced gate
(`check_current_state_facts.py`) cited a deprecated ADR (ADR-047) as its policy
origin, and the policy itself was never specified in any decision record.

### Why #1 — Why did the gate cite a deprecated ADR?

Because the checker's docstring (added in `b6f400b6`, "coverage-ramp and DX
tooling files") and several derived docs (added in `1c5b206e`) reused "ADR-047"
as a shorthand for "the SSOT check", without verifying that ADR-047 actually
specified the volatility policy. It did not — it only listed the checker as an
input to its (now-withdrawn) aggregation layer.

### Why #2 — Why was the policy never specified?

Because the checker was created as a pragmatic single-file gate and grew
organically; its policy lived only in its source patterns, not in a decision
record. When ADR-047's toolchain was withdrawn, nobody carved out a successor
ADR for the one checker that survived.

### Architectural design response

Specify the policy in its own focused ADR with status ✅ Accepted/active, so
the enforcement surface (CI-blocking + pre-commit) is documented honestly and
the gate has a legitimate SSOT origin.

---

## Decision Drivers

- **§7 finding-lifecycle discipline:** enforcement must be reflected as
  enforcement, not pointed at a withdrawn decision.
- **SSOT hierarchy (CONSTRAINTS.md §8):** `ADR-*.md` files are the authoritative
  source for architecture decisions; an active gate needs an active ADR.
- **No false controls (FIND-014 lesson):** do not let a doc reference imply an
  enforcement backing that the referenced (deprecated) ADR no longer provides.
- **RULE-06 (one responsibility):** this ADR governs exactly one policy
  (CURRENT_STATE.md volatility), not the broader (withdrawn) governance thesis.

---

## Options Considered

### Option A — Un-deprecate ADR-047 and narrow its scope

Rewrite ADR-047's status to "Scope narrowed: P0-P5 toolchain withdrawn, SSOT
volatility check retained."

**Pros:**

- Existing "ADR-047" references stay valid; no repointing needed.

**Cons:**

- Rewrites history: ADR-047's deprecation was **intentional and broad**
  (FIND-014 withdrew ~60 files including the AUFG registry and
  `check_governance_health.py`). Re-activating the ADR contradicts the
  established record in `CURRENT_STATE.md`, `CONSTRAINTS.md` §8, and the cr-08
  remediation.
- ADR-047 never specified the volatility policy anyway, so "narrowing" it would
  require injecting new content into a withdrawn decision — confusing the
  historical record with current policy.

### Option B — Successor ADR (ADR-076) for the volatility policy

Create a focused ADR that specifies the policy, marks it ✅ active, and
repoints all active-gate references (checker docstring, pre-commit comment,
README, deployment-guide, §8 enforcement) to it. ADR-047 stays 🗄️ Deprecated.

**Pros:**

- Honest separation: withdrawn toolchain (ADR-047) vs. active narrow gate
  (ADR-076). Each ADR's status reflects reality.
- Gives the policy a legitimate SSOT home it never had.
- Mirrors how the drift checkers already work: `check_doc_drift.py` /
  `check_gate_drift.py` are ADR-041 artifacts that survived independently; this
  ADR does the same for the volatility checker.

**Cons:**

- More files to touch (new ADR + repoint references). Acceptable: one-time
  repointing is the correct price of an honest record.

### Option C — Status quo + disclaimer notes

Leave ADR-047 deprecated, keep references, add a disclaimer at each that
"ADR-047 is deprecated but the SSOT check survived as an independent gate."

**Pros:**

- Least change.

**Cons:**

- Perpetuates the exact anti-pattern (documented ≠ enforced / false control)
  that FIND-014 was filed against. An active CI-blocking gate would still cite a
  deprecated ADR as its origin, now with an apology note. Not sustainable.

---

## Decision

**We choose Option B.** ADR-076 is the canonical, active governance home for
the `CURRENT_STATE.md` volatility policy enforced by
`check_current_state_facts.py`. ADR-047 remains Deprecated for its actual
(withdrawn) scope; ADR-076 does **not** supersede it — it adopts a narrow policy
that pre-existed ADR-047 and survived its withdrawal.

---

## Rationale

The cleanest record is one where each ADR's status matches reality. ADR-047's
governance toolchain is gone (FIND-014); pretending any part of it is "still
active under ADR-047" re-creates the false-control class of bug. The volatility
checker is real, enforced, and useful — it deserves its own honest ADR rather
than borrowing the legitimacy of a withdrawn one. This is the same pattern
already established for the surviving drift checkers (ADR-041): when ADR-047's
aggregation layer was withdrawn, the individual first-class checkers it
consumed kept their original homes and remained CI-blocking on their own merit.

---

## Consequences

**Positive:**

- The active gate has a legitimate SSOT origin matching its enforcement surface.
- §7 compliance: documentation now reflects implementation + enforcement.
- ADR-047's deprecation is internally consistent (no "partly active" ambiguity).

**Negative / Tradeoffs:**

- One more ADR to maintain. Mitigated: the ADR is narrow and points at a stable
  checker.
- References were repointed once (in the change that introduced this ADR).

**Constraints introduced:**

- `CURRENT_STATE.md` MAY NOT contain volatile generated count claims; fresh
  authoritative facts MUST be backed by a link or command.
- Adding a new forbidden-pattern category requires updating both the checker
  (`scripts/check_current_state_facts.py`) and noting it in this ADR's
  Implementation Notes.

---

## Implementation Notes

- **Checker:** `scripts/check_current_state_facts.py` (single-file regex pass;
  exit 0 = pass, exit 1 = violations found).
- **Forbidden categories (authoritative in the checker source):**
  - Knowledge Graph node/edge/risk counts.
  - Backend/frontend test-file counts.
  - ADR/feature/question/exception inventory counts.
  - Adoption-debt/health-score counts.
- **Required-authority rule:** fresh authoritative facts need a link or
  reproducible command, not a bare number.
- **CI:** blocking step in the `architecture` job (no `continue-on-error`).
- **pre-commit:** `ssot-consistency` hook, `always_run: true`.
- **Reference in code/docs:** cite `ADR-076` (not ADR-047) for this policy.

---

## Candidate RULE-XX Assessment

Candidate wording: *"CURRENT_STATE.md must not contain volatile generated count
claims; authoritative facts require a link or command."*

**Decision:** Do **not** add a RULE-XX yet — mirror ADR-047's §"Candidate
RULE-24 Assessment" reasoning. Keep the policy ADR-backed first; elevate to
`CONSTRAINTS.md` only after the mechanics are proven stable across multiple
review cycles and the user approves. (See "Folge-Punkte" in the handoff.)

---

## Review Trigger

- After the next full review cycle in which the gate runs.
- When a new category of volatile claim appears that the checker should reject.
- If the project adopts a typed/structured CURRENT_STATE format that makes the
  regex pass obsolete.

---

## Compliance Checklist

- [x] Root cause documented with at least two "Why" steps.
- [x] Minimum two options evaluated (three considered).
- [x] No workaround: the policy gets a real ADR, not a disclaimer.
- [x] RULE-06 respected: one policy per ADR.
- [x] CONSTRAINTS.md §8 respected: `ADR-*.md` remains authoritative for
      decisions; this ADR does not redefine the SSOT hierarchy.
- [x] §7 respected: enforcement (CI-blocking + pre-commit) is documented as such.
