# ADR-061 — Configuration Adoption Matrix Effect-Integrity Hardening (P1 + P2)

> **Status:** 🔄 Proposed
> **Date:** 2026-07-01
> **Deciders:** Architecture Specialist (recommendation; awaits Coordinator + User approval)
> **Supersedes:** —
> **Related:** ADR-051 (Configuration Effect Adoption Contract / RULE-18b), ADR-060 (Retry False-Control Resolution — the triggering instance), AUFG-01-01, CONSTRAINTS.md RULE-18b / RULE-22

---

## Context

ADR-051 established the Configuration Adoption Matrix and the checker
`scripts/check_configuration_matrix.py` (CI-blocking) to enforce RULE-18b. Review-01
(2026-07-01) proved that **two structural gaps in that checker allowed a false control to
ship as `adopted`**:

- **RC1 — checker-blindness (presence ≠ truth).**
  `scripts/governance/configuration_matrix.py::validate_matrix` (Rules 6/7/8) checks that
  `runtime_consumer` and `enforcement_evidence` are **non-empty strings**. It does not
  verify that the `runtime_consumer` string names a real code location that actually
  consumes the resolved value, nor that the cited `enforcement_evidence` test exercises
  the setting. The `websocket_idle_retry_cascade` entry cited
  `runtime_consumer: "WritingSessionHandler"` and `enforcement_evidence:
  "test_ws_handler.py"` and PASSED — while neither referenced the two `retry_*` settings
  the entry also claimed. The gate validated the form of the claim, not its truth.

- **RC2 — aggregation defeats per-setting integrity.**
  The matrix has no one-setting-per-row rule. `websocket_idle_retry_cascade` aggregated
  three settings (`ws_idle_timeout_seconds`, `retry_max_attempts`, `retry_base_delay`)
  under one `setting_id`. A single real runtime consumer + one evidence path then
  satisfied the entire row, letting two false controls inherit an `adopted` label.
  RULE-18b is phrased per **value** ("a configurable value … consumed at the runtime
  boundary it claims to affect"), but enforcement operated per **entry** with no
  per-setting granularity.

ADR-060 resolves the specific `retry_*` instance. This ADR closes the **class** of
defect so it cannot recur for any future setting.

---

## Decision Drivers

- **RULE-18b:** effect integrity must be enforceable per setting, not per aggregate row.
- **RULE-22 (Cross-Feature Coherence):** governance claims must be coherent and
  checkable across the matrix, code, and tests.
- **Architectural discipline §7 ("documented ≠ implemented"; green check covers only the
  layer it inspects):** the matrix checker currently inspects field presence; it must
  inspect field truth against the code graph.
- **RULE-04 / RULE-06 / RULE-07:** the checker must stay modular, single-purpose, and
  must not import application runtime internals — it reads manifests and (optionally)
  graph/AST data, per the existing Platform governance pattern (ADR-051, ADR-047).
- **Incremental correctness:** each hardening step is independently shippable
  (warning-only baseline → blocking ratchet).

---

## Options Considered

### Option A — Status quo: trust the matrix fields (no change)

Keep validating only field presence/vocabulary.

**Pros:** No new tooling.

**Cons:** Preserves RC1/RC2 exactly — the defect recurs. Rejected.

### Option B — Per-setting effect-integrity checker + aggregation prohibition

Extend the matrix governance so that (1) every entry maps to exactly one setting, and
(2) the checker verifies, against the code graph (or a documented evidence manifest),
that each entry's `runtime_consumer` actually references the resolved value at a real
call site, and that the cited evidence genuinely covers that setting.

**Pros:** Directly closes RC1 (truth, not presence) and RC2 (one setting per row);
reusable for every future setting; builds on the existing graph/governance infrastructure.

**Cons:** New checker surface; graph-grounded verification needs a baseline/grace period;
some runtime consumers are indirect (DI, async generators) and may require a declared
evidence-manifest fallback when pure graph resolution is ambiguous.

### Option C — Move the entire matrix into the code (annotations / decorators)

Replace the YAML matrix with in-code `@config_effect(...)` decorators on the runtime
consumer, derived from the source.

**Pros:** Single source of truth inside the code; impossible to drift from the consumer.

**Cons:** Over-engineered for the current need; forces a settings-vocabulary change across
Core/Backend; couples governance metadata into runtime code (violates RULE-07 spirit for
governance tooling); high blast radius for a checker-hardening goal. Rejected for now.

---

## Decision

**We choose Option B.** Two first-class, complementary measures:

### P2 — Aggregation prohibition (one setting per row)

- A matrix entry's `setting_id` MUST name exactly **one** setting. An entry MAY NOT
  aggregate multiple distinct settings (e.g. a timeout + a retry count + a backoff) under
  one id.
- The checker rejects any entry whose `source`, `runtime_consumer`, or
  `effect_semantics` text enumerates more than one distinct setting, or whose
  `setting_id` contains a plural/cascade compound (e.g. `*_cascade`, `*_retry_*` naming
  two unrelated concerns). A controlled allowlist permits legitimately atomic compound
  names with a `composite_rationale` only when the settings are genuinely inseparable
  (rare; each requires Architecture approval).
- This makes RULE-18b **per-entry enforceable**: one row = one setting = one runtime
  consumer = one evidence path.

### P1 — Per-setting effect-integrity verification (presence AND truth)

- For every `user` / `project` / `adopted` entry, the checker verifies that the
  `runtime_consumer` references a **real** code location that consumes the resolved
  value. Verification strategy (chosen at implementation, may combine):
  1. **Graph-grounded** (preferred where unambiguous): resolve the consumer symbol via
     the code graph and confirm the resolved setting value reaches it (data-flow or
     call-site check). This is P6 ("graph-grounded adopted proof") in its first concrete
     form — see Deferred section.
  2. **Evidence-manifest fallback** (required for indirect/DI/async-generator consumers
     that the graph cannot statically prove): a machine-readable evidence record that
     binds the `setting_id` to (a) the exact call site that applies it and (b) the named
     test that proves changing the value changes behavior. The checker asserts the
     manifest entry exists and that the named test file/symbol exists.
- The cited `enforcement_evidence` MUST reference a test that exercises **this setting**,
  not a sibling. When the evidence manifest is used, it records the setting→test binding
  explicitly so a test covering only a sibling setting no longer satisfies the row.

### Enforcement phasing

1. **P2 (aggregation prohibition)** ships first as **blocking** — it is a structural
   matrix rule with no ambiguity (the `websocket_idle_retry_cascade` split in ADR-060
   clears the only existing violation).
2. **P1 (effect-integrity)** ships **warning-only** for one cycle to baseline existing
   entries against the graph/manifest, then **ratchets to blocking** once the baseline is
   clean. A governed-debt baseline (per ADR-056 true-debt semantics) captures any entry
   that cannot yet be graph-proven, with owner + review trigger.

---

## Rationale

RC1 and RC2 are independent: even with perfect per-setting rows (P2), a checker that
trusts field *presence* (RC1) still cannot tell a true consumer from a plausible-looking
string. Both must close. P2 makes the unit of enforcement correct; P1 makes the claim
verifiable. Together they turn RULE-18b from "the matrix says so" into "the code proves
it" — the same truthful-status discipline ADR-045/056 introduced for adoption scoring.

Option C is rejected as disproportionate; the matrix is the right declarative surface,
and it only needs to be *grounded* in the code, not relocated into it.

---

## Consequences

**Positive:**
- The `websocket_idle_retry_cascade` class of false control cannot recur: aggregated
  claims are structurally rejected, and consumer/evidence claims are verified.
- RULE-18b becomes machine-checkable per setting, not per aggregate.
- Future settings pay a small upfront cost (real consumer + real test) instead of
  accumulating silent false controls.

**Negative / Trade-offs:**
- New checker module + tests + baseline/grace work (Platform, Stage 3).
- Some entries need an evidence-manifest record where graph proof is infeasible
  (indirect consumers); this is a small ongoing maintenance cost, not a workaround.
- Initial warning-only phase means P1 is not immediately blocking — governed by the
  ratchet discipline (ADR-056).

**Constraints introduced:**
- **RULE-18b:** matrix entries are one-setting-per-row; `runtime_consumer` and
  `enforcement_evidence` must be truth-verifiable (graph or manifest), not merely
  present.
- Aggregated `setting_id`s are prohibited absent an approved `composite_rationale`.

---

## RULE-XX Compliance

| Rule | Status | Note |
|------|--------|------|
| RULE-18b | ✅ | Effect integrity enforced per setting (P1) on non-aggregated rows (P2). |
| RULE-22 | ✅ | Governance claim ↔ code ↔ test coherence is checked, not asserted. |
| RULE-04/06/07 | ✅ | Checker stays modular, single-purpose, no runtime imports. |
| RULE-10/11 | ✅ | Checker failures are testable and visible; no silent pass. |

---

## Implementation Notes (Stage 3 — Platform; NOT done by this ADR)

- Likely home: a new `scripts/governance/` module (e.g. `_matrix_effect_integrity.py`) +
  a checker entrypoint, wired into `scripts/run_checks.py` / `just` / CI architecture job,
  alongside `check_configuration_matrix.py`.
- Reuse the code graph (code-review-graph / codebase-memory-mcp) for symbol resolution;
  fall back to a typed evidence manifest for indirect consumers.
- P2's allowlist + `composite_rationale` field are added to the matrix schema
  (`_matrix_types.py`) and documented in the ADR-051 remediation spec.
- Tests: `tests/unit/scripts/governance/` — aggregation rejection cases; true-consumer
  PASS; sibling-evidence-only FAIL; manifest-fallback PASS.

**ADR Implementation Completeness Gate (Gate 12):** P2 blocking + P1 baseline before
marking ✅ Implemented; P1 ratchets to blocking in a follow-up once clean.

---

## Review Trigger

- After P1's first full review cycle at blocking severity.
- If the code-graph provider changes and consumer resolution becomes unreliable.
- If a legitimate need for a composite `setting_id` arises (re-evaluate the allowlist).
