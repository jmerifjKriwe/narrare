#!/usr/bin/env python3
"""Governance Health Checker — ADR-047 Phase 3+4.

Checks governance health by aggregating all drift checkers and the
review-finding coverage checker into a unified report.

Output status:
    PASS          — all checkers pass, all findings have lifecycle coverage.
    GOVERNED_DEBT — some checkers warn (registered exceptions), but no fails.
    FAIL          — at least one checker has critical/unregistered issues,
                    or some findings lack lifecycle coverage.

Exit codes (Phase 4 — BLOCKING):
    0 — PASS or GOVERNED_DEBT (governed debt is tracked, not a failure).
    1 — FAIL (unmatched findings or critical drift).

See: docs/architecture/decisions/ADR-047-governance-drift-automation.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from governance.governance_health import HealthStatus  # noqa: E402
from governance.ssot_aggregation import (  # noqa: E402
    aggregate_ssot_gate_health,
    format_aggregation_summary,
)


def main() -> int:
    """Run the governance health check and print a report.

    Returns 0 for PASS/GOVERNED_DEBT, 1 for FAIL (Phase 4 blocking).
    """
    report = aggregate_ssot_gate_health(ROOT)

    print("Governance Health Check — ADR-047 Phase 3+4 (blocking)")
    print("=" * 60)
    print(format_aggregation_summary(report))
    print("-" * 60)
    print(f"Total issues across checkers: {report.total_issues}")
    print(f"Overall status: {report.status.value}")
    print("-" * 60)

    if report.status == HealthStatus.FAIL:
        print("❌ Governance health FAIL — unmatched findings or critical drift.")
        print("   Fix the issues above or register them in the AUFG lifecycle.")
        return 1

    if report.status == HealthStatus.GOVERNED_DEBT:
        print("⚠️  Governance health GOVERNED_DEBT — warnings tracked, not blocking.")

    if report.status == HealthStatus.PASS:
        print("✅ Governance health PASS — all checkers clean.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
