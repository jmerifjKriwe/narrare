"""Regression tests for the ADR-049 Phase D D8 ADR-STATUS consistency checker.

Verifies that the checker:
1. Flags INDEX.md status markers that don't match ADR file status.
2. Flags non-canonical status symbols.
3. Passes when INDEX and ADR files agree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.architecture._checkers._check_adr_status_consistency import (
    check_adr_status_consistency,
)
from scripts.architecture.types import CheckResult

if TYPE_CHECKING:
    from pathlib import Path


def _has_violation(result: CheckResult, detail_fragment: str = "") -> bool:
    return any(
        v.rule == "ADR-STATUS" and (not detail_fragment or detail_fragment in v.detail)
        for v in result.violations
    )


def _write_adr_project(
    root: Path,
    *,
    index_status: str = "✅",
    adr_status: str = "✅ Accepted",
) -> None:
    """Create a minimal ADR decisions directory with INDEX + one ADR file."""
    decisions = root / "docs" / "architecture" / "decisions"
    decisions.mkdir(parents=True)

    (decisions / "INDEX.md").write_text(
        "# ADR Index\n\n"
        "| Symbol | Meaning |\n|--------|---------|\n"
        "| ✅ | Accepted |\n| 🔄 | Proposed |\n"
        "| ⛔ | Superseded |\n| 🗄️ | Deprecated |\n\n"
        "| ID | Title | Status | Date | Affects |\n"
        "|----|-------|--------|------|---------|\n"
        f"| [ADR-001](ADR-001-test.md) | Test | {index_status} | 2026-01-01 | core/ |\n",
        encoding="utf-8",
    )

    (decisions / "ADR-001-test.md").write_text(
        "# ADR-001 — Test\n\n"
        f"> **Status:** {adr_status}\n"
        "> **Date:** 2026-01-01\n\n"
        "## Context\n\nTest.\n",
        encoding="utf-8",
    )


def _run_checker(root: Path) -> CheckResult:
    result = CheckResult()
    check_adr_status_consistency(result, root=root)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_adr_status_accepts_consistent_statuses(tmp_path: Path) -> None:
    """D8: INDEX and ADR file agree → no violations."""
    _write_adr_project(tmp_path, index_status="✅", adr_status="✅ Accepted")
    result = _run_checker(tmp_path)
    assert result.violations == []


def test_adr_status_blocks_non_canonical_symbol(tmp_path: Path) -> None:
    """D8: non-canonical symbol (🔧) in INDEX is flagged."""
    _write_adr_project(tmp_path, index_status="🔧", adr_status="✅ Accepted")
    result = _run_checker(tmp_path)
    assert _has_violation(result, "non-canonical")


def test_adr_status_blocks_mismatch_accepted_vs_proposed(tmp_path: Path) -> None:
    """D8: INDEX says ✅ but ADR file says 🔄 Proposed → mismatch flagged."""
    _write_adr_project(tmp_path, index_status="✅", adr_status="🔄 Proposed")
    result = _run_checker(tmp_path)
    assert _has_violation(result, "Status mismatch")


def test_adr_status_blocks_mismatch_proposed_vs_accepted(tmp_path: Path) -> None:
    """D8: INDEX says 🔄 but ADR file says ✅ Accepted → mismatch flagged."""
    _write_adr_project(tmp_path, index_status="🔄", adr_status="✅ Accepted")
    result = _run_checker(tmp_path)
    assert _has_violation(result, "Status mismatch")


def test_adr_status_real_repo_passes() -> None:
    """The real repo's ADR INDEX statuses match their ADR files.

    This is the CI-blocking assertion. ADR-045's `🔧` was fixed to `🔄`
    during Phase D; any future status drift will fail this test.
    """
    from scripts.architecture.helpers import ROOT

    result = _run_checker(ROOT)
    assert result.violations == [], "ADR status inconsistencies found: " + "; ".join(
        v.detail[:100] for v in result.violations[:5]
    )
