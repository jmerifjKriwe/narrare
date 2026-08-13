# Pre-commit Runtime Optimization — Implementation Plan

> **For agentic workers:** Each task is independently testable before commit.
> Steps use checkbox (`- [ ]`) syntax for tracking.
> **Binding decisions:** D1 (stage reorg + incremental check_architecture),
> D2b (adoption → manual), D3a–c (just verify overhaul). See
> `docs/development/` analysis session 2026-08-13.

**Goal:** Bring the pre-commit hook runtime reliably under the 120s budget
without quality loss and without shifting expensive checks to CI, by moving
slow non-mutating hooks to a new pre-push stage and making
`check_architecture.py` scan only changed files in pre-commit.

**Architecture:** The pre-commit stage keeps only fast governance hooks
(<2s each), mutating hooks (ruff/biome/openapi), and sole-local gates.
Slow CI-backed hooks (`pyright`, `pyright-tests`, `bandit`) move to a
**pre-push** stage (local, not CI). `check_architecture.py` gains an
**incremental scan mode** (RULE-03 contract below): in pre-commit it
scans only staged `.py` files; standalone (`just check-architecture`, CI)
keeps the full-tree default. `just verify` drops its `check` duplication
and gains RAM-safe defaults plus a new `verify-quick` recipe.

**Tech Stack:** Python 3.14, pre-commit (local hooks), just, pytest-xdist,
GitHub Actions CI (unchanged — all CI jobs run scripts directly, not
pre-commit).

## Global Constraints

- **RULE-03:** The incremental scan capability has a Protocol contract
  (`ArchitectureScanPort`, defined below) BEFORE any implementation slice.
- **RULE-04:** Every new file stays under the relevant line limit
  (scripts/ default 400).
- **RULE-06:** One responsibility per file — the scan orchestrator is a
  separate module from the CLI entry point.
- **RULE-18:** Named constants for thresholds (RAM cutoff, etc.), no
  hardcoded literals at call sites.
- **No quality loss:** every hook that currently runs still runs — either
  at pre-commit (fast) or pre-push (slow). CI backing is unchanged.
- **Package sizing:** each task ≤3 files / ≤250 new LOC.
- **Regression-first:** the incremental scan has a failing parity test
  before implementation (Task 4 → Task 5).
- **Pre-push hook must be installed** before the stage reorg takes effect
  (Task 1 before Task 2).

---

## RULE-03 Contract — Incremental Architecture Scan

This contract is the binding interface specification. Task 4 creates the
Protocol module + failing parity test; Task 5 implements against it.

### Contract: `ArchitectureScanPort`

**File:** `scripts/architecture/scanner.py` (new)

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from scripts.architecture.types import CheckResult

# RULE-18: named constant, not a literal at the call site.
DEFAULT_SCAN_ROOTS: tuple[str, ...] = ("apps", "packages", "scripts", "tests")

# RAM threshold below which the pyproject.toml guard is most critical
# (fewer workers = slower feedback = more temptation to skip).
_PYPROJECT_GUARD_DOC = (
    "If pyproject.toml is in `files`, fall back to FULL scan. Rationale: "
    "_validate_exception_consistency checks inline # narrare: allow markers "
    "against the pyproject.toml exceptions register. A removed register entry "
    "would make an unchanged file's marker unregistered — incremental would "
    "miss it."
)


@runtime_checkable
class ArchitectureScanPort(Protocol):
    """Contract for architecture constraint scanning (RULE-03).

    Two modes, selected by the ``files`` argument:

    FULL scan (``files is None``):
        Walk all ``*.py`` files under the scan roots, AST-parse each, and
        run every RULE-XX checker (RULE-01b, 02, 04, 06, 07, 08, 11, 15,
        18, 19). Default for standalone invocations
        (``just check-architecture``, CI architecture job).

    INCREMENTAL scan (``files`` non-empty):
        AST-scan ONLY the ``*.py`` files in ``files`` that fall within the
        scan roots. This is the pre-commit fast-feedback mode.

    Guarantees — per-file parity:
        For any file F, the violations attributed to F are IDENTICAL in
        FULL and INCREMENTAL mode. Every checker in ``scan_file`` operates
        on F's AST + source_lines alone; none reads cross-file state.
        This is verified by a parity test (Task 4).

    pyproject.toml guard:
        """ + _PYPROJECT_GUARD_DOC

    RULE-15 (forbidden files):
        Always runs regardless of mode — it is a cheap ``rglob`` for
        ``middleware.ts`` and is not AST-based.
    """

    def scan(
        self,
        files: "Sequence[Path] | None" = None,
        *,
        config: dict[str, Any] | None = None,
    ) -> "CheckResult":
        """Run architecture checks and return accumulated violations.

        Args:
            files: Paths to scan (INCREMENTAL mode). ``None`` → FULL scan.
                Empty sequence → skip AST scan, only RULE-15 runs.
            config: Override config (testing). Defaults to pyproject.toml.
        """
        ...
```

### Mode-selection semantics (CLI)

The CLI entry point (`check_architecture.py`) translates argv to the
contract:

| Invocation | `--incremental` | positional files | Contract call |
|---|---|---|---|
| `just check-architecture` / CI | absent | — | `scan(files=None)` → FULL |
| pre-commit (staged .py) | present | `file1.py file2.py` | `scan(files=[f1, f2])` → INCREMENTAL |
| pre-commit (no .py staged) | present | (none) | `scan(files=[])` → RULE-15 only |

The `--incremental` flag disambiguates "standalone full scan" (no flag,
no files) from "pre-commit, nothing relevant changed" (flag, no files).
This avoids relying on environment detection.

### File filtering (`_select_files`)

Pre-commit passes paths relative to the repo root. The scanner resolves
them against `ROOT` and filters:

1. Skip non-`.py` files (except `pyproject.toml` → triggers guard).
2. Skip files outside scan roots (`apps/`, `packages/`, `scripts/`, `tests/`).
3. Skip deleted files (`not path.exists()` → `scan_file` already handles
   `OSError`, but skipping early avoids needless work).

### Parity test strategy

The parity test (Task 4) does NOT run the real 2470-file scan (14.6s — too
slow for unit tests). Instead it uses a **temp directory** with 3 fixture
`.py` files (one RULE-04 violation, one RULE-07 violation, one clean),
constructs an `ArchitectureScanner` with `scan_roots=[tmp_dir]`, and asserts:

```
incremental_violations(files=[f1, f2, f3])
    == full_violations() restricted to f1, f2, f3
```

The scanner accepts `scan_roots` as a constructor parameter (dependency
injection for testability).

---

## Investigation Summary (grounds every design decision)

### Where does the 14.6s go?

`check_architecture.py` `main()` scans **2470 Python files** (apps: 599,
packages: 385, scripts: 170, tests: 1316). For each file: `read_text` +
`splitlines` + `ast.parse` + **18 independent checker functions**, each
doing its own `ast.walk`. That is ~5.9 ms per file → 2470 × 5.9 ms ≈ 14.6 s.

### Per-file vs whole-tree decomposition

**ALL 18 checkers inside `scan_file` are per-file.** They take
`(rel_path, tree, source_lines, config)` and operate on one file's AST:

| Checker | RULE | Input | Cross-file? |
|---|---|---|---|
| `check_llm_imports` | 01b | tree, lines | No |
| `check_llm_urls` | 01b | tree, lines | No |
| `check_agent_imports` | 01b | tree, lines | No |
| `check_agent_instantiation` | 01b | tree, lines | No |
| `check_prompt_building` | 02 | tree, lines | No |
| `check_app_layer_prompt_loader` | — | tree, lines | No |
| `check_prompt_registry_access` | — | tree, lines | No |
| `check_prompt_channel_injection` | — | tree, lines | No |
| `check_inline_prompts` | — | tree, lines | No |
| `check_bare_except` | 11 | tree | No |
| `check_file_size` | 04 | lines | No |
| `check_bare_magic_mock` | — | tree, lines | No |
| `check_bare_async_session` | — | tree, lines | No |
| `check_router_queries` | 06/18 | tree, lines | No |
| `check_hardcoded_model_config` | 19 | tree, lines | No |
| `check_hardcoded_constants` | 18 | tree, lines | No |
| `check_import_direction` | 07 | tree, lines | No |
| `check_export_binary_confinement` | 08 | tree, lines | No |

**Whole-tree checks:**
- `check_forbidden_files` (RULE-15): `rglob("middleware.ts")` in
  `packages/web`. Not AST-based, trivially cheap (< 5 ms). **Always runs.**
- `_validate_exception_consistency` (ADR-028): validates per-file inline
  `# narrare: allow` markers against the `pyproject.toml` exceptions
  register. Per-file by construction (uses `start_index` to validate only
  newly-added approvals). **Risk:** if `pyproject.toml`'s exceptions
  section changes (entry removed), an unchanged file's marker becomes
  unregistered — incremental would miss it. **Guard:** if `pyproject.toml`
  is in the changed set → fall back to FULL scan.

### Is incremental worth it?

**Yes — definitively.** If 3 files changed: 3 × 5.9 ms ≈ 0.02 s instead of
14.6 s (730× speedup). Even a 50-file commit: ~0.3 s. The cost is linearly
proportional to changed-file count; the ceiling is always below full-scan.
No "fake incremental" concern — the checkers are per-file by construction.

### Cheaper optimization exists?

No alternative that preserves correctness. The only other lever — caching
AST parse results across runs — would require a persistent cache invalidation
strategy (which file's AST changed?), which is strictly harder than
"pre-commit tells us which files changed." Incremental is the simplest
correct solution.

---

## Tasks

### Task 1: Install pre-push hook in dev-setup

**Files:**
- Modify: `justfile:98-109` (`dev-setup`)
- Modify: `justfile:112-124` (`dev-setup-min`)

**Why first:** the pre-push stage (Task 2) is inert until
`.git/hooks/pre-push` exists. This must land before or with the stage move.

- [ ] **Step 1: Add `--hook-type pre-push` to `dev-setup`**

In `dev-setup` (line 103), change:
```
pre-commit install --install-hooks
```
to:
```
pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
```

- [ ] **Step 2: Add `--hook-type pre-push` to `dev-setup-min`**

In `dev-setup-min` (line 116), apply the same change.

- [ ] **Step 3: Add one-time migration note**

Add a comment above both recipes:
```
# NOTE: existing devs (pre-2026-08-13) must re-run `just dev-setup-min`
# or `pre-commit install --hook-type pre-push` once to activate the
# pre-push stage. New clones get it automatically.
```

- [ ] **Step 4: Verify**

```bash
pre-commit uninstall  # remove existing hooks
just dev-setup-min    # re-install
test -f .git/hooks/pre-push && echo "OK" || echo "MISSING"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add justfile
git commit -m "chore(dev-setup): install pre-push hook stage

Existing devs must re-run just dev-setup-min once to activate
the pre-push stage required by the upcoming stage reorganization."
```

---

### Task 2: Move slow hooks to pre-push stage

**Files:**
- Modify: `.pre-commit-config.yaml` (3 hook blocks)

**Binding decision:** D1 main — pyright, pyright-tests, bandit →
`stages: [pre-push]`. CI still backs them (typecheck job, security job).
No quality loss: these run once per push, not on every commit.

- [ ] **Step 1: Move `pyright` to pre-push**

In the `pyright` hook block (lines 215-221), change:
```yaml
        stages: [pre-commit]
```
to:
```yaml
        stages: [pre-push]
```

- [ ] **Step 2: Move `pyright-tests` to pre-push**

In the `pyright-tests` hook block (lines 225-232), change:
```yaml
        stages: [pre-commit]
```
to:
```yaml
        stages: [pre-push]
```

- [ ] **Step 3: Move `bandit` to pre-push**

In the `bandit` hook block (lines 235-240), add `stages`:
```yaml
      - id: bandit
        name: Security (Bandit)
        entry: uv run bandit -c pyproject.toml
        language: system
        types: [python]
        require_serial: false
        stages: [pre-push]
```

- [ ] **Step 4: Verify pre-commit stage skips them**

```bash
pre-commit run pyright --hook-stage pre-commit 2>&1 | grep -q "skipped" && echo "OK" || echo "FAIL"
pre-commit run bandit --hook-stage pre-commit 2>&1 | grep -q "skipped" && echo "OK" || echo "FAIL"
```
Expected: both `OK`

- [ ] **Step 5: Verify pre-push stage runs them**

```bash
pre-commit run pyright --hook-stage pre-push --all-files
```
Expected: pyright runs (exit 0 on clean tree).

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "perf(pre-commit): move pyright + bandit to pre-push stage

These hooks are 1:1 duplicates of CI blocking gates (typecheck job,
security job) and together consume ~36s warm / ~80s cold. Moving them
to pre-push keeps fast commits while preserving the local gate.

CI backing unchanged — ci.yml runs them directly (not via pre-commit)."
```

---

### Task 3: Move adoption-score to manual stage

**Files:**
- Modify: `.pre-commit-config.yaml` (1 hook block, lines 42-52)

**Binding decision:** D2b — the `adoption-score` hook exits 1 locally
because it needs `.evidence/*.json` markers that only CI regenerates
(`run_all_probes.py`). CI is the authoritative regenerator. Moving to
`stages: [manual]` means it never blocks a commit locally; run it
explicitly with `pre-commit run adoption-score --hook-stage manual` or
`just check-adoption`.

- [ ] **Step 1: Change adoption-score stage**

In the `adoption-score` hook block (lines 42-52), change:
```yaml
        stages: [pre-commit]
```
to:
```yaml
        stages: [manual]
```

Keep the `args: ["--evidence-dir", ".evidence"]` and the comment block
explaining ADR-056.

- [ ] **Step 2: Verify it no longer runs at pre-commit**

```bash
pre-commit run adoption-score --hook-stage pre-commit 2>&1 | grep -q "skipped" && echo "OK" || echo "FAIL"
```
Expected: `OK`

- [ ] **Step 3: Verify manual invocation still works**

```bash
pre-commit run adoption-score --hook-stage manual --all-files
```
Expected: runs (exit code depends on evidence state — non-zero is OK if
`.evidence/` is stale; the point is it runs, not that it passes).

- [ ] **Step 4: Verify `just check-adoption` still works**

```bash
just check-adoption
```
Expected: runs `scripts/check_adoption.py --evidence-dir .evidence` directly.

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "fix(pre-commit): move adoption-score to manual stage

The hook exits 1 locally because .evidence/*.json markers are only
regenerated by CI (run_all_probes.py). CI is the authoritative
regenerator; the local hook was a read-only false-failure gate.

stages: [manual] — run explicitly via pre-commit run --hook-stage manual
or just check-adoption."
```

---

### Task 4: Incremental scan — contract module + failing parity test

**Files:**
- Create: `scripts/architecture/scanner.py` (~110 LOC — Protocol + stub)
- Create: `tests/unit/scripts/test_architecture_incremental.py` (~130 LOC)

**Binding decision:** D1 sub-c — check_architecture gains incremental mode.
This task is RULE-03 contract-first + regression-first (failing test).

**Interfaces:**
- Produces: `ArchitectureScanPort` Protocol, `ArchitectureScanner` class
  (stub: `scan()` raises `NotImplementedError`), `DEFAULT_SCAN_ROOTS`
  constant.
- Consumes: `scripts.architecture._checkers.scan_file`,
  `scripts.architecture.types.CheckResult`,
  `scripts.architecture.helpers.{ROOT, load_config}`.

- [ ] **Step 1: Create the contract module with a stub**

Create `scripts/architecture/scanner.py` with the `ArchitectureScanPort`
Protocol (verbatim from the RULE-03 Contract section above) plus a stub
`ArchitectureScanner`:

```python
class ArchitectureScanner:
    """Concrete implementation of ArchitectureScanPort.

    Full implementation in Task 5 — currently a stub.
    """

    def __init__(
        self,
        scan_roots: list[Path] | None = None,
    ) -> None:
        self._scan_roots = scan_roots or [ROOT / r for r in DEFAULT_SCAN_ROOTS]

    def scan(
        self,
        files: Sequence[Path] | None = None,
        *,
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        raise NotImplementedError("Task 5 implements this.")
```

Add the necessary imports (`ROOT`, `load_config`, `CheckResult`,
`scan_file`, `check_forbidden_files` — see Step 2 note).

**Note:** `check_forbidden_files` currently lives in
`scripts/check_architecture.py`. To avoid a circular import
(`check_architecture` → `scanner` → `check_architecture`), move it to
`scripts/architecture/_checkers/forbidden_files.py` in Task 5. For this
stub, import it from `check_architecture` with a `# noqa` and a TODO
comment pointing to Task 5. Alternatively, inline the stub without the
import (the stub raises before reaching the call).

- [ ] **Step 2: Write the failing parity test**

Create `tests/unit/scripts/test_architecture_incremental.py`:

```python
"""Parity test: incremental scan == full scan for each file (RULE-03).

Proves that scanning a subset of files produces the same per-file
violations as a full scan restricted to those files. Uses a temp
directory fixture so the test runs in < 0.1s (not the real 14.6s scan).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.architecture.scanner import ArchitectureScanner
from scripts.architecture.types import CheckResult

# ── Fixture sources ─────────────────────────────────────────────

# A file that violates RULE-04 (too many lines).
_OVERSIZED = "x = 1\n" * 500  # 500 lines, default limit 400

# A file that violates RULE-07 (core imports from api).
_BAD_DIRECTION = (
    "# path: packages/core/narrare_core/bad.py\n"
    "from narrare.api.writing.service import WritingService\n"
)

# A clean file.
_CLEAN = "# path: apps/api/narrare/good.py\nx = 1\n"


@pytest.fixture
def scan_dir(tmp_path: Path) -> Path:
    """Temp directory mimicking scan_roots with 3 fixture files."""
    core = tmp_path / "packages" / "core" / "narrare_core"
    api = tmp_path / "apps" / "api" / "narrare"
    core.mkdir(parents=True)
    api.mkdir(parents=True)
    (core / "oversized.py").write_text(_OVERSIZED)
    (core / "bad_direction.py").write_text(_BAD_DIRECTION)
    (api / "clean.py").write_text(_CLEAN)
    return tmp_path


def _violations_by_file(result: CheckResult) -> dict[str, list[str]]:
    """Group violations by relative file path."""
    grouped: dict[str, list[str]] = {}
    for v in result.violations:
        grouped.setdefault(str(v.file), []).append(v.rule)
    return grouped


class TestIncrementalParity:
    """Incremental scan produces identical per-file results to full scan."""

    def test_incremental_matches_full_on_all_files(self, scan_dir: Path) -> None:
        """Scanning all 3 files incrementally == full scan."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])

        full = scanner.scan(files=None)
        incr = scanner.scan(files=[
            scan_dir / "packages" / "core" / "narrare_core" / "oversized.py",
            scan_dir / "packages" / "core" / "narrare_core" / "bad_direction.py",
            scan_dir / "apps" / "api" / "narrare" / "clean.py",
        ])

        assert _violations_by_file(full) == _violations_by_file(incr)

    def test_incremental_subset_matches_full_subset(self, scan_dir: Path) -> None:
        """Scanning 1 file incrementally == that file's full-scan violations."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])
        target = scan_dir / "packages" / "core" / "narrare_core" / "oversized.py"

        full = scanner.scan(files=None)
        incr = scanner.scan(files=[target])

        full_for_target = {
            k: v for k, v in _violations_by_file(full).items()
            if "oversized.py" in k
        }
        incr_result = _violations_by_file(incr)
        assert full_for_target == incr_result

    def test_empty_files_runs_forbidden_only(self, scan_dir: Path) -> None:
        """files=[] → no AST violations, only RULE-15 (forbidden files)."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])
        result = scanner.scan(files=[])

        # No .py violations (RULE-04/07 etc.) — only RULE-15 could appear
        # (and won't, since no middleware.ts in tmp_path).
        ast_rules = {v.rule for v in result.violations if v.rule != "RULE-15"}
        assert ast_rules == set()

    def test_pyproject_toml_triggers_full_scan(self, scan_dir: Path) -> None:
        """pyproject.toml in files → full scan (exception-consistency guard)."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])

        full = scanner.scan(files=None)
        guarded = scanner.scan(files=[scan_dir / "pyproject.toml"])

        assert _violations_by_file(full) == _violations_by_file(guarded)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/unit/scripts/test_architecture_incremental.py -v
```
Expected: FAIL with `NotImplementedError("Task 5 implements this.")`.

- [ ] **Step 4: Commit**

```bash
git add scripts/architecture/scanner.py tests/unit/scripts/test_architecture_incremental.py
git commit -m "feat(arch): add ArchitectureScanPort contract + parity test (stub)

RULE-03 contract-first: defines the incremental scan Protocol and a
failing parity test proving incremental == full per-file. Implementation
follows in the next commit.

The stub raises NotImplementedError; the test exercises the contract
against a temp-directory fixture (3 .py files: RULE-04, RULE-07, clean)."
```

---

### Task 5: Incremental scan — implementation

**Files:**
- Create: `scripts/architecture/_checkers/forbidden_files.py` (~35 LOC)
- Modify: `scripts/architecture/scanner.py` (~90 LOC changed/added)
- Modify: `scripts/check_architecture.py` (~40 LOC changed)

**Interfaces:**
- Consumes: `ArchitectureScanPort` from Task 4,
  `scan_file` from `scripts.architecture._checkers`.
- Produces: working `ArchitectureScanner.scan()`, modified `main()` that
  accepts `--incremental` + positional file args.

- [ ] **Step 1: Move `check_forbidden_files` to its own module**

Create `scripts/architecture/_checkers/forbidden_files.py`:
- Copy `check_forbidden_files()` verbatim from `check_architecture.py:60-85`.
- Import `ROOT` from `scripts.architecture.helpers`.
- Import `CheckResult`, `Violation` from `scripts.architecture.types`.

Add it to `scripts/architecture/_checkers/__init__.py` exports.

Delete the function body from `check_architecture.py` and replace the
call site with an import.

- [ ] **Step 2: Implement `ArchitectureScanner.scan()`**

Replace the stub in `scripts/architecture/scanner.py` with:

```python
class ArchitectureScanner:
    """Concrete implementation of ArchitectureScanPort."""

    def __init__(
        self,
        scan_roots: list[Path] | None = None,
    ) -> None:
        self._scan_roots = scan_roots or [ROOT / r for r in DEFAULT_SCAN_ROOTS]

    def scan(
        self,
        files: Sequence[Path] | None = None,
        *,
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        from scripts.architecture._checkers.forbidden_files import (
            check_forbidden_files,
        )
        from scripts.architecture._checkers import scan_file

        cfg = config if config is not None else load_config()
        result = CheckResult()

        # RULE-15: always runs (cheap glob, not AST-based)
        check_forbidden_files(result)

        py_files = self._select_files(files)

        if py_files is None:
            # FULL scan — walk all .py under scan_roots
            for root in self._scan_roots:
                if not root.exists():
                    continue
                for py_file in root.rglob("*.py"):
                    scan_file(py_file, cfg, result)
        else:
            # INCREMENTAL scan — only the selected files
            for py_file in py_files:
                scan_file(py_file, cfg, result)

        return result

    def _select_files(
        self,
        files: Sequence[Path] | None,
    ) -> list[Path] | None:
        """Filter changed files to .py within scan_roots.

        Returns:
            None → full scan (no files given, or pyproject.toml guard).
            []   → skip AST scan (non-.py changes only).
            [...]→ incremental scan of these files.
        """
        if files is None:
            return None  # FULL scan (standalone / CI)

        # pyproject.toml guard → FULL scan
        if any(f.name == "pyproject.toml" for f in files):
            return None

        resolved_roots = [r.resolve() for r in self._scan_roots]
        selected: list[Path] = []
        for f in files:
            if f.suffix != ".py":
                continue
            resolved = self._resolve(f)
            if not resolved.exists():
                continue  # deleted file
            if not any(
                resolved.is_relative_to(root) for root in resolved_roots
            ):
                continue  # outside scan_roots (e.g. evals/)
            selected.append(resolved)
        return selected

    @staticmethod
    def _resolve(path: Path) -> Path:
        """Resolve a path that may be relative to ROOT or absolute."""
        if path.is_absolute():
            return path.resolve()
        return (ROOT / path).resolve()
```

- [ ] **Step 3: Wire `main()` to use the scanner + `--incremental` flag**

In `scripts/check_architecture.py`, modify `main()`:

```python
def main() -> int:
    parser = argparse.ArgumentParser(description="Narrare Architecture Constraint Checker")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Incremental mode: scan only the files passed as positional "
        "arguments (used by pre-commit pass_filenames). Without this flag, "
        "a full tree scan runs (standalone / CI default).",
    )
    parser.add_argument(
        "--prompt-integrity",
        action="store_true",
        help="Run additional prompt integrity checks.",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="Print the enforced RULE-XX identifiers and exit.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to scan (incremental mode). Provided by pre-commit.",
    )
    args = parser.parse_args()

    if args.list_rules:
        _print_enforced_rules()
        return 0

    from scripts.architecture.scanner import ArchitectureScanner

    # --incremental with no files → scan(files=[]) (RULE-15 only).
    # No --incremental → scan(files=None) (FULL).
    if args.incremental:
        scan_files: list[Path] | None = [Path(f) for f in args.files]
    else:
        scan_files = None  # FULL scan

    result = ArchitectureScanner().scan(files=scan_files)

    # Prompt integrity checks (unchanged — whole-tree, always full)
    if args.prompt_integrity:
        run_prompt_integrity_checks(result)

    # ... (rest of main: print violations / approved exceptions, return code)
```

Remove the old inline scan loop and `check_forbidden_files` call (now in
the scanner).

- [ ] **Step 4: Run parity test — must PASS**

```bash
uv run pytest tests/unit/scripts/test_architecture_incremental.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 5: Run full check_architecture — must still work**

```bash
just check-architecture
```
Expected: exit 0 (same output as before — full scan, same violations).

- [ ] **Step 6: Run incremental mode manually**

```bash
uv run python scripts/check_architecture.py --incremental apps/api/narrare/writing/router.py
```
Expected: scans only that file, exits quickly (< 1s).

- [ ] **Step 7: Verify check_architecture.py stays under RULE-04 limit**

```bash
just check-python-size
```
Expected: exit 0. (Removing the scan loop + check_forbidden_files should
keep main() well under 400 lines.)

- [ ] **Step 8: Commit**

```bash
git add scripts/architecture/_checkers/forbidden_files.py \
        scripts/architecture/_checkers/__init__.py \
        scripts/architecture/scanner.py \
        scripts/check_architecture.py
git commit -m "feat(arch): implement incremental architecture scan

ArchitectureScanner.scan() implements ArchitectureScanPort:
- files=None → full tree scan (standalone / CI)
- files=[...] → incremental scan of only changed .py files
- pyproject.toml in files → full scan (exception-consistency guard)
- RULE-15 (forbidden files) always runs

check_architecture.py main() gains --incremental flag + positional file
args. Pre-commit wiring (pass_filenames) follows in the next commit.

check_forbidden_files extracted to _checkers/forbidden_files.py (RULE-06).
Parity test: 4/4 pass (incremental == full per-file)."
```

---

### Task 6: Wire incremental mode into pre-commit config

**Files:**
- Modify: `.pre-commit-config.yaml` (1 hook block, lines 5-11)

**Binding decision:** D1 sub-c — the architecture-constraints hook uses
`pass_filenames: true` + `--incremental` entry so pre-commit passes staged
files and the checker scans only those.

- [ ] **Step 1: Update the architecture-constraints hook**

Change:
```yaml
      - id: architecture-constraints
        name: Architecture Constraints
        entry: uv run python scripts/check_architecture.py
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```
to:
```yaml
      - id: architecture-constraints
        name: Architecture Constraints
        entry: uv run python scripts/check_architecture.py --incremental
        language: system
        pass_filenames: true
        always_run: true
        stages: [pre-commit]
```

**Why both `pass_filenames: true` AND `always_run: true`:** always_run
ensures the hook fires on every commit (so RULE-15 forbidden-files always
checks). pass_filenames passes the staged file list for incremental AST
scanning. When no `.py` files are staged, pre-commit runs with zero
positional args → `scan(files=[])` → RULE-15 only.

**Why no `types: [python]` filter:** we want `pyproject.toml` to be passed
when staged (triggers the full-scan guard for exception consistency).
Non-`.py` files are filtered inside `_select_files`.

- [ ] **Step 2: Verify incremental mode activates**

```bash
git add apps/api/narrare/writing/router.py  # or any .py file
pre-commit run architecture-constraints --files apps/api/narrare/writing/router.py
```
Expected: runs fast (< 2s), scans only the one file.

- [ ] **Step 3: Verify full scan still works standalone**

```bash
just check-architecture
```
Expected: full scan (same as before).

- [ ] **Step 4: Verify CI path unaffected**

CI runs `uv run python scripts/check_architecture.py` (no `--incremental`)
→ full scan. No CI YAML change needed. Verify:
```bash
rg "check_architecture" .github/workflows/ci.yml
```
Expected: `uv run --no-sync python scripts/check_architecture.py` (no
`--incremental` flag).

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "perf(pre-commit): architecture-constraints uses incremental scan

pass_filenames: true + --incremental entry → the hook scans only staged
.py files (14.6s → < 0.1s for typical commits). pyproject.toml in the
staged set triggers a full-scan fallback for exception-consistency safety.

Standalone (just check-architecture) and CI remain full-scan by default."
```

---

### Task 7: Simplify `verify` + add `verify-quick`

**Files:**
- Modify: `justfile:386` (`verify`) + add new recipe

**Binding decisions:** D3a (verify → test-all only) + D3c (verify-quick).

- [ ] **Step 1: Change `verify` to drop `check`**

In `justfile:386`, change:
```just
verify: check test-all
```
to:
```just
verify: test-all
```

Update the comment (lines 382-385):
```just
# Validate after every slice/step: full test suite (backend + frontend).
# `check` is dropped — it duplicates pre-commit/pre-push gates that already
# run on commit/push. For the full pre-merge gate, use `just check-full`.
# `verify-quick` (below) is the fast variant: unit + frontend, no integration.
verify: test-all
```

- [ ] **Step 2: Add `verify-quick` recipe**

After the `verify` recipe, add:
```just
# Quick validation: unit tests + frontend tests (no integration, no Docker).
# Use for fast iteration between slices. Full gate is `just verify`.
verify-quick: test-unit test-frontend
```

- [ ] **Step 3: Verify both recipes work**

```bash
just --list | grep -E "verify|verify-quick"
just verify-quick
```
Expected: `verify-quick` listed; runs `test-unit` + `test-frontend`.

- [ ] **Step 4: Check doc-drift for phantom recipe references**

```bash
uv run python scripts/check_doc_drift.py --governance-only
```
Expected: no new findings. (Existing docs reference `just verify` which
still exists — composition changed, recipe name unchanged.)

**Note:** `docs/architecture/implementation-plans/IO-001-export-pipeline.md`
references `just verify` as "green = `just verify` +
`scripts/check_architecture.py`". After this change, `just verify` no
longer includes `check` (which includes check_architecture). The IO-001
doc's Definition of Done still works because it explicitly lists
check_architecture separately. No update needed — the redundancy is
removed, the intent is preserved.

- [ ] **Step 5: Commit**

```bash
git add justfile
git commit -m "perf(just): simplify verify + add verify-quick recipe

verify: drop redundant check (duplicates pre-commit/pre-push gates).
verify-quick: new recipe = test-unit + test-frontend (no integration,
no Docker) for fast slice iteration.

Existing docs referencing just verify are unaffected — the recipe name
is unchanged; only its composition dropped the duplicated check gate."
```

---

### Task 8: RAM-aware test parallelism  ⚠️ NEEDS USER APPROVAL

**Files:**
- Modify: `justfile:277-290` (`test`, `test-lowmem`)

**Binding decision:** D3b — cap default test parallelism to prevent the
OOM killer (Q-019). The mechanism choice below is a **recommendation
pending user approval**.

**Background:** `-n auto` (one worker per core) can SIGKILL a worker on
machines with < 12 GB RAM (Q-019: 9.6 GB machine, 4 workers, crash at
58% suite progress). CI uses 16 GB runners and runs pytest directly
(`uv run pytest tests/unit/ -n auto` in ci.yml:413), NOT via `just test` —
so this change does NOT affect CI.

#### Recommended mechanism: RAM detection via shell

```just
# Run all tests. Worker count is RAM-aware: < 12 GB available → -n 2
# (Q-019 OOM mitigation); otherwise -n auto. CI runs pytest directly
# (not this recipe) and is unaffected.
# See docs/architecture/questions/resolved/Q-019-xdist-worker-crash-oom.md.
test:
    #!/usr/bin/env bash
    set -euo pipefail
    # Detect available RAM (MB). Linux: /proc/meminfo. macOS: sysctl.
    if [ -f /proc/meminfo ]; then
        avail_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    elif command -v sysctl >/dev/null 2>&1; then
        avail_mb=$(( $(sysctl -n hw.memsize) / 1048576 ))
    else
        avail_mb=0
    fi
    # RULE-18: 12288 MB = 12 GB threshold (Q-19 measured ~2.4 GB/worker headroom
    # on 9.6 GB / 4 workers; 12 GB gives ~3 GB/worker with -n auto on 4 cores).
    _RAM_THRESHOLD_MB=12288
    if [ "$$avail_mb" -gt 0 ] && [ "$$avail_mb" -lt "$$_RAM_THRESHOLD_MB" ]; then
        workers=2
    else
        workers=auto
    fi
    uv run pytest tests/ -v -n "$$workers" -m "not schema_mutating"
    uv run pytest tests/integration/ -v -m schema_mutating
```

**Alternative mechanisms (for user to choose):**

| Option | Mechanism | Pro | Con |
|---|---|---|---|
| **A (recommended)** | Shell RAM detection | Optimal on all machines; CI unaffected | ~10 LOC shell; platform-specific branches |
| B | Default `-n 2` always, add `test-fast` (`-n auto`) | Simplest; never OOMs | Slower default on big machines |
| C | Cap at `min(nproc, 4)` | Simple; avoids extreme worker counts | Doesn't address RAM, only CPU |

- [ ] **Step 1: Await user decision on mechanism (A / B / C)**

- [ ] **Step 2: Implement chosen mechanism**

(Implementation depends on the decision. If A: replace the `test` recipe
body with the RAM-detection script above. If B: change `-n auto` → `-n 2`
in `test`, add `test-fast` recipe with `-n auto`. If C: change to
`-n $$(nproc 2>/dev/null | awk '{print ($1 > 4) ? 4 : $1}')`.)

- [ ] **Step 3: Verify on this machine (9 GB RAM)**

```bash
just test --help 2>/dev/null || true
# Run a quick subset to confirm workers=2 is selected:
just test-file tests/unit/core/llm/test_gateway.py
```

- [ ] **Step 4: Commit**

```bash
git add justfile
git commit -m "perf(just): RAM-aware test parallelism (Q-019 OOM mitigation)

<mechanism-specific body>"
```

---

## Global Verification (after all tasks)

Run these after all tasks are committed to confirm no gate drift:

- [ ] **Gate drift check**

```bash
uv run python scripts/check_gate_drift.py
```
Expected: exit 0 (no unregistered drift).

- [ ] **Doc drift check**

```bash
uv run python scripts/check_doc_drift.py
```
Expected: exit 0 (no phantom recipe references).

- [ ] **Architecture constraints (full scan)**

```bash
just check-architecture
```
Expected: exit 0.

- [ ] **Pre-commit all hooks (pre-commit stage)**

```bash
pre-commit run --hook-stage pre-commit --all-files
```
Expected: all non-skipped hooks pass. `pyright`, `pyright-tests`, `bandit`,
`adoption-score` should be skipped (moved to pre-push / manual).

- [ ] **Pre-push hooks**

```bash
pre-commit run --hook-stage pre-push --all-files
```
Expected: `pyright`, `pyright-tests`, `bandit` run and pass.

---

## Execution Order

```
Task 1 (install pre-push hook)
  ↓
Task 2 (move hooks to pre-push)     Task 3 (adoption → manual)
                                      ↓
Task 4 (contract + parity test) ← independent of 1-3
  ↓
Task 5 (implementation)
  ↓
Task 6 (pre-commit wiring)          Task 7 (verify + verify-quick)
                                      ↓
                                    Task 8 (RAM-aware test) ⚠️ needs approval
                                      ↓
                                    Global Verification
```

**Dependency graph:**
- Task 1 → Task 2 (pre-push stage needs the hook installed)
- Task 4 → Task 5 → Task 6 (contract → implementation → wiring)
- Tasks 3, 7, 8 are independent of each other and of 1-2, 4-6
- Task 8 is blocked on user approval (mechanism choice)

**Recommended commit order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → (8 after approval)

---

## Decisions Needing User Approval

### Decision A (Task 8): RAM-detection mechanism for `just test`

**Recommendation:** Option A (shell RAM detection — see Task 8 table).
**Alternatives:** B (default conservative + opt-in `test-fast`), C (nproc cap).
**Why A:** optimal on all machines, CI unaffected (runs pytest directly),
platform branches are ~4 LOC each. **Risk:** if `/proc/meminfo` or
`sysctl` is unavailable (exotic platform), falls back to `workers=auto`
(safe default — same as current behavior, CI has 16 GB).

### Decision B (confirmed, no action needed): changed-file source for incremental

**Resolved in this plan:** `--incremental` flag + pre-commit `pass_filenames: true`.
This disambiguates standalone full-scan (no flag) from pre-commit incremental
(flag + positional args). No environment detection needed. The `pyproject.toml`
guard handles the exception-consistency edge case. **This design decision is
finalized — flagging for transparency, not for approval.**

### Decision C (informational): `ci: skip: [pyright]` line

The `.pre-commit-config.yaml` line 337 (`ci: skip: [pyright]`) is vestigial
— this project does not use pre-commit.ci (the hosted service). After Task 2,
pyright is at pre-push anyway, so `pre-commit run --all-files` (pre-commit
stage) won't run it regardless. **No action required** — the line is inert
and harmless. Noted for completeness.

---

## Implementation Deviations (post-completion notes)

> Honest record of what diverged from the plan during execution. Read this
> if you re-run or adapt this plan.

### Task 8: `$$` escaping in just shebang recipes

The plan's Option-A snippet (Task 8) used `$$avail_mb`, `$_RAM_THRESHOLD_MB`,
and `$$workers`, assuming just 1.x converts `$$` → `$` for bash variables in
shebang recipes. This is **wrong for just 1.51.0**: `$$` → `$` conversion
applies only in non-shebang (plain) recipes. In shebang recipes (`[shebang]`
attribute), just passes the recipe body verbatim to bash, so `$$` is expanded
by bash to the current shell PID — not the intended variable reference. The
fix was to use single `$` (`$avail_mb`, `$workers`) throughout the shebang
body. **Rule: use single `$` for shell variables in just shebang recipes.**

### Task 4: `_PYPROJECT_GUARD_DOC` concatenation pattern is invalid Python

The contract section defines:

```python
_PYPROJECT_GUARD_DOC = (
    "If pyproject.toml is in `files`, fall back to FULL scan. Rationale: "
    "..."
)
```

and then uses it inside the Protocol docstring as:

```python
"""...pyproject.toml guard:
    """ + _PYPROJECT_GUARD_DOC
```

This is syntactically invalid Python (unterminated triple-quoted string +
concatenation outside the string). The actual `scanner.py` implementation
inlines the docstring content directly. **Do not transcribe the concatenation
pattern verbatim from this plan.**

### Tasks 2, 3, 6: verification wording assumes specific pre-commit output

The plan's verification steps use `grep -q "skipped"` to confirm hooks were
moved to a different stage (e.g., `pre-commit run pyright --hook-stage
pre-commit 2>&1 | grep -q "skipped"`). The installed pre-commit version may
output `No hook with id X in stage pre-commit` instead of the word
"skipped". Verify via raw output inspection or exit-code semantics (the hook
should exit 0 with no output when it is not in the requested stage) rather
than grepping for a specific keyword.

### Accepted out-of-scope commits

Two commits were made by the Task-5 implementer during the execution window
and accepted by the user:

- `b3abd68c` — justfile variadic recipe support (unrelated to this plan)
- `462dcd74` — lint `evals/` directory (unrelated to this plan)

These sit in the branch history (`chore/pre-commit-runtime-optimization`)
but are **not part of this plan's scope**. When auditing the branch, filter
them out of the "plan commits" ledger.

### Task 5: ROOT binding — lazy vs. import-time

The `ArchitectureScanner` and `forbidden_files.py` read `helpers.ROOT`
lazily (module-level attribute access, not import-time binding), which honors
test monkeypatching of `helpers.ROOT`. However, the 4 prompt-integrity
checkers (`prompt_integrity`, `_check_i18n`, `_check_variables`,
`_check_intents`) still use an import-time `ROOT` binding (captured in a
module-level variable or function default). This was confirmed **NOT a bug**:
their tests either patch the module binding directly or they are
production-only checks with no test need for ROOT redirection. There is no
"lazy-ROOT contract for all checkers" — only scanner + forbidden_files
were refactored to use lazy access.
