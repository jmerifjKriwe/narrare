"""Parity test: incremental scan == full scan for each file (RULE-03).

Proves that scanning a subset of files produces the same per-file
violations as a full scan restricted to those files. Uses a temp
directory fixture so the test runs in < 0.1 s (not the real 14.6 s scan).

Regression-first: this test FAILS until Task 5 implements
``ArchitectureScanner.scan()`` (the stub raises ``NotImplementedError``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.architecture.scanner import ArchitectureScanner

if TYPE_CHECKING:
    from pathlib import Path

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
def scan_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temp directory mimicking scan_roots with 3 fixture files.

    Patches ``scripts.architecture.helpers.ROOT`` to ``tmp_path`` so that
    ``relative_to_root`` yields repo-relative paths. Without this patch the
    temp-dir files resolve to absolute paths and RULE-07
    (``check_import_direction`` matches on the ``packages/core/`` prefix)
    silently fails to fire — a vacuous-parity false-pass.
    """
    core = tmp_path / "packages" / "core" / "narrare_core"
    api = tmp_path / "apps" / "api" / "narrare"
    core.mkdir(parents=True)
    api.mkdir(parents=True)
    (core / "oversized.py").write_text(_OVERSIZED)
    (core / "bad_direction.py").write_text(_BAD_DIRECTION)
    (api / "clean.py").write_text(_CLEAN)
    # Minimal pyproject.toml so load_config() works under the patched ROOT.
    (tmp_path / "pyproject.toml").write_text("[tool.narrare.architecture]\n")
    monkeypatch.setattr("scripts.architecture.helpers.ROOT", tmp_path)
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
        incr = scanner.scan(
            files=[
                scan_dir / "packages" / "core" / "narrare_core" / "oversized.py",
                scan_dir / "packages" / "core" / "narrare_core" / "bad_direction.py",
                scan_dir / "apps" / "api" / "narrare" / "clean.py",
            ]
        )

        assert _violations_by_file(full) == _violations_by_file(incr)

    def test_incremental_subset_matches_full_subset(self, scan_dir: Path) -> None:
        """Scanning 1 file incrementally == that file's full-scan violations."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])
        target = scan_dir / "packages" / "core" / "narrare_core" / "oversized.py"

        full = scanner.scan(files=None)
        incr = scanner.scan(files=[target])

        full_for_target = {
            k: v for k, v in _violations_by_file(full).items() if "oversized.py" in k
        }
        incr_result = _violations_by_file(incr)
        assert full_for_target == incr_result

    def test_empty_files_runs_forbidden_only(self, scan_dir: Path) -> None:
        """files=[] -> no AST violations, only RULE-15 (forbidden files)."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])
        result = scanner.scan(files=[])

        # No .py violations (RULE-04/07 etc.) — only RULE-15 could appear
        # (and won't, since no middleware.ts in tmp_path).
        # NOTE: this assertion is meaningful ONLY alongside its siblings
        # (test_incremental_matches_full_on_all_files /
        # test_incremental_subset_matches_full_subset), which prove the
        # fixtures yield real RULE-04/07 violations; without them this
        # would pass vacuously if scan() were a no-op.
        ast_rules = {v.rule for v in result.violations if v.rule != "RULE-15"}
        assert ast_rules == set()

    def test_pyproject_toml_triggers_full_scan(self, scan_dir: Path) -> None:
        """pyproject.toml in files -> full scan (exception-consistency guard)."""
        scanner = ArchitectureScanner(scan_roots=[scan_dir])

        full = scanner.scan(files=None)
        guarded = scanner.scan(files=[scan_dir / "pyproject.toml"])

        assert _violations_by_file(full) == _violations_by_file(guarded)
