# Q-018 — Per-Test-Database Isolation for Schema-Mutating Tests

> **Status:** 🟡 Open
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

> **Status:** 🟡 Open — two-phase serial is the current adequate mitigation;
> per-test-DB isolation is the root-cause fix. Blocks nothing while the
> schema-mutating test count stays small.
