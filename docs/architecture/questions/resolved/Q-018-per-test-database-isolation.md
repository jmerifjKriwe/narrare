# Q-018 — Per-Test-Database Isolation for Schema-Mutating Tests

> **Status:** ✅ Resolved (2026-08-08) — Option B (keep enforced two-phase serial; revisit at break-point)
> **Blocks:** Nothing (two-phase serial is the current adequate mitigation)
> **Raised:** 2026-08-08
> **Source:** Architecture review C-2 (migration-test parallelization race)

---

## Question

Should schema-mutating integration tests (alembic downgrade/upgrade
round-trips) run against a **dedicated per-test database** (created from a
template, dropped on teardown) instead of the shared `narrare_test` database?

## Context

`tests/integration/test_migration_0037_round_trip.py` downgrades and
re-upgrades the **shared** test-DB schema mid-run. Under `pytest-xdist`
parallelism (`-n auto`), concurrent tests hit `column "series_id" does not
exist` during the downgrade window, and the migration test can crash workers.

The **current mitigation** (implemented in this review cycle):

1. A `@pytest.mark.schema_mutating` marker routes marked tests to a dedicated
   **serial phase 2** in both `just test` and CI (`pytest tests/integration/
   -m schema_mutating`, no xdist).
2. A **collection guard** (`tests/_schema_guard.py` + `tests/conftest.py`
   `pytest_collection_modifyitems` hook) fails collection loudly if any
   integration test exhibits schema-mutating patterns (alembic `downgrade`,
   `metadata.create_all`/`drop_all`, SQL DDL: `CREATE/DROP/ALTER TABLE`,
   `CREATE/DROP INDEX`, `CREATE/DROP SCHEMA`) without the marker.

This is **disciplined** (enforced, not convention) but not the **root cause**.
The root cause is that schema-mutating tests share a single database with all
other integration tests. Two-phase serial eliminates the concurrency window
but serializes the marked tests (currently 2 modules: the migration round-trip
+ the TRUNCATE-based `test_rotate_encryption_key.py`).

## Options

- **A — Per-test-DB isolation (root-cause fix):** each schema-mutating test
  gets a throwaway database (`CREATE DATABASE … TEMPLATE narrare_test …`), runs
  its downgrade/upgrade cycle there, and drops it on teardown. The test can
  then run **concurrently** with all other tests (no shared-resource mutation).
  Feasible because `test_migration_0037_round_trip.py` already overrides
  `DATABASE_URL` per subprocess (line 48-52). The guard and marker would
  remain as a safety net, but phase-2 serialization could be relaxed.
- **B — Keep two-phase serial (current mitigation):** the marker + guard +
  serial phase 2 are adequate for the current test count (2 modules). The
  serial phase adds ~20s to the full run. Acceptable until the schema-mutating
  test count grows significantly.

## Affected Areas

- `tests/integration/test_migration_0037_round_trip.py` — `_run_alembic`
  overrides `DATABASE_URL` per subprocess (the hook point for per-test-DB).
- `tests/integration/conftest.py` — session-scoped `check_db_available` runs
  `alembic upgrade head` on the shared DB; a per-test-DB approach would need a
  template DB pre-created at head.
- `tests/_schema_guard.py` / `tests/conftest.py` — the guard and marker remain
  as a safety net regardless of which option is chosen.
- `justfile` / `.github/workflows/ci.yml` — phase-2 recipe.

## Related

- `docs/development/testing-standards.md` — `schema_mutating` marker guidance
- `tests/_schema_guard.py` — AST-based schema-mutation detection
- RULE-14 — schema exclusively via Alembic migrations (no `create_all()`)

---

## Resolution — Option B (keep two-phase serial; revisit at a documented break-point)

> **Status:** ✅ Resolved (2026-08-08) — **Option B** chosen.
> **Documentation:** Resolution in this question file. No full ADR (a testing-strategy
> retention within existing xdist/marker infrastructure — no new pattern/dependency).

### Root cause (acknowledged, not fixed now)

The root cause — schema-mutating tests sharing one database with all other integration
tests — is **correctly identified and deliberately contained**, not fixed. The current
mitigation is **enforced**, not convention: the `@pytest.mark.schema_mutating` marker +
`tests/_schema_guard.py` AST collection guard fail collection **loudly** if a
schema-mutating test lacks the marker, so the race cannot silently recur. This is a
legitimate test-phase split for a known shared-resource constraint, not a workaround
(§4): it does not bypass an abstraction or add an undocumented special case.

### Alternatives considered

- **Option A — Per-test-DB isolation (`CREATE DATABASE … TEMPLATE …`).** *Deferred.*
  This is the true root-cause fix, but it is non-trivial infra for the current scale:
  a template DB pre-created at head in the session fixture, per-test CREATE/DROP
  DATABASE (DDL outside transactions → autocommit + maintenance-DB connection), robust
  teardown-under-crash, and fixture management under xdist. The concurrency benefit is
  marginal because schema-mutating tests are inherently rare and serial-eligible.
- **Option B — Keep two-phase serial (chosen).** The enforced mitigation is correct
  (guard prevents silent lapse) and simplest. The serial phase adds ~20 s for **2**
  modules today.

### Sustainability check — the break-point

At what test count does Option B break? Schema-mutating tests grow slowly (~1 per
major migration needing round-trip verification; the second module is a TRUNCATE-based
encryption-key test). The serial phase scales linearly (~10 s/module). **Review
trigger — revisit and move to Option A when EITHER:**

- the `schema_mutating` module count reaches **5**, OR
- the serial phase-2 wall time exceeds **60 s** on CI,

whichever comes first. Below that, the per-test-DB infra complexity is premature
optimisation (YAGNI at scale). The guard + marker remain as the safety net regardless.

### Decision

Keep the current two-phase serial recipe in both `justfile test` (lines 277-279) and
`.github/workflows/ci.yml` (test-integration job, lines 519-524). Keep `tests/
_schema_guard.py` + the `pytest_collection_modifyitems` hook unchanged. Record the
break-point above in `docs/development/testing-standards.md` (§ schema_mutating) so the
review trigger is discoverable.

### Implementation handoff → Platform specialist (docs only — no code change)

1. `docs/development/testing-standards.md` — add a one-paragraph note under the
   `schema_mutating` guidance: "Two-phase serial is the **contained** mitigation, not
   the root-cause fix (per-test-DB isolation, Q-018 Option A). Revisit when
   schema_mutating modules ≥ 5 or serial phase-2 > 60 s."
2. No `justfile` / `ci.yml` / `_schema_guard.py` change.

**Test plan:** none — this decision changes no code. Confirm `just test` two-phase
recipe is unchanged and the guard still trips on an unmarked schema mutation.

---

> **Status:** ✅ Resolved (2026-08-08) — **Option B**: keep enforced two-phase serial.
> Root cause (shared DB) is contained by the collection guard, not fixed; per-test-DB
> (Option A) revisited at the documented break-point (≥ 5 modules or > 60 s phase-2).
