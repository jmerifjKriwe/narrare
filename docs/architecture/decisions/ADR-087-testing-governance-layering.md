# ADR-087 — Testing Governance Layering: Principles → Preferences → Patterns

> **Status:** 🔄 Proposed (draft) — awaiting per-row decisions on the Keep/Relax/Drop table (§7)
> **Date:** 2026-08-28
> **Deciders:** Architecture Agent (draft) · User (row-by-row selection pending)
> **Supersedes:** none (amends the *structure* of `docs/development/testing-standards.md`; changes no RULE-XX)

---

## Context

### The rule-accumulation dynamic

Narrare's test governance grew reactively. The recurring pattern:

```
agent makes a specific, repeated mistake
  → a rule is written to forbid that mistake
    → the rule accretes exceptions, thresholds, and recipes
      → the standards document grows
        → rules start prescribing *technique*, not just *outcomes*
          → technique prescriptions collide with each other and with new tooling
```

This dynamic is rational in context: the codebase is written almost exclusively
by AI agents, and nearly every mechanical gate in place today exists because
agents repeatedly made the specific mistake the gate now catches (evidence in
§7 and in the CONSTRAINTS.md exceptions register,
`docs/_shared/CONSTRAINTS.md:1219-1326`). The gates are not ceremonial — they
have a documented catch history.

The problem is **document structure, not gate substance**:

- `docs/development/testing-standards.md` — **1472 lines** — mixes
  non-negotiable principles ("a test lives at the lowest level where it is
  meaningful"), preferences ("Fakes instead of MagicMock"), mechanical quotas
  ("3 cases per method"), and copy-pasteable recipes (FakeChapterRepository,
  auth-proxy pattern) in one flat document with identical normative force.
- `docs/_shared/CONSTRAINTS.md` — **1389 lines, 23 RULE-XX** plus RULE-TEST-01
  through RULE-TEST-04 defined in testing-standards.md — is approaching the
  size where contradiction risk grows faster than rule value.

### The symptom that triggered this ADR

An external review asked: should agents use **TDD London School** (interaction
based, mock-framework-centric) or the project's **Fake policy** (state-based,
hand-written fakes)? The question only arises **because the standards
prescribe test technique**. A governance model that separates *what must hold*
(principles) from *what we prefer* (technique defaults) from *how we did it
last time* (recipes) dissolves the question: test doubles are chosen by
purpose, not by school.

Related verified findings from the review fact-check (2026-08-27):

- The global coverage gate is `fail_under = 80`
  (`pyproject.toml [tool.coverage.report]`, key `fail_under`), **not** decreed 90/95% hard gates.
- Per-module coverage is **ratcheted baselines** over 56 packages
  (`scripts/coverage_baselines.json`, updated 2026-08-18) plus per-root
  RULE-10 targets enforced as a hard floor in CI `--fail` mode
  (`scripts/check_module_coverage.py`, `.github/workflows/ci.yml:450`).
- Rule text and enforcement text have **drifted apart in both directions**:
  - `scripts/check_module_coverage.py:5` calls the RULE-10 target a "hard
    floor — blocking", while its own help epilog
    (`scripts/check_module_coverage.py:119-122`) calls the same values
    "aspirational — warnings until met" — stale pre-ratchet language.
  - The coverage table in testing-standards.md:938-959 lists per-role
    minimums (85% services, 80% repositories/routers) that no script enforces
    (the script derives 95/90/80 from source root,
    `scripts/check_module_coverage.py:119-122`) and claims "Coverage below
    minimum = CI failure. No exceptions."
  - testing-standards.md:1437-1447 references four files that do not exist
    (`AGENT.md`, `TEST_STRATEGY.md`, `PATTERNS.md`, `COVERAGE_GOALS.md`).
  - The document header still names a "Testing Agent" (testing-standards.md:7),
    a role dissolved by ADR-014 (implementers write their own tests; Platform
    is gatekeeper). The footer (:1471-1472) names the Architecture Agent —
    correct as is.

### Verified current enforcement mechanics (do not re-litigate)

| Mechanism | Where | CI behavior |
|---|---|---|
| Global coverage floor 80% | `pyproject.toml [tool.coverage.report]` (`fail_under`) | blocking |
| Per-module ratcheted baselines (56 pkgs) | `scripts/coverage_baselines.json` + `scripts/check_module_coverage.py` | regression = warning; below target = exit 1 in `--fail` (ci.yml:450) |
| Test-file existence (RULE-10) | `scripts/check_test_coverage_gaps.py --fail-on-missing` | blocking (ci.yml:248) |
| Bare-MagicMock AST scan (RULE-TEST-01) | `scripts/architecture/_checkers/testing.py:12-41` | blocking via `check_architecture.py` (pre-commit + CI) |
| Auto-tagging + schema-mutating guard (RULE-TEST-03) | `tests/conftest.py:119`, `tests/_schema_guard.py` | collection-fail + two-phase serial (justfile:311-316, ci.yml:562-566) |
| Architecture checker as test | `tests/conftest.py:203-212` | blocking |
| Real-LLM call prevention | `tests/conftest.py:83` (`ALLOW_MODEL_REQUESTS = False`) | runtime RuntimeError |
| Frontend coverage floors | `packages/web/vitest.config.mts` (`lib/**` ≥ 80%, components ratcheted 65%) | blocking (frontend job) |
| Collection / runtime budgets | `check_pytest_collection_performance.py` (ci.yml:458), `check_test_performance.py` (ci.yml:721-738) | **warning-only** |
| RAM-aware xdist worker selection | `justfile` `test`/`test-lowmem` (Q-019) | local runner logic |
| RULE-23 type-ignore ratchet | `check_architecture.py` `# type: ignore` scan + baseline comparison (CONSTRAINTS.md:1019) | blocking |
| Per-variable prompt-integrity ratchet + STALE-BASELINE | `scripts/architecture/_checkers/prompt_integrity.py` via `check_architecture.py --prompt-integrity`; baseline `scripts/architecture/ai-gate-baseline.json` | blocking (landed `9a9a77fe`) |
| PROMPT-L2-HEADERS header governance | `scripts/architecture/_checkers/_check_system_headers.py` (run within prompt-integrity checks); allowlist 7 → 0 | blocking (program completed `9f4c7519`) |

---

## Decision Drivers

- **Agent error rates justify mechanical gates.** The exceptions register and
  git history show real catches (§7). Dropping enforcement would reintroduce
  known failure classes.
- **Technique prescription creates false conflicts.** London-School-vs-Fakes
  is a governance artifact, not a real engineering question.
- **Flat normativity is unauditable.** When everything is mandatory, nothing
  is; reviewers cannot tell principle from recipe.
- **Doc-reality drift is already measurable** (three concrete cases above).
  A layering that makes the machine SSOT the *only* place where numbers live
  removes an entire drift class.
- **ADR-014 must remain untouched.** Implementers write their own unit/
  regression tests; bug fixes are regression-first (ADR-014:54, 63).
- **CONSTRAINTS.md is the constitution** — any RULE-10 phrasing change
  requires its own governance step (PR + decisions entry per
  CONSTRAINTS.md:3-6). This ADR proposes, it does not amend.

---

## Options Considered

### Option A — Status quo with incremental pruning

Keep the flat document; fix the identified drift (coverage table, stale
references, Testing-Agent header) in place.

**Pros:** Smallest diff; no structural risk.
**Cons:** Does not fix the root cause (flat normativity); the accumulation
dynamic continues; the next technique question re-triggers the same debate;
drift re-appears because prose keeps duplicating machine SSOT values.

### Option B — Three-tier governance layering (principles → preferences → patterns)

Restructure testing-standards.md into three normativity tiers, add a
risk-tiered test mandate replacing the flat per-method quota, and replace all
duplicated numbers with references to the machine SSOT.

**Pros:** Separates outcomes from technique from recipe; makes every rule's
normativity explicit and auditable; dissolves the London-School question by
construction; eliminates number-duplication drift; keeps every enforcement
mechanism intact (pure documentation restructure).
**Cons:** One-time restructuring cost (~1472 lines reorganized); every
deep-link into testing-standards.md must be re-validated; risk of *accidental*
semantic change during the move (mitigated by the §7 inventory + per-row
approval + `check_doc_drift.py` / `check_gate_drift.py` gates).

### Option C — Radical simplification (principles only, drop mechanical gates)

Reduce to ~1 page of principles; delete quotas, recipes, and most gates.

**Pros:** Minimal reading burden; maximum agent freedom.
**Cons:** Contradicts the verified catch history — gates exist because agents
repeatedly made those specific mistakes (e.g., ~25% local crash rate before
RAM-aware xdist, testing-standards.md:840-856; shared-schema corruption before
the schema_mutating guard, testing-standards.md:790-814; the RULE-14
model-without-migration production crash, CONSTRAINTS.md:519-529). Rejecting
evidence of caught defects is not simplification — it is amnesia.

---

## Decision

**We choose Option B.**

The standards are not "over-gated" — the *gates* have catch evidence. The
standards are **over-flat**: principles, preferences, and recipes carry the
same "must" voice, which manufactures conflicts (London School vs Fakes),
invites number duplication (coverage tables drifting from the script), and
makes the document's real normative core unfindable. Layering fixes the
structure while leaving enforcement — and its proven catch record — intact.

---

## The 3-Tier Model

### Tier 1 — Non-negotiable principles (~8)

Violating a Tier-1 principle is a defect, regardless of which technique was
used. These are the only testing rules that carry unconditional "must".

1. **Test behavior, not implementation structure.** A test asserts observable
   outcomes (return values, state changes, emitted events, HTTP responses) —
   not how the code produced them.
2. **A test lives at the lowest level where it is meaningful** (reaffirms
   testing-standards.md:31-34). Unit for logic, integration for persistence
   and HTTP, E2E for user flows.
3. **Unit tests perform no external I/O.** No network, no DB, no subprocess;
   externals are controlled at a seam (constructor injection, TestModel,
   fixtures). Backed by `ALLOW_MODEL_REQUESTS = False` (`tests/conftest.py:83`).
4. **Use real infrastructure when infrastructure is the subject.** Repository
   SQL and migrations are tested against a real database with real Alembic
   migrations (testing-standards.md:53-56, 676-694) — a mocked `AsyncSession`
   proves nothing about a WHERE clause.
5. **Non-deterministic externals are controlled.** LLMs (TestModel/
   FunctionModel), time, randomness — every test must be repeatable
   (`pytest-randomly` exists precisely to catch violations).
6. **Cross-layer contracts are tested explicitly at the boundary.**
   Backend↔frontend field names (RULE-17), i18n namespaces (RULE-16),
   schema↔model consistency (RULE-14). Unit tests that mock both sides prove
   nothing about the seam — this is the "three bugs went undetected" lesson
   (testing-standards.md:163-168).
7. **Assertions must be meaningful.** Coverage without assertion quality is
   theater (testing-standards.md:961-963); a test that cannot fail is not a
   test. Post-state verification beats response-only verification where state
   is the contract (RULE-TEST-02, testing-standards.md:697-714).
8. **The implementation does not certify itself.** The code under test must
   not weaken, bypass, or generate its own assertions; regression tests for
   bug fixes are written first and fail before the fix (ADR-014, untouched).

### Tier 2 — Preferences ("prefer, don't prohibit")

Defaults with named escape hatches. Deviation requires a one-line
justification (comment or PR note), not an exceptions-register entry.

- **Test doubles are chosen by purpose** (resolves the London-School question):
  - Default workflow is **outside-in, contract-first TDD**: define the
    Protocol (RULE-03), write the failing consumer test, implement.
  - **State-based verification is the default** — assert outcomes and state.
  - **Fakes are preferred for complex domain collaborators** (repositories,
    services): they implement the Protocol, double as contract documentation,
    and break loudly on Protocol drift.
  - **Mocks/spies are permitted when the interaction *is* the contract under
    test** (e.g., "exactly one retry", "credential wiped on logout",
    "tool was invoked with these arguments"). Interaction testing is a tool
    for interaction contracts — not a school to belong to.
- **Constructor injection** for substitutable dependencies; never bypass
  `__init__` with `__new__` (testing-standards.md:641-651).
- **TestModel/FunctionModel for pydantic-ai agents** — exercises the real
  agent code path (testing-standards.md:522-571).
- **Real DB for repository/migration tests** — see Tier 1 #4.
- **Testing Library for UI** — query by role/ARIA, assert on behavior, not on
  component internals (testing-standards.md:1031-1036).
- **Property-based tests (Hypothesis) for pure parsing/serialization code** —
  where input space is large and the oracle is cheap
  (testing-standards.md:1185-1206).

### Tier 3 — Patterns and recipes ("recipes, not law")

Copy-pasteable starting points. Following them is convenient; deviating is
fine when the deviation is deliberate. All of these survive as documentation,
explicitly labeled as recipes:

FakeChapterRepository (seed + call tracking), `tests/fakes/` layout, fake
conformance tests, `capture_run_messages`, `FunctionModel(stream_function=…)`,
`model_validate()` on 200/201 responses, autouse env-var fixtures,
`make_*` factory helpers, the `schema_mutating` marker workflow, E2E
auth-proxy pattern, E2E wizard/editor robustness patterns, the global
`motion/react` mock, MSW handler layout, snapshot discipline rules,
`test_<what>_<condition>_<expected_result>` naming, RAM-aware `just test`
recipes.

**Numbers live only in the machine SSOT.** Tier 3 (and the whole document)
must *reference* thresholds (`scripts/coverage_baselines.json`,
`pyproject.toml [tool.coverage.report]`, `packages/web/vitest.config.mts`) — never
restate them. This deletes the drift class exemplified by
testing-standards.md:938-959.

---

## Risk-Tiered Test Mandate (replaces the flat "every public method → happy/error/edge")

The current quota (testing-standards.md:42-46 for services, 90-103 for
repositories/routers) optimizes for *test count*, not *risk reduction*.
Replacement:

### High-risk code — full mandatory case matrix

Applies to any code touching **auth, transactions, state transitions,
retries, or external side effects** (LLM calls, export/file writes,
shared-data mutations per RULE-22), at service/domain level:

- happy path; every typed domain error in the contract; boundary conditions
  the domain defines; and, where applicable, retry/idempotency and
  ordering/concurrency behavior.
- Failure modes are derived **from the contract** (typed errors, Protocol
  semantics), not from imagining arbitrary inputs.

### Standard code — contract-derived cases

Ordinary service/domain methods: happy path plus the failure modes and edges
*the contract declares*. No numeric minimum.

### Documented trivial exemption

Pure accessors, DTO passthroughs, and declarative re-exports are exempt from
case-count guidance (a smoke test suffices). The exemption does **not**
weaken RULE-10 test-file existence (`check_test_coverage_gaps.py`) or the
coverage floors.

### Untouched

**Regression-first for bug fixes (ADR-014)** stays exactly as decided: every
bug fix starts with a failing regression test. Router-endpoint integration
coverage (401/404/422 classes, testing-standards.md:99-103) remains mandatory
— HTTP status behavior *is* the contract of a router.

---

## Keep / Relax / Drop Decision Table

Every mechanical gate / mandate found in testing-standards.md plus related
enforcement. **Recommendations are proposals — the user decides per row.**
Line numbers cite current HEAD and may drift; locate targets by semantic name.

Legend — **KEEP**: unchanged substance and enforcement. **RELAX**: substance
survives with reduced normativity (typically: quota → preference, duplicated
number → SSOT reference, per-file mandate → risk-based). **DROP**: remove
(stale, superseded, or zero value).

| # | Gate / mandate | Current form (file:line) | Enforcement | Historical catch evidence | Cost | Options | **Recommendation** |
|---|---|---|---|---|---|---|---|
| 1 | Global coverage floor 80% | `pyproject.toml [tool.coverage.report]` (`fail_under = 80`) | pytest-cov, blocking | baseline hygiene commits (`f6f94bcf` 6-wave uplift) | low | KEEP / RELAX / DROP | **KEEP** |
| 2 | Per-module ratcheted baselines (56 pkgs) | `scripts/coverage_baselines.json`; `scripts/check_module_coverage.py` | regression → warning; CI `--fail` (ci.yml:450) | ratchet hardening `2c13df80`; override-weakening closed `3e1f2f3f` | medium (baseline updates on refactors) | KEEP / RELAX / DROP | **KEEP** |
| 3 | RULE-10 per-root targets 95/90/80 | `scripts/check_module_coverage.py:5,119-122`; RULE-10 text CONSTRAINTS.md:726-727 | below target → exit 1 in `--fail` mode | targets derived from source root `9e087688` | low | KEEP / RELAX / DROP | **KEEP** + fix the script's own "aspirational" vs "hard floor" wording contradiction (stale epilog) |
| 4 | Coverage table w/ per-role minimums + "No exceptions" | testing-standards.md:938-959 | none — values (85/80%) match no script; contradicts enforced 95/90/80 | drift itself is the finding | high (agents optimize for wrong numbers) | KEEP / RELAX / DROP | **RELAX** — delete table, reference machine SSOT (Tier-3 rule: numbers live only in scripts) |
| 5 | Test-file existence gap check | `scripts/check_test_coverage_gaps.py`; ci.yml:248 `--fail-on-missing`; RULE-10 (CONSTRAINTS.md:722-736) | blocking (architecture job) | gap-closure commits (`326dac15`, `80803d26`) | low | KEEP / RELAX / DROP | **KEEP** |
| 6 | 3-case quota, service methods | testing-standards.md:42-46 | review-only | no catch evidence found (no gate ever counted cases) | high (test-count theater) | KEEP / RELAX / DROP | **RELAX** — replaced by §"Risk-Tiered Test Mandate" |
| 7 | Case mandates, repositories + routers | testing-standards.md:90-103 | review-only | router 401/404/422 classes caught real bugs (per RULE-17 history, CONSTRAINTS.md:807-815) | medium | KEEP / RELAX / DROP | **RELAX** — router status-class coverage stays mandatory (contract); repository case list becomes contract-derived |
| 8 | Fake-not-MagicMock prose dogma (RULE-TEST-01 text) | testing-standards.md:387-457 | prose only (broader than the AST gate) | exception #11 shows legitimate mock needs (CONSTRAINTS.md:1245, 1289-1294) | medium (false conflict w/ interaction testing) | KEEP / RELAX / DROP | **RELAX** — restate as Tier-2 test-doubles-by-purpose formulation; enforcement unchanged |
| 9 | Bare-`MagicMock()` AST scan | `scripts/architecture/_checkers/testing.py:12-41` (tests/ minus tests/fakes/, spec= and allow-comment aware) | blocking via `check_architecture.py` | exceptions #11; commits `48fa9314` (spec= added), `45756ed0` (MagicMock→Fakes migration) | low | KEEP / RELAX / DROP | **KEEP** — narrow, precise, exception-capable |
| 10 | Fake conformance tests | testing-standards.md:128-159; `tests/unit/test_fake_conformance.py` | pytest (`@runtime_checkable` isinstance) | Protocol-change breakage caught by design (intent documented at :130-132); no specific incident found | low | KEEP / RELAX / DROP | **KEEP** |
| 11 | "Repositories are NOT unit-tested" | testing-standards.md:53-56 | review-only | RULE-14 migration bug class supports real-infra testing (CONSTRAINTS.md:519-529) | none | KEEP / RELAX / DROP | **KEEP** — reclassified as Tier-1 #4 (real infra when infra is the subject) |
| 12 | `model_validate()` on every 200/201 | testing-standards.md:105-116 | review-only | schema-drift class per RULE-17 (CONSTRAINTS.md:802-815) | low | KEEP / RELAX / DROP | **KEEP** — as Tier-2/3 recipe with rationale (contract check at HTTP boundary) |
| 13 | Architecture checker embedded as test | testing-standards.md:118-126; `tests/conftest.py:203-212` | pytest subprocess, blocking | gate parity with CI (dual enforcement of RULE-XX) | low | KEEP / RELAX / DROP | **KEEP** |
| 14 | i18n namespace registry test (RULE-16) | testing-standards.md:172-211; CONSTRAINTS.md:762-798 | vitest CI blocking | runtime-only failure class documented (CONSTRAINTS.md:769-776); commits `e824041b`, `e9bf88b2` (NOTES-001 parity) | low | KEEP / RELAX / DROP | **KEEP** |
| 15 | API response contract tests (RULE-17) | testing-standards.md:215-282; CONSTRAINTS.md:802-841 | pytest + PR review | "both sides green, integration broken" class documented (CONSTRAINTS.md:807-815) | low | KEEP / RELAX / DROP | **KEEP** |
| 16 | Router config source-inspection tests (RULE-18) | testing-standards.md:286-333 (`inspect.getsource` + FORBIDDEN_STRINGS) | pytest per-router | RULE-18 rationale (CONSTRAINTS.md:561-565); referenced from CONSTRAINTS.md:1209 | medium (brittle string lists per router) | KEEP / RELAX / DROP | **RELAX** — Tier-3 recipe, apply where hardcoded-config risk exists; consider consolidating generic provider strings into the architecture checker long-term |
| 17 | Config-effect finding marker convention (RULE-18b, post-matrix) | testing-standards.md:335-383 | review-only (checker removed in `f8abb42c`) | matrix over-governance already rolled back once | low | KEEP / RELAX / DROP | **KEEP** — already at correct weight (convention) |
| 18 | `ALLOW_MODEL_REQUESTS = False` | testing-standards.md:508-519; `tests/conftest.py:83` | runtime RuntimeError on real LLM call | pydantic-ai built-in guard; no Narrare-specific incident found | none | KEEP / RELAX / DROP | **KEEP** — Tier-1 #3 backbone |
| 19 | LLM test tool hierarchy (TestModel/FunctionModel/capture) | testing-standards.md:522-601 | none (guidance) | migration notes :618-630 | none | KEEP / RELAX / DROP | **KEEP** — as Tier-2/3 |
| 20 | RULE-01b allow-comment placement in test files | testing-standards.md:603-616 | checker reads `lineno-2..lineno` (mechanical constraint) | format-wrap failures documented in the rule itself | low | KEEP / RELAX / DROP | **KEEP** — required by checker mechanics |
| 21 | Constructor injection, no `__new__` bypass | testing-standards.md:641-651 | review-only | no catch evidence found | none | KEEP / RELAX / DROP | **KEEP** — as Tier-2 |
| 22 | Real Alembic migrations, never `create_all` | testing-standards.md:676-694 | conftest engine setup (convention) | **RULE-14 production crash** (model column without migration; CONSTRAINTS.md:519-529) | medium (test-DB boot time) | KEEP / RELAX / DROP | **KEEP** — strongest catch evidence in the file |
| 23 | Post-assertion pattern (RULE-TEST-02) | testing-standards.md:697-714 | review-only | "API succeeds, second table unwritten" class (:716-717) | low | KEEP / RELAX / DROP | **KEEP** — folded into Tier-1 #7 |
| 24 | Autouse env-var fixture scoping rules | testing-standards.md:719-741 | none | no catch evidence found | none | KEEP / RELAX / DROP | **KEEP** — Tier-3 recipe |
| 25 | Factory helpers over fixtures (`make_*`) | testing-standards.md:743-754 | none | no catch evidence found | none | KEEP / RELAX / DROP | **KEEP** — Tier-3 recipe |
| 26 | Plugin set: xdist / randomly / timeout / hypothesis | testing-standards.md:756-764 | dependency + pytest config | `pytest-randomly` caught ordering flakes (e.g., `e63788d9`, `9ab76c1d` structlog isolation fixes) | low | KEEP / RELAX / DROP | **KEEP** |
| 27 | Auto-tagging (RULE-TEST-03) | testing-standards.md:767-788; `tests/conftest.py:119` | pytest hook, blocking on misuse | enables `-m` selection + strict-markers safety | none | KEEP / RELAX / DROP | **KEEP** |
| 28 | `schema_mutating` marker + two-phase serial + AST collection guard | testing-standards.md:790-828; justfile:311-316, 324-326; ci.yml:562-566; `tests/_schema_guard.py`; `tests/conftest.py:141,149` | collection-fail (loud) + dedicated serial CI phase | shared-schema corruption race documented (:790-814); Q-018 thresholds (:816-820) | medium (extra CI phase) | KEEP / RELAX / DROP | **KEEP** — root-cause fix (per-test-DB) correctly deferred w/ review trigger |
| 29 | RAM-aware xdist worker selection + `test-lowmem` | testing-standards.md:830-863; justfile:311, 324-326; Q-019 | local runner logic | **~25% crash rate** on 9.6 GB w/ `-n auto` before fix (:840-856); commit `3cfd0887` | low | KEEP / RELAX / DROP | **KEEP** |
| 30 | Per-level runtime targets (unit <5 s / int <60 s / e2e <5 min) | testing-standards.md:15-29, 1215 | none (aspirational) | no catch evidence found | none | KEEP / RELAX / DROP | **RELAX** — fold into Tier-3 alongside the measured budgets (row 31); drop prescriptive framing |
| 31 | Collection / runtime budget checkers | `check_pytest_collection_performance.py` (ci.yml:458); `check_test_performance.py` (ci.yml:721-738); Vitest 240 s budget (testing-standards.md:1003-1015) | **warning-only** | snapshot values re-measured live (:881) | low (already soft) | KEEP / RELAX / DROP | **KEEP** — correct weight already |
| 32 | Frontend coverage floors (`lib/**` ≥ 80%, components ratcheted 65%) | testing-standards.md:1043-1049; `packages/web/vitest.config.mts` | blocking (frontend job) | ratcheted like row 2 | low | KEEP / RELAX / DROP | **KEEP** |
| 33 | Frontend stretch-target table | testing-standards.md:1051-1058 | none (self-labeled "not the CI threshold") | no catch evidence found | low | KEEP / RELAX / DROP | **RELAX** — Tier-3 advisory only, or delete with row 4's SSOT rule |
| 34 | Global `motion/react` mock | testing-standards.md:986-1001; `setupTests.ts` | test infra | **51 analysis-panel tests restored** (:994) | medium (keeps real MotionConfig under test — correct scope) | KEEP / RELAX / DROP | **KEEP** |
| 35 | VRT baseline rules (`just vrt` only, verify-before-update) | testing-standards.md:1115-1133; ADR-059; justfile:392-397 | review + recipe discipline | blind-baseline-update risk documented (:1132-1133) | medium (baseline maintenance) | KEEP / RELAX / DROP | **KEEP** — per ADR-059 (binding mock contract) |
| 36 | Snapshot testing rules (RULE-TEST-04) | testing-standards.md:1135-1181 | review-only | dynamic-content snapshot churn class documented | low | KEEP / RELAX / DROP | **KEEP** — as Tier-2/3 discipline |
| 37 | Hypothesis mandate for pure `core/` functions | testing-standards.md:1185-1206 | none | no catch evidence found | medium when forced on unsuitable targets | KEEP / RELAX / DROP | **RELAX** — Tier-2 preference (use where oracle is cheap) |
| 38 | E2E infrastructure (`NARRARE_E2E_TEST`, auth-proxy, wizard/editor patterns, warmup) | testing-standards.md:1210-1326 | conftest + CI (main-branch only) | fake-token 401 class documented (:1240-1243); TipTap autosave nondeterminism (:1272-1279) | low | KEEP / RELAX / DROP | **KEEP** — Tier-3 recipes |
| 39 | Eval separation (pytest vs pydantic-evals; smoke blocking, runtime nightly) | testing-standards.md:926-932, 1330-1410; ADR-032 | CI (smoke blocking, drift warning-only) | program per ADR-032/ADR-083 | low | KEEP / RELAX / DROP | **KEEP** |
| 40 | Test naming convention | testing-standards.md:1414-1423 | none | no catch evidence found | none | KEEP / RELAX / DROP | **RELAX** — keep as convention/recipe, drop mandate flavor |
| 41 | Session-closing protocol (coverage delta, quality notes, fixture list) | testing-standards.md:1451-1467 | none | no catch evidence found; predates ADR-014 | ceremony per session | KEEP / RELAX / DROP | **DROP** — superseded by ADR-014 implementer-owns-tests + per-task report contracts |
| 42 | "What You Do NOT Do" agent-role section | testing-standards.md:1427-1432 | none | contradicts ADR-014 role model (ADR-014:41-47) | stale role guidance | KEEP / RELAX / DROP | **DROP** — stale; roles governed by AGENTS.md hierarchy |
| 43 | "Context You Load Automatically" section | testing-standards.md:1435-1447 | none | references 4 nonexistent files (verified absent) | actively misleading | KEEP / RELAX / DROP | **DROP** — broken references |
| 44 | "Maintained by: Testing Agent" header | testing-standards.md:7 | none | role dissolved by ADR-014 | misleading ownership | KEEP / RELAX / DROP | **DROP** (fix header :7 during restructure; owner = Architecture per SSOT table, CONSTRAINTS.md:1348) |
| 45 | RULE-23 type-ignore ratchet (no new undisciplined suppressions) | CONSTRAINTS.md:1019; `check_architecture.py` `# type: ignore` scan + baseline comparison in CI (CONSTRAINTS.md:1214) | blocking (pre-commit + CI) | fired 3× in one wave — every firing re-typed, none baselined (2026-09-12) | low | KEEP / RELAX / DROP | **KEEP** |
| 46 | Per-variable prompt-integrity ratchet + STALE-BASELINE detection | `scripts/architecture/_checkers/prompt_integrity.py` via `check_architecture.py --prompt-integrity`; baseline `scripts/architecture/ai-gate-baseline.json` | blocking; resolved debt must be pruned from the baseline, not accumulated (`[STALE-BASELINE]`) | landed `9a9a77fe` | low | KEEP / RELAX / DROP | **KEEP** |
| 47 | PROMPT-L2-HEADERS header governance (system.md `##` allowlist) | `scripts/architecture/_checkers/_check_system_headers.py` (RULE_ID :53), run within prompt-integrity checks; allowlist 7 → 0 | blocking (architecture gate) | program completed `9f4c7519` | low | KEEP / RELAX / DROP | **KEEP** |

**Recommendation totals: KEEP 34 · RELAX 9 · DROP 4.** (Rows 45-47 are gates
landed after this draft was written — added for completeness; all KEEP.)

Note on rows 1-3 (coverage gates): the external review's claim of "hard
90/95% gates" was factually wrong; the ratchet is already the proportionate
mechanism the review asked for. Rows 4 and 33 are where the *documentation*
wrongly implies harder gates than exist — the fix is deleting the duplicated
numbers, not touching enforcement.

---

## Consequences

**Positive:**
- Every rule's normativity becomes explicit: 8 principles that always hold,
  preferences with escape hatches, recipes with none.
- The London-School-vs-Fakes question is dissolved structurally
  (Tier 2 test-doubles-by-purpose).
- Number duplication is eliminated → one drift class fewer for
  `check_doc_drift.py` / `check_gate_drift.py` to chase.
- The document shrinks materially (rows 41-44 dropped; large recipe blocks
  compress into Tier-3 referenced patterns; duplicated tables removed).
- Test-count theater (3-case quota) is replaced by risk-derived coverage.

**Negative / Tradeoffs:**
- One-time restructure risk: deep links into testing-standards.md
  (from AGENTS.md, sub-AGENTS files, training prompts) must be re-validated.
- Tier boundaries need maintenance discipline: new rules must be assigned a
  tier at birth, or the flatness regrows.
- Reviewers must learn the tier vocabulary before it pays off.

**Constraints introduced:**
- None to CONSTRAINTS.md from this ADR. **RULE-10 phrasing proposal
  (separate governance, explicitly not enacted here):** keep RULE-10's
  existence mandates (every new service method → unit test; every new router
  endpoint → integration test; test-file mirroring) unchanged; move the
  *case-count* guidance out of any RULE-flavored text into the Tier-2/mandate
  layer; align RULE-10's numeric line (CONSTRAINTS.md:726-727) to reference
  the script SSOT instead of restating 90/80. Any such edit follows the
  CONSTRAINTS.md:3-6 amendment process (PR + decisions entry).
- Enforcement mapping stays fully intact: this ADR changes no script, no CI
  job, no checker. `check_architecture.py`, `check_module_coverage.py`,
  `check_test_coverage_gaps.py`, `tests/_schema_guard.py`,
  `tests/conftest.py` hooks — all untouched.

---

## Implementation Notes

**What moves where (restructure map):**

| Current section (testing-standards.md) | Target tier |
|---|---|
| Three levels + "lowest level" rule (:11-34) | Tier 1 #2, #3 |
| Per-method quotas (:40-56, 90-103) | replaced by Risk-Tiered Mandate |
| Contract/cross-layer testing (:118-383) | Tier 1 #6 + Tier 3 recipes (RULE-16/17/18 stay referenced) |
| Mocking standards (:387-499) | Tier 2 (doubles-by-purpose) + Tier 3 (Fake pattern) |
| LLM testing (:502-630) | Tier 1 #5 + Tier 2/3 |
| Fixtures/infra (:634-764) | Tier 2 (#injection) + Tier 3 |
| schema_mutating / xdist / budgets (:767-933) | Tier 3 recipes + machine-SSOT references |
| Coverage standards (:936-963) | pointer to `pyproject.toml` + scripts (numbers deleted) |
| Frontend (:967-1181) | Tier 2 (Testing Library) + Tier 3 |
| Hypothesis (:1185-1206) | Tier 2 preference |
| E2E (:1210-1326) | Tier 3 |
| Evals (:1330-1410) | unchanged section (ADR-032), referenced |
| Naming (:1414-1423) | Tier 3 convention |
| Roles/context-load/session-close (:1427-1467) | dropped (rows 41-43) |

Sequencing when accepted: (1) per-row decisions on §7; (2) restructure PR for
testing-standards.md; (3) script-epilog wording fix (row 3, one-line,
bug-fix-sized); (4) optional RULE-10 phrasing PR under CONSTRAINTS amendment
process; (5) ADR status → ✅ Accepted + INDEX.md registration (this draft
deliberately does not edit INDEX.md).

**ADR Implementation Completeness Gate (Gate 12):** Before marking this ADR
as "✅ Implemented", verify all items in the Gate 12 checklist in
`docs/architecture/decisions/ADR-072-pydantic-ai-harness-adoption-strategy.md`
(§ "ADR Implementation Completeness Gate (Gate 12)", :432).

---

## Review Trigger

- [ ] Immediately: user per-row selection on §7 (numbered rows 1-47).
- [ ] After the restructure PR: re-run `check_doc_drift.py` +
  `check_gate_drift.py`; confirm no enforcement semantics changed.
- [ ] After 3 months: measure whether new testing rules were assigned tiers
  at birth (if >20% of new rules are untiered, the model is failing).
- [ ] When Q-018 thresholds hit (5 schema_mutating modules or 60 s phase-2):
  per-test-DB isolation decision — independent of this ADR.
