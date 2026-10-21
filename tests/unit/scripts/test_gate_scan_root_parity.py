"""Gate scan-roots parity tests — both RULE-04 gates scan the same roots.

The python-size walk (``scripts/check_python_file_size.py::
_iter_python_sources``) and the architecture scan roots
(``scripts/architecture/scanner.py::DEFAULT_SCAN_ROOTS``) drifted apart
historically: ``evals/`` was in the python-size walk but not in the
architecture scanner's roots. Unified 2026-08-19 (evals code is real
production code under limits, per 2c6a3b3d).

Since the 2026-08-19 fix-round, the python-size walk's root set is the
module-level constant ``PYTHON_SIZE_SCAN_ROOTS`` (not a candidate list
inside the walk): the behavioral walk skips nonexistent directories, so
it alone cannot detect a unilateral ADD — the constant-equality tests
below can, and the monkeypatch test proves the constant is load-bearing.

Extracted from ``test_check_python_file_size.py`` (RULE-04 split at the
400-line test hard limit) — the parity contract is a cross-gate concern
importing from BOTH gates, not python-size-internal logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.check_python_file_size as check_python_file_size  # noqa: E402
from scripts.architecture.scanner import DEFAULT_SCAN_ROOTS  # noqa: E402
from scripts.check_python_file_size import (  # noqa: E402
    PYTHON_SIZE_SCAN_ROOTS,
    _iter_python_sources,
)

# The pinned root contract of BOTH RULE-04 gates. These tests fail on any
# UNILATERAL root change; a coordinated root change must update this literal
# together with both gates. ``benchmark`` joined 2026-08-27 (kb-benchmark
# runner Task 1 — RULE-04 limits apply to benchmark code per plan Global
# Constraints; the ADR-083 manually-only carve-out governs CI test jobs,
# not the size/architecture gates). ``app`` joined with the v2 tree: it is
# production code and gets the same limits and AST checkers as apps/.
EXPECTED_GATE_SCAN_ROOTS: tuple[str, ...] = (
    "app",
    "apps",
    "packages",
    "scripts",
    "tests",
    "evals",
    "benchmark",
)


class TestScanRootParity:
    """Both RULE-04 gates must scan the same directory roots."""

    def test_walk_roots_equal_expected_gate_roots(self, tmp_path: Path) -> None:
        """The python-size walk visits exactly the pinned gate roots."""
        for name in EXPECTED_GATE_SCAN_ROOTS:
            directory = tmp_path / name
            directory.mkdir()
            (directory / "module.py").write_text("x = 1\n", encoding="utf-8")

        files = _iter_python_sources(tmp_path)

        walked = {f.parent.relative_to(tmp_path).as_posix() for f in files if f.parent != tmp_path}
        assert walked == set(EXPECTED_GATE_SCAN_ROOTS)

    def test_architecture_default_scan_roots_equal_expected_gate_roots(self) -> None:
        """The architecture scanner's default roots equal the pinned gate roots."""
        assert DEFAULT_SCAN_ROOTS == EXPECTED_GATE_SCAN_ROOTS

    def test_python_size_scan_roots_constant_equal_expected_gate_roots(self) -> None:
        """The python-size gate's hoisted root constant equals the pinned roots.

        Add-side guard: the behavioral walk test above skips a unilaterally
        ADDED root whose directory does not exist; this direct constant
        comparison does not.
        """
        assert PYTHON_SIZE_SCAN_ROOTS == EXPECTED_GATE_SCAN_ROOTS

    def test_gate_scan_root_constants_bilaterally_equal(self) -> None:
        """Both gates' root constants are equal — a unilateral add or
        removal on EITHER side fails here."""
        assert set(PYTHON_SIZE_SCAN_ROOTS) == set(DEFAULT_SCAN_ROOTS)

    def test_walk_consumes_scan_roots_constant_add_side_teeth(self, tmp_path: Path) -> None:
        """Add-side regression: the walk really consumes the constant.

        Mutating ``PYTHON_SIZE_SCAN_ROOTS`` with an extra, populated root
        makes the walk visit that root — proving the constant is
        load-bearing and the equality tests above guard real behavior.
        If the walk ever stops consuming the constant (e.g. a re-hardcoded
        candidate list), this test fails.
        """
        rogue = tmp_path / "rogue_root"
        rogue.mkdir()
        (rogue / "module.py").write_text("x = 1\n", encoding="utf-8")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                check_python_file_size,
                "PYTHON_SIZE_SCAN_ROOTS",
                (*PYTHON_SIZE_SCAN_ROOTS, "rogue_root"),
            )

            files = _iter_python_sources(tmp_path)

        assert rogue / "module.py" in files

    def test_directories_outside_gate_roots_not_walked(self, tmp_path: Path) -> None:
        """A directory outside the gate roots is invisible to the walk."""
        decoy = tmp_path / "not_a_scan_root"
        decoy.mkdir()
        (decoy / "module.py").write_text("x = 1\n", encoding="utf-8")

        files = _iter_python_sources(tmp_path)

        assert files == []

    def test_root_level_python_files_collected(self, tmp_path: Path) -> None:
        """Documented asymmetry: the walk also covers root-level ``*.py``
        (e.g. repo-root conftest.py); the architecture scanner's scan roots
        are directories only."""
        (tmp_path / "conftest.py").write_text("x = 1\n", encoding="utf-8")

        files = _iter_python_sources(tmp_path)

        assert tmp_path / "conftest.py" in files
