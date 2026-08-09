# Q-019 — xdist Worker Crash (OOM) Under `-n auto` on Memory-Constrained Machines

> **Status:** ✅ Resolved (2026-08-08) — Option A (`just test-lowmem` recipe; default unchanged)
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

## Resolution — Option A (low-memory justfile recipe; document; default unchanged)

> **Status:** ✅ Resolved (2026-08-08) — **Option A** chosen.
> **Documentation:** Resolution in this question file + justfile recipe comment +
> `docs/development/testing-standards.md` note. No full ADR (a tooling recipe within
> existing xdist infrastructure — no new pattern/dependency).

### Root cause (identified; pragmatic, not code-fixable)

The root cause is **accumulated per-worker memory pressure** when 4 xdist workers each
import the full Narrare app + ~11 k test items on a machine with < 16 GB RAM. It is a
**hardware-budget reality**, not a code defect: the victim is random, the victim test's
own memory delta is 0 MB, and CI (16 GB, ~4 GB/worker headroom) is unaffected. There is
no in-code "fix" that makes 4 full-app worker processes fit in 9.6 GB once accumulated
footprint exceeds the budget — except reducing parallelism (the standard, correct
response to OOM-under-xdist, which directly addresses "too many worker processes for
available memory").

### Alternatives considered

- **Option B — Mark repo-scanning tests serial.** *Rejected as a non-fix.* The crash
  victim is random; marking the observed victim serial just shifts the crash to the
  next random victim. It does not reduce total worker memory pressure.
- **Option C — Document and accept (rerun on crash).** *Rejected as the sole response.*
  A 25 % local crash rate with "just rerun" is poor DX and hides a real memory
  pressure signal. A working mitigation (Option A) exists and is low-effort; "accept
  and rerun" when a real fix exists is the "good enough for now" anti-pattern (§4).
- **Option D — Per-worker memory limit + retry.** *Rejected.* pytest-xdist restarts a
  crashed worker but **does not retry** the killed test — it marks it FAILED. Native
  retry would need `pytest-rerunfailures` (a **new dependency** → would require an ADR)
  and would mask the underlying pressure by silently retrying (treating the symptom).
  Discard.
- **Option A — Reduce local parallelism (chosen).** A `test-lowmem` recipe (`-n 2` /
  `--maxprocesses=2`) halves memory pressure at ~2× local wall time on constrained
  machines. This is the correct tooling response to a known hardware constraint, not a
  workaround. The default stays `-n auto` (correct for 16 GB / CI).

### Sustainability check

1. *Correct in 3 months?* Yes — the recipe stays valid as long as xdist is used; the
   deeper lever (reducing per-worker import footprint via lazy imports / smaller
   fixtures) is noted below as a long-term option, not required now.
2. *Hard-to-undo coupling?* None — an additive justfile recipe.
3. *Simplest correct solution?* Yes — vs. a new dependency (D) or non-fixes (B/C).
4. *Understandable to next dev?* Yes — the recipe + comment explain *why* `-n auto`
   can OOM locally and *what to do* about it.

### Decision

Add a `test-lowmem` justfile recipe; **do not** change the default `test` recipe
(`-n auto` is correct for CI's 16 GB and for 16 GB dev machines — the default serves
the common/canonical case; CI is the source of truth). Document the memory-budget
reality in `docs/development/testing-standards.md` so developers on < 16 GB machines
know to use `just test-lowmem`.

### Implementation handoff → Platform specialist

1. `justfile` — add after the `test` recipe (around line 279):
   ```just
   # Run all tests with reduced parallelism for machines with < 16 GB RAM.
   # `-n auto` (= one worker per core) can trigger the OOM killer on memory-constrained
   # machines because each xdist worker imports the full app + test suite. Use this on
   # < 16 GB RAM; see docs/architecture/questions/resolved/Q-019-xdist-worker-crash-oom.md.
   # CI (16 GB) and 16 GB dev machines should keep the default `just test`.
   test-lowmem:
       uv run pytest tests/ -v -n 2 --dist loadfile -m "not schema_mutating"
       uv run pytest tests/integration/ -v -m schema_mutating
   ```
2. `docs/development/testing-standards.md` — add a short "Running tests on low-memory
   machines" note: "`-n auto` may SIGKILL a worker on < 16 GB RAM (Q-019); use
   `just test-lowmem` (`-n 2`)."
3. No `ci.yml` change — CI uses 16 GB runners and is unaffected.

**Test plan:** run `just test-lowmem` on the 9.6 GB machine and confirm no OOM crash
across 4 runs (vs. the 25 % crash rate under `-n auto`). `just test` (default) must
remain unchanged and green on 16 GB / CI.

### Long-term lever (not in scope)

The deeper root cause is the **per-worker import footprint** (each worker imports the
full FastAPI app + all routers + SQLAlchemy models + pydantic-ai + ~11 k test items). A
future investigation into lazy imports / smaller fixture scopes / test-suite diet could
lower the per-worker base footprint and raise the `-n auto` ceiling. Track separately;
not needed to resolve this question.

---

> **Status:** ✅ Resolved (2026-08-08) — **Option A**: add `just test-lowmem` (`-n 2`)
> for < 16 GB RAM machines; default `just test` unchanged (CI = 16 GB). Options B/D are
> non-fixes; C-only is rejected (a working mitigation exists).
