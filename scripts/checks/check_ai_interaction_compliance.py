#!/usr/bin/env python3
"""§16 AI Interaction Standards Compliance Check (ADR-043).

Verifies 5 machine-checkable rules across TSX components and i18n files:
  Check 1 — Every TSX file importing SSE API values must also import useAIOperation
  Check 2 — No raw new AbortController() in feature code (classified allowed/violation)
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
    ExcludeRegistry,
    check_error_i18n_keys,
    check_no_hardcoded_errors,
    check_no_raw_abort_controller,
    check_no_use_connection_lost,
    check_use_ai_operation_usage,
    load_exclude_list,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Gate names matching the ``gate=`` field in ``.ai_interaction_exclude``.
GATE_CHECK_1 = "check_1_use_ai_operation"
GATE_CHECK_2 = "check_2_no_raw_abort"
GATE_CHECK_3 = "check_3_error_i18n_keys"
GATE_CHECK_4 = "check_4_no_hardcoded_errors"
GATE_CHECK_5 = "check_5_no_use_connection_lost"


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

    registry: ExcludeRegistry = load_exclude_list(args.exclude_file)

    report = ComplianceReport()

    # Report malformed exclude entries (global, not per-check).
    if registry.malformed:
        report.add_malformed(registry.malformed)

    # -- Check 1 ---------------------------------------------------------
    c1_p, c1_v = check_use_ai_operation_usage(registry)
    report.add("Check 1: useAIOperation in AI components", c1_p, c1_v)
    report.add_governed("Check 1", registry.get_entries_for_gate(GATE_CHECK_1))

    # -- Check 2 ---------------------------------------------------------
    c2_p, c2_v = check_no_raw_abort_controller(registry)
    report.add("Check 2: No raw AbortController (classified)", c2_p, c2_v)
    report.add_governed("Check 2", registry.get_entries_for_gate(GATE_CHECK_2))

    # -- Check 3 ---------------------------------------------------------
    c3_p, c3_v = check_error_i18n_keys(registry)
    report.add("Check 3: aiActions.error* keys in all locales", c3_p, c3_v)
    report.add_governed("Check 3", registry.get_entries_for_gate(GATE_CHECK_3))

    # -- Check 4 ---------------------------------------------------------
    c4_p, c4_v = check_no_hardcoded_errors(registry)
    report.add("Check 4: No hardcoded error.message in TSX", c4_p, c4_v)
    report.add_governed("Check 4", registry.get_entries_for_gate(GATE_CHECK_4))

    # -- Check 5 ---------------------------------------------------------
    c5_p, c5_v, c5_f = check_no_use_connection_lost(registry, fix=args.fix)
    report.add(
        "Check 5: No deprecated useConnectionLost (Phase 3)",
        c5_p,
        c5_v,
        c5_f if args.fix else None,
    )
    report.add_governed("Check 5", registry.get_entries_for_gate(GATE_CHECK_5))

    if args.json:
        print(report.format_json())
    else:
        print(report.format_text(compact=args.compact))

    return 0 if report.compliant else 1


if __name__ == "__main__":
    sys.exit(main())
