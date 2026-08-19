"""Gate scan-roots parity tests — both RULE-04 gates scan the same roots.

The python-size walk (``scripts/check_python_file_size.py::
_iter_python_sources``) and the architecture scan roots
(``scripts/architecture/scanner.py::DEFAULT_SCAN_ROOTS``) drifted apart
historically: ``evals/`` was in the python-size walk but not in the
architecture scanner's roots. Unified 2026-08-19 (evals code is real
production code under limits, per 2c6a3b3d).

Extracted from ``test_check_python_file_size.py`` (RULE-04 split at the
400-line test hard limit) — the parity contract is a cross-gate concern
importing from BOTH gates, not python-size-internal logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture.scanner import DEFAULT_SCAN_ROOTS  # noqa: E402
from scripts.check_python_file_size import _iter_python_sources  # noqa: E402

# The pinned root contract of BOTH RULE-04 gates. These tests fail on any
# UNILATERAL root change; a coordinated root change must update this literal
# together with both gates.
EXPECTED_GATE_SCAN_ROOTS: tuple[str, ...] = ("apps", "packages", "scripts", "tests", "evals")


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
