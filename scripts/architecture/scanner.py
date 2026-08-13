"""Incremental architecture scan contract (RULE-03).

Defines the :class:`ArchitectureScanPort` Protocol and a stub
:class:`ArchitectureScanner`. Full implementation arrives in Task 5;
this module establishes the binding contract first (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from scripts.architecture.types import CheckResult

from scripts.architecture.helpers import ROOT

# RULE-18: named constant, not a literal at the call site.
DEFAULT_SCAN_ROOTS: tuple[str, ...] = ("apps", "packages", "scripts", "tests")


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
        If pyproject.toml is in ``files``, fall back to FULL scan.
        Rationale: ``_validate_exception_consistency`` checks inline
        ``# narrare: allow`` markers against the pyproject.toml exceptions
        register.  A removed register entry would make an unchanged file's
        marker unregistered — incremental would miss it.

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

    Full implementation in Task 5 — currently a stub whose :meth:`scan`
    raises :class:`NotImplementedError`.
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
