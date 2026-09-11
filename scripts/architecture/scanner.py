"""Incremental architecture scan contract (RULE-03).

Defines the :class:`ArchitectureScanPort` Protocol and its concrete
implementation :class:`ArchitectureScanner`.

Two scan modes, selected by the ``files`` argument:

- FULL scan (``files is None``): walk all ``*.py`` under the scan roots.
- INCREMENTAL scan (``files`` provided): AST-scan only the listed ``*.py``
  files that fall within the scan roots (pre-commit fast feedback).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

from scripts.architecture import helpers
from scripts.architecture.types import CheckResult

# RULE-18: named constant, not a literal at the call site.
# Gate-roots parity (2026-08-19): must stay equal to the python-size gate's
# scan roots (``scripts/check_python_file_size.py``::PYTHON_SIZE_SCAN_ROOTS) —
# pinned by ``tests/unit/scripts/test_gate_scan_root_parity.py::
# TestScanRootParity``. ``evals/`` is included per 2c6a3b3d (evals code is
# real production code under limits); unifying both RULE-04 gates on
# identical roots also subjects evals/ to the full AST checker set.
# ``benchmark/`` joined 2026-08-27 (kb-benchmark runner Task 1): the
# ADR-083 manually-only carve-out excludes benchmark from CI test jobs,
# but the repo's Python standards (incl. RULE-04 size limits and the AST
# checker set) DO apply to benchmark code per the plan's Global
# Constraints — coordinated with the python-size gate + the parity test.
DEFAULT_SCAN_ROOTS: tuple[str, ...] = ("apps", "packages", "scripts", "tests", "evals", "benchmark")


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
        FULL and INCREMENTAL mode for all AST-local checkers (they operate
        on F's AST + source_lines alone). Two checkers read cross-file
        state — ``_validate_exception_consistency`` (pyproject.toml
        exceptions register) and ``check_inline_prompts``
        (adoption-registry.yaml) — which is why edits to those state
        files trigger a FULL scan instead (see "Full-scan guards" below).
        Parity is verified by a parity test (Task 4).

    Full-scan guards (cross-file state triggers):
        If ``pyproject.toml`` or ``scripts/architecture/adoption-registry.yaml``
        is in ``files``, fall back to FULL scan. Rationale:
        ``_validate_exception_consistency`` checks inline ``# narrare: allow``
        markers against the pyproject.toml exceptions register, and
        ``check_inline_prompts`` checks RULE-02 inline-prompt exceptions
        against adoption-registry.yaml. A register/registry-only edit would
        otherwise be skipped by the ``.py`` selection — incremental would
        miss violations that only the changed state file can reveal.

    RULE-15 (forbidden files):
        Always runs regardless of mode — it is a cheap ``rglob`` for
        ``middleware.ts`` and is not AST-based.
    """

    def scan(
        self,
        files: Sequence[Path] | None = None,
        *,
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Run architecture checks and return accumulated violations.

        Args:
            files: Paths to scan (INCREMENTAL mode). ``None`` → FULL scan.
                Empty sequence → skip AST scan, only RULE-15 runs.
            config: Override config (testing). Defaults to pyproject.toml.
        """
        ...


class ArchitectureScanner:
    """Concrete implementation of :class:`ArchitectureScanPort`.

    ``ROOT`` is read lazily via ``helpers.ROOT`` so the binding honors
    runtime reassignment (e.g. test monkeypatching of
    ``scripts.architecture.helpers.ROOT``).
    """

    def __init__(
        self,
        scan_roots: list[Path] | None = None,
    ) -> None:
        self._scan_roots = scan_roots or [helpers.ROOT / r for r in DEFAULT_SCAN_ROOTS]

    def scan(
        self,
        files: Sequence[Path] | None = None,
        *,
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        from scripts.architecture._checkers import scan_file
        from scripts.architecture._checkers.forbidden_files import (
            check_forbidden_files,
        )

        cfg = config if config is not None else helpers.load_config()
        result = CheckResult()

        # RULE-15: always runs (cheap glob, not AST based)
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
            None → full scan (no files given, or a full-scan guard fired).
            []   → skip AST scan (non-.py changes only).
            [...]→ incremental scan of these files.
        """
        if files is None:
            return None  # FULL scan (standalone / CI)

        # pyproject.toml guard → FULL scan
        if any(f.name == "pyproject.toml" for f in files):
            return None

        # adoption-registry.yaml guard → FULL scan. Rationale:
        # ``check_inline_prompts`` reads this registry (cross-file state);
        # a YAML-only edit would otherwise be filtered out by the ``.py``
        # selection below and trigger no re-scan of registered markers.
        if any(f.name == "adoption-registry.yaml" for f in files):
            return None

        resolved_roots = [r.resolve() for r in self._scan_roots]
        selected: list[Path] = []
        for f in files:
            if f.suffix != ".py":
                continue
            resolved = self._resolve(f)
            if not resolved.exists():
                continue  # deleted file
            if not any(resolved.is_relative_to(root) for root in resolved_roots):
                continue  # outside scan_roots (e.g. root-level or docs/ files)
            selected.append(resolved)
        return selected

    @staticmethod
    def _resolve(path: Path) -> Path:
        """Resolve a path that may be relative to ROOT or absolute."""
        if path.is_absolute():
            return path.resolve()
        return (helpers.ROOT / path).resolve()
