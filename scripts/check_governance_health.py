#!/usr/bin/env python3
"""Governance Health Checker — ADR-047 Phase 2.

Checks that every review finding has a matching AUFG / accepted-risk /
accepted-enhancement lifecycle entry in the AUFG registry.

Output status:
    PASS          — all findings have lifecycle coverage.
    GOVERNED_DEBT — all covered, some via accepted risk/enhancement.
    FAIL          — some findings lack lifecycle coverage.

Phase 2 is **warning-only**: the script always exits 0 so it does not
block CI. Future phases will ratchet to blocking after a baseline cycle.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from governance.aufg_registry import load_registry  # noqa: E402
from governance.governance_health import (  # noqa: E402
    CoverageStatus,
    assess_health,
)
from governance.review_findings import load_findings  # noqa: E402

REGISTRY_PATH = ROOT / "docs" / "architecture" / "governance" / "aufg-registry.md"
REVIEW_DIR = ROOT / "_audit" / "results" / "technical-review"


def main() -> int:
    """Run the governance health check and print a report."""
    registry = load_registry(REGISTRY_PATH)
    findings = load_findings(REVIEW_DIR)
    report = assess_health(findings, registry)

    print("Governance Health Check — ADR-047 Phase 2 (warning-only)")
    print("=" * 60)
    print(f"Registry entries: {len(registry.entries)}")
    print(f"Candidate findings: {report.total}")
    print(f"  Covered:        {report.covered}")
    print(f"  Governed debt:  {report.governed_debt}")
    print(f"  Unmatched:      {report.unmatched}")
    print(f"Overall status:  {report.status.value}")
    print("-" * 60)

    unmatched = [c for c in report.coverages if c.coverage == CoverageStatus.UNMATCHED]
    if unmatched:
        print("Unmatched findings (need AUFG/AR/AE lifecycle reference):")
        for cov in unmatched:
            text_preview = cov.finding.text[:80]
            if len(cov.finding.text) > 80:
                text_preview += "..."
            print(f"  - {cov.finding.source_file}:{cov.finding.line_number}: {text_preview}")
        print("-" * 60)

    if report.governed_debt > 0:
        print("Governed debt (accepted risk/enhancement — tracked):")
        for cov in report.coverages:
            if cov.coverage == CoverageStatus.GOVERNED_DEBT:
                print(
                    f"  - {cov.finding.source_file}:{cov.finding.line_number}: "
                    f"matched {', '.join(cov.matched_ids)}"
                )
        print("-" * 60)

    print("Phase 2 is warning-only — no CI blocking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
