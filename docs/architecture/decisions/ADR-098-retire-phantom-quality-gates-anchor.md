# ADR-098 — Retire the Phantom `quality-gates.md` Doc Anchor

> **Status:** ✅ Implemented — PR #255 CI green (run 38633764724);
> wave commits 98296b57 + 32ce36e0.
> **Date:** 2026-10-14
> **Deciders:** Architecture Agent
> **Supersedes:** none
> **Related:** ADR-097 (whose wave rider `b203e71e` fixed the first fallow
> anchor — the ci.yml header pointer — and explicitly deferred
> restore-vs-retire for the rest to this decision)

---

## Context

### The phantom

The path `.opencode/context/narrare-dev/processes/quality-gates.md` does not
exist. It was a real, tracked, maintained document — commits `26b6b940`
(review-04 DX/tooling, #111), `3ee3f048` (CR-06, #126), `42c762d2` (Q-016),
and `90e0a60f` (ADR-080 follow-up) all maintained it — until `f11eb44a`
("chore(opencode): rebuild agent setup with graphify + opencode-mem")
deliberately deleted it together with the entire `.opencode/context/` tree
(verified: `.opencode/` today contains only `agents/`, `commands/`,
`skills/`, `plugins/`, `env.example`). The removal was a deliberate
agent-setup rebuild, not an accident. What survived downstream are **fallow
anchors**: references — some executable — to a doc surface that no longer
exists.

ADR-097's wave fixed the first of them: rider `b203e71e` on main `16ef2c9e`
dropped the stale pointer from the ci.yml header comment and flagged the
rest, stating "restore-vs-retire for the drift-check doc anchor is an
Architecture decision, not a comment fix". This ADR is that decision.

### Where the gate SSOT actually lives today

Since the rebuild, the quality-gate SSOT is:

- the **ci.yml header table** (`.github/workflows/ci.yml` lines ~8–37:
  G1–G10 plus G6a; G2 row: "`--cov-fail-under` … Target 80% reached"; G6
  row: "pyright (strict; **mypy not required**)"), and
- **CONSTRAINTS.md §6** (enforcement table, RULE-10 row: "`pytest --cov`
  with minimum thresholds") plus RULE-10 itself (core ≥90%, apps/api ≥80%).

### Consumer inventory (re-verified in code at ADR-writing time)

| # | Consumer | Verified state |
|---|----------|----------------|
| 1 | `scripts/gate_drift_checks.py:23-25` — `QUALITY_GATES_PATH`; `:310` — `docs_content = _read_file(QUALITY_GATES_PATH) or ""`; module docstring `:7` cites "Gate 11" | Reads the phantom; silently degrades to `""` |
| 1a | └ `check_coverage_threshold()` (`:146-181`) | `docs_content` parameter is **decorative** — never read. The documented target is the hardcoded constant `target = 80` (`:165`); comment `:163` cites "per quality-gates.md Gate 2". The coverage dimension never actually depended on the doc. |
| 1b | └ `check_mypy_drift()` (`:184-228`) | `_mypy_in_docs(docs_content)` (`:191`, helper `:121-123` = `"mypy" in docs_content.lower()`) reduces to `"mypy" in ""` → always `False` → the trivial-pass branch `:195-200` ("mypy not referenced in quality-gates documentation") fires unconditionally. **Vacuous since `f11eb44a`.** Reproduced live: `check_gate_drift.py` prints exactly that line and exits 0. |
| 1c | └ `check_streaming_compliance()` / `check_locale_sync()` (`:231`, `:269`) | `ci_content` only — no doc dependency, unaffected by this ADR. |
| 2 | `scripts/check_gate_drift.py` — CI-wired (ci.yml `:256`, architecture job); docstring `:17` cites "Gate 11" | Runs green **with vacuous doc-side comparisons** — green without assurance for the mypy dimension. |
| 3 | `scripts/check_gate_expirations.py:18` — docstring cites the phantom + "Gate 11" | Stale pointer, no functional impact. CI-wired (ci.yml `:253`). Reads `scripts/gate-exceptions.json`. |
| 4 | `scripts/gate-exceptions.json:2` — `_comment` cites the phantom + "Gate 11" | Stale pointer in a real, functional registry. The registry holds 2 entries — `coverage-threshold` (G2) and `mypy-not-configured` (G6) — **both `status: "resolved"`** (0 active; `_get_exception_ids` filters on `active`). |
| 5 | `scripts/doc_drift/lookup_drift_checks.py:102-116` — `_Pattern(check_id="LOOKUP-COVERAGE-60-FLOOR", rel_path="processes/quality-gates.md", …)` | `_check_one` (`:167-169`) returns `None` for missing files → the pattern scans a file that never exists → **dead guard**. Its tests (`tests/unit/scripts/test_lookup_drift_checks.py:77-80`, `:146-153`) build synthetic fixture trees containing that file — the pattern is "tested" but can never fire against the real repo. |
| 6 | ~12 immutable historical records: 9 ADRs (025, 045, 063, 066, 071, 080, 081, 089, 091), `_TEMPLATE.md`, `docs/architecture/implementation-plans/IO-001-export-pipeline.md:1474`, `docs/superpowers/plans/2026-09-30-ci-minutes-hardening.md:185`, `docs/features/infra/INFRA-012-prompt-governance-hardening.md:458` | Historical records — explicitly OUT OF SCOPE, untouched. |

Adjacent facts, recorded for honesty: no dedicated unit tests exist for
`gate_drift_checks` (verified: `tests/` has no `gate_drift` reference; only
`test_lookup_drift_checks.py` covers this family); nothing outside
`gate_drift_checks.py` imports `check_mypy_drift`, `_mypy_in_docs`, or
`QUALITY_GATES_PATH` (repo-wide grep) — retirement is a clean removal. And
because the whole `.opencode/context/` tree is gone, **every** lookup-drift
pattern — not only the quality-gates one — is dormant against the real repo;
this ADR retires only the `quality-gates.md` anchor. The broader
lookup-pattern catalog's fate is a separate decision, deliberately not
pre-empted here.

### Root cause (2× Why)

1. *Symptom:* a CI-wired drift check runs green without doc-side assurance,
   and a doc-drift guard pattern exists that can never fire.
2. *Why?* `run_all_checks()` coerces the missing file to `""`
   (`_read_file(...) or ""`), and the consumers treat "file missing" as
   "doc makes no claim" — so the mypy branch trivially passes and the
   coverage comparison never reads the doc at all.
3. *Why is that the actual cause?* The doc was deliberately removed
   (`f11eb44a`) without retiring its consumers. The check design conflates
   "no doc" with "no claim", so removing the doc surface silently hollowed
   the checks instead of failing them. The defect is the surviving anchor
   set — not the removal, and not the checks' CI wiring.

---

## Decision Drivers

- **Single gate SSOT:** the gate matrix already lives in the ci.yml header
  table (G1–G10 + G6a) and CONSTRAINTS.md §6; no third location.
- **No vacuous gates:** a check that cannot fail is worse than no check —
  it manufactures assurance (green without protection). Silent degradation
  of a gate contradicts RULE-11's spirit even where the letter does not
  apply.
- **Immutability of history:** ADRs and plan docs are records of their
  time; rewriting them to erase a path would falsify history.
- **Minimal, mechanical wave:** the code changes are small, local, and
  provable — no behavior with real input surfaces changes.

---

## Options Considered

### Option A — restore the document

Recreate `.opencode/context/narrare-dev/processes/quality-gates.md` so the
anchors resolve again.

**Pros:** every existing reference becomes valid; the drift checks regain a
real comparison surface; no code changes.

**Cons:** recreates a doc the project deliberately removed; the gate SSOT
already lives in two authoritative places (ci.yml header table,
CONSTRAINTS.md §6) — a restored doc would be a **third SSOT location** with
no consumer that needs it (the coverage check never read it; the mypy
question is resolved); re-introduces exactly the manual-sync burden the
lookup-drift architecture was built to detect.

**Rejected:** the removal in `f11eb44a` was intentional; restoring would
reverse a deliberate decision without a demand, create SSOT triplication,
and re-arm a doc-drift surface (RULE-22 spirit: drift checks must compare
two *real* surfaces — a restored doc nobody maintains recreates the
original drift problem review-04 documented).

### Option B — retire the doc anchor (chosen)

Remove every *executable* dependency on the phantom path and re-anchor the
*prose* pointers to real sources. Details in Decision.

**Pros:** every surviving check compares only real surfaces; the vacuous
mypy dimension disappears honestly instead of passing forever; the
exception registry's authority gets a real anchor (this ADR + the registry
itself); no third SSOT.

**Cons:** `check_gate_drift.py` loses its (already vacuous) mypy dimension;
a future gates doc would need explicit re-wiring (see Review Trigger).

### Option C — redirect `docs_content` to CONSTRAINTS.md §6

Keep the plumbing, read `docs/_shared/CONSTRAINTS.md` instead of the
phantom.

**Pros:** minimal code churn; the mypy check regains a real doc surface.

**Cons:** of the two doc-consuming checks, only `check_mypy_drift` would
use the redirected content — and no current document makes a
"mypy-as-gate" claim worth guarding (ci.yml G6 itself records "mypy not
required", and the registry resolved the question in June 2026). This adds
coupling from a CI script to CONSTRAINTS.md's prose structure for zero
present protective value.

**Rejected:** guards should watch claims that exist. A guard wired to a
surface that makes no claim of the guarded kind is a future vacuity, just
relocated.

---

## Decision

**We choose Option B — retire the phantom anchor.** The implementation wave
follows in this branch (`chore/gate-drift-anchor`); this ADR changes no
code itself. Binding items:

1. **`scripts/gate_drift_checks.py` — drop the doc plumbing.** Remove
   `QUALITY_GATES_PATH`, the `docs_content` read in `run_all_checks()`, the
   `docs_content` parameters, and the module docstring's "Gate 11" pointer.
2. **Coverage check unchanged in behavior, re-anchored in prose.** The
   hardcoded `target = 80` stays; its comment is re-anchored from
   "per quality-gates.md Gate 2" to the real sources — the ci.yml header
   G2 row and CONSTRAINTS.md §6 (RULE-10: core ≥90%, apps/api ≥80%).
3. **`check_mypy_drift` is RETIRED outright** — not rewired. Its protective
   purpose ("docs claim mypy is a gate while CI doesn't run it") has had no
   real doc surface since `f11eb44a`; ci.yml's own G6 row documents "mypy
   not required"; and the question was adjudicated and resolved on
   2026-06-04 in the registry (`mypy-not-configured`, G6: "pyright alone is
   sufficient … No mypy needed"). Removing an always-trivial-pass check
   loses zero assurance and deletes a silent-degradation path.
4. **Prose re-anchors.** `scripts/check_gate_expirations.py:18` (docstring)
   and `scripts/gate-exceptions.json:2` (`_comment`) — and the equivalent
   docstring in `scripts/check_gate_drift.py:17` — re-anchor from the
   phantom "Gate 11" to **this ADR + the JSON registry itself**. The
   gate-exception registry's process authority moves here. Expiry
   discipline is unchanged: `check_gate_expirations.py` keeps validating
   `set_date` / `expires` / `review_after`, warning on approaching review
   (`REVIEW_DUE`), failing on expiry (exit 1), and failing hard on >30-day
   expiry (exit 2).
5. **`scripts/doc_drift/lookup_drift_checks.py` — remove the dead
   `LOOKUP-COVERAGE-60-FLOOR` pattern.** Its tests shrink accordingly: the
   clean-tree fixture (`test_lookup_drift_checks.py:77-80`) no longer
   writes `processes/quality-gates.md`, and
   `test_60_percent_coverage_floor_is_critical` (`:146-153`) is removed.
6. **Scope boundary — what this wave does NOT touch.** The ~12 immutable
   historical records (9 ADRs, `_TEMPLATE.md`, both plan docs, the
   INFRA-012 feature record) stay as written. Two *living*-doc stragglers
   are recorded here as follow-up, deliberately outside this wave's file
   list: `_TEMPLATE.md`'s Gate-12 block (which still points new ADR authors
   at the phantom) and `docs/_shared/CURRENT_STATE.md` (whose line-10 note
   tracks this exact dangling-pointer problem and is refreshed when the
   wave lands).

---

## Rationale

The phantom is not a missing file to restore — it is a *removed* SSOT
location whose consumers were never retired. That is why the failure mode
is so quiet: `_read_file` returning `None` for an absent path is correct
behavior for an optional input, and `or ""` then converts "no doc" into
"doc makes no claim", which the mypy check treats as a pass. Nothing ever
goes red; the assurance simply evaporated on the day of `f11eb44a`.

Option A reverses a deliberate removal to satisfy legacy references — the
tail wagging the dog — and would create a third gate SSOT that nobody
maintains, which is precisely the drift situation review-04 built the
lookup-drift checker to catch. Option C keeps a guard alive for a claim no
document makes; the only honest input for "is mypy documented as a gate?"
is *no document exists to make that claim*, and a guard whose answer is
structurally predetermined is not a guard. Option B is the only option
where every surviving check compares real surfaces and every prose pointer
resolves to something that exists.

The mypy retirement deserves the explicit justification, because deleting a
CI check is normally a red flag: the check has been a no-op for its entire
recent life (vacuous since `f11eb44a`), the substantive question it guarded
was decided and resolved in the registry in June 2026, and the authoritative
statement ("mypy not required") lives in the same ci.yml G6 row the rest of
the checker already reads. There is no input, present or plausible, on which
retiring it changes an outcome.

---

## Consequences

**Positive:**

- Every surviving `check_gate_drift.py` dimension (coverage, streaming,
  locale) compares real, existing surfaces — no vacuous green.
- The exception registry's `_comment` and the expiry checker's docstring
  point at something that exists (this ADR + the registry), so future
  readers are not sent hunting for a phantom "Gate 11".
- A dead guard pattern and its synthetic-only tests are removed — test
  count shrinks, but the removed tests verified nothing about the real
  repo.
- The historical record stays intact: nothing written before `f11eb44a` is
  rewritten.

**Negative / Tradeoffs:**

- The CI-wired `check_gate_drift.py` loses its mypy dimension. This is a
  documentation-level loss only — in practice no assurance change, because
  the dimension has been vacuous since `f11eb44a`.
- Re-introducing a gates doc at any future point requires a new ADR and
  explicit re-wiring (see Review Trigger) — this is deliberate friction
  against accidental SSOT sprawl.
- ~12 immutable references to the path remain in the repository and will
  forever resolve to nothing. Accepted: they are records of their time, and
  this ADR is the authoritative explanation for why.

**Constraints introduced:**

- RULE-22 spirit (formalized for this family): a drift check must compare
  two real, existing surfaces. A check that can never fail, or a guard
  pattern whose target file cannot exist, must be retired, not left green.
- RULE-10 enforcement is unchanged and now solely anchored in ci.yml G2 /
  CONSTRAINTS.md §6 — the hardcoded `target = 80` keeps those as its cited
  source.
- No new dependencies; no CONSTRAINTS.md text changes.

---

## Implementation Notes

**Files touched by the implementation wave (none touched by this ADR):**

- `scripts/gate_drift_checks.py` — delete `QUALITY_GATES_PATH` (`:23-25`),
  the `docs_content` read (`:310`) and its plumbing into
  `check_coverage_threshold` / `check_mypy_drift`; delete
  `check_mypy_drift` (`:184-228`), `_mypy_in_docs` (`:121-123`), and
  `_has_mypy_config` (`:116-118`) — the mypy retirement also orphans the
  `pyproject_content` plumbing (`PYPROJECT_PATH` `:22`, read `:309`,
  passed `:317`, consumed only by the deleted check at `:193`), which goes
  with it; re-anchor the module docstring (`:7`) and the `:163` comment.
  NOTE: removing the check shrinks the report from 4 to 3 items —
  `scripts/check_gate_drift.py`'s rendering handles any item count, no
  other consumer reads the `mypy` check id.
- `scripts/check_gate_drift.py` — docstring `:17` re-anchor; behavior
  otherwise unchanged (still CI-wired at ci.yml `:256`).
- `scripts/check_gate_expirations.py` — docstring `:18` re-anchor to this
  ADR + the registry; expiry logic untouched.
- `scripts/gate-exceptions.json` — `_comment` (`:2`) re-anchor to this ADR
  + the registry itself. Registry data untouched.
- `scripts/doc_drift/lookup_drift_checks.py` — remove the
  `LOOKUP-COVERAGE-60-FLOOR` pattern (`:102-116`) and the coverage-drift
  section comment (`:101`).
- `tests/unit/scripts/test_lookup_drift_checks.py` — clean-tree fixture
  (`:77-80`) stops writing `processes/quality-gates.md`;
  `test_60_percent_coverage_floor_is_critical` (`:146-153`) removed.

**ADR Implementation Completeness:** An ADR is not implemented until it is
fully wired, tested, consumed, and documented. For this ADR the binding
checklist is: (1) `gate_drift_checks.py` de-anchored (no
`QUALITY_GATES_PATH`, no `docs_content`), (2) `check_mypy_drift` removed,
(3) both docstrings + `gate-exceptions.json` `_comment` re-anchored,
(4) `LOOKUP-COVERAGE-60-FLOOR` pattern and its fixtures removed, (5) the
wave's PR CI architecture job runs `check_gate_drift.py` green with the
3-item report — the only item that cannot be evidenced locally, gating the
flip to ✅.

---

## Review Trigger

- [ ] If a future gates-doc SSOT is (re)created at any path: re-wire the
      doc-side drift comparisons to it or retire this ADR's decision
      explicitly — via a new ADR, never silently.
- [ ] When `scripts/gate-exceptions.json` entries expire or are removed:
      update its `_comment` alongside (it anchors the registry's process
      authority to this ADR).
- [ ] When the follow-up living-doc stragglers are addressed
      (`_TEMPLATE.md` Gate-12 block; `CURRENT_STATE.md` refresh at wave
      landing): confirm no *new* executable references to the phantom path
      were introduced (grep `quality-gates.md` over `scripts/`,
      `.github/`, `apps/`, `packages/` stays empty).
- [ ] If the `.opencode/context/` lookup tree is ever rebuilt, decide the
      fate of the remaining dormant lookup-drift patterns (tech-stack,
      deployment) — this ADR deliberately scoped itself to the
      quality-gates anchor only.

---

## Amendment 1 — 2026-10-15: lookup-drift subsystem retired

The Review Trigger's open question (all five remaining lookup-drift
patterns resolve under the removed `_LOOKUP_DIR` tree, so the whole
lookup-drift subsystem ran vacuously in CI) was decided by PO ruling
on 2026-10-15: **retire**.

Deleted: `scripts/doc_drift/lookup_drift_checks.py` and
`tests/unit/scripts/test_lookup_drift_checks.py`; `check_doc_drift.py`
drops the `("lookup", …)` registration. The RULE-23 ratchet key for the
deleted test file was removed via the sanctioned
`--update-baseline --allow-removed` procedure (totals 901→900). The
pattern catalog (pydantic-ai/mem0 1.x pins, fastapi-limiter,
the phantom `just dev-up` (does not exist), hardcoded hook count)
remains recoverable from git history: if a future agent-context
lookup layer returns, that is a new decision with new guards, not a
restoration of these.
