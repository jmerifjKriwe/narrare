# Q-019 — xdist Worker Crash (OOM) Under `-n auto` on Memory-Constrained Machines

> **Status:** 🟡 Open
> **Blocks:** Nothing (3/4 local runs clean; CI has 16 GB RAM — unlikely to hit)
> **Raised:** 2026-08-08
> **Source:** Worker crash during `just test` validation (schema_mutating enforcement PR)

---

## Symptom

During `just test` (= `pytest tests/ -v -n auto`) on a 4-core / 9.6 GB RAM
machine, one xdist worker crashed (SIGKILL — OOM killer) at ~58% suite progress.
The crash was attributed to
`tests/unit/scripts/test_removed_governance_refs_checks.py::test_clean_baseline_against_real_repo`
— the test running on that worker at the moment of death. The worker left no
Python traceback (SIGKILL cannot be caught), and xdist reported:

```
replacing crashed worker gw1
worker 'gw1' crashed while running 'tests/unit/scripts/...::test_clean_baseline_against_real_repo'
```

## Root Cause

**Accumulated worker memory pressure, not a test-specific defect.**

Evidence:

1. **The victim test's own memory delta is 0 MB.** Measured directly:
   `check_removed_governance_refs()` reads 1,547 markdown files sequentially
   via `rglob("*.md")` + `read_text()`, checking each against 11 literal
   substring tokens, then discarding the content. Peak RSS before and after
   the scan is identical (39 MB in a fresh process). The test does not
   accumulate files in memory.

2. **No Python traceback.** The log shows only `"worker crashed while
   running"` — no assertion error, no exception, no signal handler output.
   This is the SIGKILL signature: the kernel OOM killer selected the
   highest-RSS process and killed it instantly.

3. **Passes 100% in isolation** (3/3 runs, ~5s each) and as a full file
   (10/10 tests).

4. **Passes 3/4 full-suite runs.** Run 1 crashed; runs 2–4 clean with
   identical counts (11285 passed, 54 skipped). pytest-randomly changes the
   seed each run, so the test ordering and worker assignment differ.

5. **The victim is random.** The test was running on gw1 when the worker hit
   the memory limit. Any test assigned to that worker at that moment would
   have been the reported victim. The crash is a function of *total system
   memory vs. 4 concurrent worker processes*, not of this specific test.

## Memory Budget

| Component | This machine | CI (ubuntu-latest) |
|-----------|-------------|-------------------|
| Total RAM | 9.6 GB | 16 GB |
| CPU cores (`-n auto` workers) | 4 | 4 |
| Per-worker headroom (approx.) | ~2.4 GB | ~4 GB |
| spaCy models loaded | No (optional dep, not installed locally) | Yes (`just install-nlp-models`) |

Each xdist worker is a full Python process that imports the entire Narrare
application (FastAPI app, all routers, SQLAlchemy models, pydantic-ai, etc.)
plus the full test suite (~11k test items with their fixtures and fakes). On
9.6 GB with 4 workers, the per-worker budget is tight. By ~58% of the suite,
accumulated fixture state and import overhead can push one worker over the
limit.

CI is **unlikely** to hit this: the ubuntu-latest runner has 16 GB RAM (~4 GB
per worker headroom). The local dev machine (9.6 GB) is the primary risk.

## Relation to the schema_mutating Enforcement PR

**None.** The enforcement guard (`tests/_schema_guard.py` +
`tests/conftest.py` `_enforce_schema_mutating_guard`) adds ~1 MB of cached
module-source strings during collection — negligible vs. the ~2 GB per-worker
base footprint. The guard only inspects integration-test modules; the crash
victim is a unit test. The test file predates this PR (commit `850c72f4`,
CR-08).

## Options

- **A — Reduce local parallelism:** change the justfile `test` recipe to
  `-n 2` (or `--maxprocesses=2`) on machines with <16 GB RAM. Halves memory
  pressure at the cost of ~2× slower local test runs. Could be gated on a
  env var or a dedicated low-memory recipe alias (does not exist yet).
- **B — Mark repo-scanning tests serial:** `test_clean_baseline_against_real_repo`
  (and similar whole-repo filesystem scans) could carry a marker that routes
  them to a serial phase, reducing peak concurrent memory. But the crash is
  NOT caused by this test's memory — it's the *worker's* accumulated state.
  Marking the victim test serial would just shift the crash to a different
  random victim.
- **C — Document and accept:** the crash rate is ~25% locally (1/4 runs) on a
  9.6 GB machine, 0% on CI (16 GB). Rerun on crash. This is the lowest-effort
  option until the test count or app import footprint grows further.
- **D — Per-worker memory limit + retry:** configure xdist to detect worker
  death and retry the test on a fresh worker. pytest-xdist does restart
  crashed workers (`"replacing crashed worker"`) but does NOT retry the test
  that was running when the crash occurred — it marks it FAILED.

## Affected Areas

- `justfile` — `test` recipe (`-n auto`, no memory guard)
- `tests/unit/scripts/test_removed_governance_refs_checks.py` — the observed
  victim (but any test can be the victim; this file is not special)
- `.github/workflows/ci.yml` — unit test job uses `-n auto --dist loadfile`
  (CI is unlikely to hit OOM with 16 GB)

## Related

- Q-018 — Per-test-DB isolation for schema-mutating tests (same "shared
  resource under parallelism" pattern, different resource: memory vs. schema)

---

> **Status:** 🟡 Open — pre-existing memory-pressure flake under xdist on
> machines with <16 GB RAM. Unrelated to the schema_mutating enforcement PR.
> CI (16 GB) is unlikely to hit it. No fix in this PR; rerun on crash.
