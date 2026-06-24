"""Tests for check_governance_health.py blocking behavior (ADR-047 Phase 4).

Tests that the checker exits 0 for PASS/GOVERNED_DEBT and exits 1 for FAIL.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.governance_health import HealthStatus  # noqa: E402
from governance.ssot_aggregation import (  # noqa: E402
    CheckerResult,
    SsotAggregationReport,
)


def _make_report(status: HealthStatus) -> SsotAggregationReport:
    return SsotAggregationReport(
        status=status,
        checkers=(
            CheckerResult(
                checker_name="test_checker",
                status=status,
                issue_count=0 if status == HealthStatus.PASS else 1,
                detail="test",
            ),
        ),
        total_issues=0 if status == HealthStatus.PASS else 1,
    )


def test_check_governance_health_exit_0_on_baseline() -> None:
    """check_governance_health.py exits 0 on the real baseline (GOVERNED_DEBT)."""
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts" / "check_governance_health.py")],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
        env=env,
    )
    # The real baseline is GOVERNED_DEBT, so exit code should be 0.
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\n{result.stdout}\n{result.stderr}"
    )


def test_check_governance_health_main_returns_0_on_governed_debt() -> None:
    """main() returns 0 when aggregation reports GOVERNED_DEBT."""
    import check_governance_health as cg

    with patch(
        "check_governance_health.aggregate_ssot_gate_health",
        return_value=_make_report(HealthStatus.GOVERNED_DEBT),
    ):
        exit_code = cg.main()
    assert exit_code == 0


def test_check_governance_health_main_returns_1_on_fail() -> None:
    """main() returns 1 when aggregation reports FAIL."""
    import check_governance_health as cg

    with patch(
        "check_governance_health.aggregate_ssot_gate_health",
        return_value=_make_report(HealthStatus.FAIL),
    ):
        exit_code = cg.main()
    assert exit_code == 1


def test_check_governance_health_main_returns_0_on_pass() -> None:
    """main() returns 0 when aggregation reports PASS."""
    import check_governance_health as cg

    with patch(
        "check_governance_health.aggregate_ssot_gate_health",
        return_value=_make_report(HealthStatus.PASS),
    ):
        exit_code = cg.main()
    assert exit_code == 0
