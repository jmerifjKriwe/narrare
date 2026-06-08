#!/usr/bin/env python3
"""§16 AI Interaction Standards Compliance Check (ADR-043).

Verifies 5 machine-checkable rules across TSX components and i18n files:
  Check 1 — Every TSX file importing SSE API values must also import useAIOperation
  Check 2 — No raw new AbortController() in Studio components
  Check 3 — All 7 aiActions.error* i18n keys exist in all 3 locales (de/en/fr)
  Check 4 — No hardcoded (err|error).message in Studio TSX files
  Check 5 — No deprecated useConnectionLost imports (Phase 3 completed)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _ai_interaction_checks import (
    ComplianceReport,
    check_error_i18n_keys,
    check_no_hardcoded_errors,
    check_no_raw_abort_controller,
    check_no_use_connection_lost,
    check_use_ai_operation_usage,
    load_exclude_list,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ADR-043 AI Interaction Standards Compliance Check",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Flag Check 5 violations for removal (no automatic code changes)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--exclude-file",
        type=Path,
        default=REPO_ROOT / "scripts" / "checks" / ".ai_interaction_exclude",
        help="Path to exclude list file (default: scripts/checks/.ai_interaction_exclude)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact output (omit passes, only show violations)",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    excludes = load_exclude_list(args.exclude_file)

    report = ComplianceReport()

    c1_p, c1_v = check_use_ai_operation_usage(excludes)
    report.add("Check 1: useAIOperation in AI components", c1_p, c1_v)

    c2_p, c2_v = check_no_raw_abort_controller(excludes)
    report.add("Check 2: No raw AbortController in Studio", c2_p, c2_v)

    c3_p, c3_v = check_error_i18n_keys(excludes)
    report.add("Check 3: aiActions.error* keys in all locales", c3_p, c3_v)

    c4_p, c4_v = check_no_hardcoded_errors(excludes)
    report.add("Check 4: No hardcoded error.message in TSX", c4_p, c4_v)

    c5_p, c5_v, c5_f = check_no_use_connection_lost(excludes, fix=args.fix)
    report.add(
        "Check 5: No deprecated useConnectionLost (Phase 3)",
        c5_p,
        c5_v,
        c5_f if args.fix else None,
    )

    if args.json:
        print(report.format_json())
    else:
        print(report.format_text(compact=args.compact))

    return 0 if report.compliant else 1


if __name__ == "__main__":
    sys.exit(main())
