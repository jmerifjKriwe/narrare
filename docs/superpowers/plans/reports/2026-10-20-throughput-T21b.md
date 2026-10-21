# Throughput T21b — testable xdist worker heuristic + low-memory tier

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `ac3b573f`
- **Status:** done, verified (no commit, per task constraints)
- **Scope:** contention guard only — **not** the fix for the worker-crash class

## 1. Why

T21a proved the crash class is `pytest-timeout` calling `os._exit(1)` at the
10 s deadline, not an OOM kill. The RAM heuristic in `justfile` →
`_xdist-workers` nevertheless remains useful as a **contention guard**: on a
low-memory machine, one worker per core makes the suite slower (swap,
page-cache thrash) and pushes tests toward that timeout. The bash recipe was
unverifiable without editing `/proc`, so the decision moved into a stdlib-only
script with unit tests.

## 2. Decision table

| `MemAvailable` | `-n` |
|---|---|
| unknown (`<= 0`) | `auto` |
| `< 4096 MB` | `1` (new low-memory tier) |
| `< 12288 MB` | `2` (existing Q-019 tier) |
| `>= 12288 MB` | `auto` |

Existing tiers keep their exact semantics; 4096 MB is the new tier. The
boundaries live in the `_RamTierLimits` configuration class so RULE-18 sees
named config rather than inline call-site literals.

## 3. Changes

- `scripts/xdist_workers.py` (112 lines): `choose_workers`,
  `available_mb(meminfo_path=MEMINFO_PATH)`, `_meminfo_available_mb`,
  `_sysctl_total_mb`, `main`. `/proc/meminfo` → `MemAvailable` on Linux,
  `sysctl -n hw.memsize` on macOS, `0` (→ `auto`) when neither is readable.
  Import is side-effect free. `sysctl` subprocess carries the repo's justified
  `# nosec B404` / `# nosec B603 B607` comments.
- `justfile` (859 lines): `_xdist-workers` body is now
  `uv run --all-packages --no-sync python scripts/xdist_workers.py`; recipe
  name, callers (`test`, `test-unit`) and platform behaviour unchanged.
- `tests/unit/scripts/test_xdist_workers.py` (104 lines, 13 tests): the 7-case
  table, negative/unknown guard, meminfo parser against temp files (boundary,
  missing key, invalid value, unreadable path + sysctl fallback), and the CLI
  token check.

## 4. Evidence

- `choose_workers`: `0 -> auto`, `1024 -> 1`, `4095 -> 1`, `4096 -> 2`,
  `12287 -> 2`, `12288 -> auto`, `65536 -> auto`.
- `just _xdist-workers` → `2`; machine `MemAvailable` 4284604 kB
  (≈ 4184 MB) → tier `2`, matches.
- `pytest tests/unit/scripts/test_xdist_workers.py -q` → 13 passed.
- `pyright` → 0 errors; `ruff check` / `ruff format --check` → clean.
- `just check-architecture` → exit 0 (new script inside the gate).
- `pre-commit run --files justfile scripts/xdist_workers.py
  tests/unit/scripts/test_xdist_workers.py` → exit 0, 24 hooks passed.

## 5. Concerns

- The recipe now pays a `uv run --no-sync` startup per invocation (tens of ms);
  `--no-sync` avoids an implicit environment sync, matching the task spec.
- Tiers are heuristic and machine-state dependent: `MemAvailable` moves between
  the measurement and the pytest launch, so the guard can pick `1` on a busy
  machine. That is acceptable for a contention guard; it must not be read as
  memory-crash protection.
