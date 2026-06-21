#!/usr/bin/env python3
"""§16 AI Interaction Standards Compliance Check (ADR-043).

Verifies 12 machine-checkable rules across TSX components and i18n files:
  Check 1  — Every TSX file importing SSE API values must also import useAIOperation
  Check 2  — No raw new AbortController() in feature code (classified allowed/violation)
  Check 3  — All 7 aiActions.error* i18n keys exist in all 3 locales (de/en/fr)
  Check 4  — No hardcoded (err|error).message in Studio TSX files
  Check 5  — No deprecated useConnectionLost imports (Phase 3 completed)
  Check 6  — No deprecated §16.8 AI-action aliases in TS/TSX (CR-AUFG-07-12)
  Check 7  — useAIOperation execute callbacks must propagate signal (CR-AUFG-07-11)
  Check 8  — Exclude entries must be fresh and AUFG-linked (§7 stale-exclude policy)
  Check 9  — CR-AUFG IDs in audit must exist in registry (§8 lifecycle sync)
  Check 10 — Operation inventory must have required §4 fields and AUFG links
  Check 11 — Resolved AUFG entries need implementation + enforcement evidence
  Check 12 — No visible i18n fallback strings in KB/editor components (CR-AUFG-07-14)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _ai_interaction_checks import (
    ComplianceReport,
    ExcludeRegistry,
    check_deprecated_aliases,
    check_error_i18n_keys,
    check_lifecycle_sync,
    check_no_hardcoded_errors,
    check_no_raw_abort_controller,
    check_no_use_connection_lost,
    check_operation_inventory,
    check_resolution_evidence,
    check_signal_propagation,
    check_stale_exclude,
    check_use_ai_operation_usage,
    check_visible_i18n_fallbacks,
    load_exclude_list,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Gate names matching the ``gate=`` field in ``.ai_interaction_exclude``.
GATE_CHECK_1 = "check_1_use_ai_operation"
GATE_CHECK_2 = "check_2_no_raw_abort"
GATE_CHECK_3 = "check_3_error_i18n_keys"
GATE_CHECK_4 = "check_4_no_hardcoded_errors"
GATE_CHECK_5 = "check_5_no_use_connection_lost"
GATE_CHECK_6 = "check_6_deprecated_alias"
GATE_CHECK_7 = "check_7_signal_propagation"
GATE_CHECK_8 = "check_8_stale_exclude"
GATE_CHECK_12 = "check_12_visible_i18n_fallbacks"


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

    # -- Check 6 ---------------------------------------------------------
    c6_p, c6_v = check_deprecated_aliases(registry)
    report.add("Check 6: No deprecated §16.8 AI-action aliases", c6_p, c6_v)
    report.add_governed("Check 6", registry.get_entries_for_gate(GATE_CHECK_6))

    # -- Check 7 ---------------------------------------------------------
    c7_p, c7_v = check_signal_propagation(registry)
    report.add("Check 7: useAIOperation execute propagates signal", c7_p, c7_v)
    report.add_governed("Check 7", registry.get_entries_for_gate(GATE_CHECK_7))

    # -- Check 8 ---------------------------------------------------------
    c8_p, c8_v = check_stale_exclude(registry)
    report.add("Check 8: Exclude entries fresh and AUFG-linked", c8_p, c8_v)
    report.add_governed("Check 8", registry.get_entries_for_gate(GATE_CHECK_8))

    # -- Check 9 ---------------------------------------------------------
    c9_p, c9_v = check_lifecycle_sync()
    report.add("Check 9: CR-AUFG IDs in audit exist in registry", c9_p, c9_v)

    # -- Check 10 --------------------------------------------------------
    c10_p, c10_v = check_operation_inventory()
    report.add("Check 10: Operation inventory has required §4 fields", c10_p, c10_v)

    # -- Check 11 --------------------------------------------------------
    c11_p, c11_v = check_resolution_evidence()
    report.add("Check 11: Resolved AUFG entries have evidence", c11_p, c11_v)

    # -- Check 12 --------------------------------------------------------
    c12_p, c12_v = check_visible_i18n_fallbacks()
    report.add("Check 12: No visible i18n fallback strings", c12_p, c12_v)

    if args.json:
        print(report.format_json())
    else:
        print(report.format_text(compact=args.compact))

    return 0 if report.compliant else 1


if __name__ == "__main__":
    sys.exit(main())
