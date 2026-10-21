# Throughput T21c — stop reporting a 10 s timeout as a worker crash

- **Date:** 2026-10-21
- **Branch:** `brave-egret`
- **Base commit:** `ddd74e23`
- **Status:** done, verified
- **Scope:** the chapter-plan-context test only — the crash *mechanism* is documented, not removed

## 1. Why

T21a proved the crash class is `pytest-timeout` calling `os._exit(1)`, not OOM.
The offending file nevertheless crashed in ~5/8 runs at `-n 4` because its slow
test sits on the 10 s budget. A 10 s timeout must stay a hard guarantee for the
suite, so the fix had to remove *this* crash without loosening the global
budget.

## 2. Part A — report correction

- `scripts/xdist_workers.py`: unchanged. The tuple keeps its unparenthesised
  `except OSError, subprocess.CalledProcessError:` form, which PEP 758 makes
  valid on Python 3.14 and which is exactly what ruff's `py314` formatter emits —
  so it is canonical here, and the source is byte-identical to `ddd74e23`. An
  intermediate `# fmt: skip` that reintroduced the parentheses was reverted:
  fighting the formatter is worse than accepting its output.
- T21b report: status corrected to the committed state (`ddd74e23`).

Commit: `docs(reports): correct the T21b status to the committed state` (report
only).

## 3. Measurement

`pytest tests/integration/chapters/test_chapter_plan_context_api.py --durations=20`.
Note: `timeout_func_only = true` is already in `pyproject.toml`, so the
"with `-o timeout_func_only=true`" run is the configured run; the comparison run
uses `=false`.

Slow test, serial:

| Phase | `func_only=true` | `func_only=false` |
|---|---|---|
| setup | 0.03 s | 0.03 s |
| call | 6.17 s | 6.58 s |
| teardown | 0.18 s | 0.21 s |

`-n 4` (a run that passed): call 8.30 s, setup 1.49 s, teardown 0.18 s.
Crashed runs report no durations for the victim.

**Rule branch taken: the call dominates** (setup+teardown < 20 % of wall).
Instrumenting the call showed where it goes:

```
novel=0.027  c1=2.142  c2=2.198  c3=1.876  summaries=0.004  get=0.007
```

Each content-bearing chapter `POST` blocks ~2 s; the plan-context `GET` is 7 ms.
The blocker is the writing-stats recorder's own short-lived session: its FK
check cannot see the test transaction's uncommitted user/novel rows, so every
non-zero delta waits for the transaction that feeds it
(`writing_stats_record_failed … ForeignKeyViolationError`). That is not a
redundant *endpoint* round trip and the recorder lives outside this task's file
set, so no code fix was invented here.

## 4. Change

`tests/integration/chapters/test_chapter_plan_context_api.py`:

```python
# The endpoint is fast; each content-bearing chapter create blocks ~2 s on the
# writing-stats recorder's separate session (FK check vs. uncommitted test rows),
# so the call needs ~7 s serially and >10 s under -n 4. Perf slice owed.
pytestmark = pytest.mark.timeout(30)
```

`pyproject.toml` untouched: the 10 s suite budget and `timeout_method = thread`
stay in force, and no `timeout_func_only` change was made.

## 5. Evidence

- 8 consecutive `-n 4` runs of the file: **0 crashes / 8**, slowest wall
  25.88 s.
- `just test-file tests/integration/chapters/test_chapter_plan_context_api.py`
  → 6 passed in 20.80 s.
- Negative control, `/tmp/opencode/test_timeout_probe.py` (sleeps 2 s),
  `--timeout=1 --timeout-method=thread -n 2`:
  `worker 'gw0' crashed while running 'test_timeout_probe.py::test_sleeps_past_the_budget'`
  — still a crash, no Timeout traceback. Residual, as expected: the marker
  fixes this test, the mechanism remains for any future slow test.
- `just test-file tests/unit/scripts/test_xdist_workers.py` → 13 passed.
- `uv run --all-packages pyright scripts/xdist_workers.py` → 0 errors.
- `just check-architecture` → GREEN.
- `pre-commit run --files …` → green.

## 6. Documentation

`docs/architecture/questions/resolved/Q-019-xdist-worker-crash-oom.md` gained
"Second mechanism (2026-10-20) — a timeout reported as a crash": the misleading
symptom, the dose-response table, the `os._exit(1)` path, and the rule *check
`--timeout` and the `oom_kill` counter before blaming memory*. The 2026-08-08
OOM diagnosis is unchanged.

## 7. Concerns

- The file-level 30 s marker buys headroom; it does not make the test fast. The
  real defect is the writing-stats recorder blocking ~2 s per content-bearing
  create in the test transaction — a perf slice still owed.
- Any *other* future test over 10 s will still produce "worker crashed"; only
  the Q-019 rule (read `--timeout`, check `oom_kill`) makes that legible.
