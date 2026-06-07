#!/usr/bin/env python3
"""Quality metrics CLI — join eval results with adoption evidence.

Joins Pydantic Eval results, adoption reports, audit reports, and
invocation evidence to produce per-mode quality metrics.

Usage::

    check_quality_metrics.py [--quality] [--evidence-dir PATH]
                             [--results-dir PATH] [--json]
                             [--adoption-report PATH] [--audit-report PATH]

Opt-in: requires ``--quality`` flag or ``NARRARE_QUALITY_METRICS=1`` env var.

Returns 0 (quality metrics are informational and never fail CI).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

# Ensure the scripts directory is on sys.path for package imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from adoption.audit_report import AuditReport  # noqa: E402
from adoption.scorer import AdoptionReport  # noqa: E402
from eval_drift.parser import (  # noqa: E402
    DEFAULT_RESULTS_DIR,
    EvalResultFile,
    find_result_files,
    parse_pydantic_eval_report,
)
from quality.joiner import join_quality_metrics, parse_evidence_lines  # noqa: E402
from quality.quality_report import QualityReport, build_quality_report  # noqa: E402

# ── Default paths ─────────────────────────────────────────────────

DEFAULT_EVIDENCE_DIR = _SCRIPTS_DIR.parent / ".evidence"
DEFAULT_ADOPTION_REPORT = _SCRIPTS_DIR / "adoption_report.json"
DEFAULT_AUDIT_REPORT = _SCRIPTS_DIR / "audit_report.json"


# ── Argument parsing ──────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Narrare Quality Metrics — eval + evidence + adoption correlation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/check_quality_metrics.py --quality\n"
            "  python scripts/check_quality_metrics.py --quality --json\n"
            "  python scripts/check_quality_metrics.py --quality --evidence-dir .evidence\n"
        ),
    )
    parser.add_argument(
        "--quality",
        action="store_true",
        dest="quality_flag",
        help="Explicitly enable quality metrics generation.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=DEFAULT_EVIDENCE_DIR,
        help=f"Directory containing .evidence/invocations.jsonl (default: {DEFAULT_EVIDENCE_DIR})",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=f"Directory containing Pydantic Evals results (default: {DEFAULT_RESULTS_DIR})",
    )
    parser.add_argument(
        "--adoption-report",
        type=Path,
        default=DEFAULT_ADOPTION_REPORT,
        help=f"Path to adoption report JSON (default: {DEFAULT_ADOPTION_REPORT})",
    )
    parser.add_argument(
        "--audit-report",
        type=Path,
        default=DEFAULT_AUDIT_REPORT,
        help=f"Path to audit report JSON (default: {DEFAULT_AUDIT_REPORT})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the quality report as JSON (for CI consumption).",
    )
    return parser.parse_args(argv)


# ── Report loaders ────────────────────────────────────────────────


def _load_adoption_report(path: Path) -> AdoptionReport | None:
    """Load an :class:`AdoptionReport` from a JSON file.

    Returns ``None`` if the file does not exist or cannot be parsed.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        # AdoptionReport is reconstructed from the JSON dict.
        return AdoptionReport(**cast("dict[str, Any]", data))
    except json.JSONDecodeError, OSError, TypeError:
        return None


def _load_audit_report(path: Path) -> AuditReport | None:
    """Load an :class:`AuditReport` from a JSON file.

    Returns ``None`` if the file does not exist or cannot be parsed.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return AuditReport(**cast("dict[str, Any]", data))
    except json.JSONDecodeError, OSError, TypeError:
        return None


def _load_eval_results(results_dir: Path) -> list[EvalResultFile]:
    """Load all eval result files from *results_dir*."""
    result_paths = find_result_files(results_dir)
    eval_results: list[EvalResultFile] = []
    for fp in result_paths:
        result = parse_pydantic_eval_report(fp)
        if result.test_cases:
            eval_results.append(result)
    return eval_results


# ── Main ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Generate the quality report.

    Returns 0 — quality metrics are informational and never fail CI.
    """
    args = parse_args(argv)

    # -- Opt-in check --
    quality_enabled = args.quality_flag or os.environ.get("NARRARE_QUALITY_METRICS") == "1"
    if not quality_enabled:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "message": (
                            "Quality metrics disabled. "
                            "Use --quality or set NARRARE_QUALITY_METRICS=1."
                        ),
                        "enabled": False,
                    },
                    indent=2,
                )
            )
        else:
            print(
                "Quality metrics disabled. "
                "Use --quality or set NARRARE_QUALITY_METRICS=1 to enable."
            )
        return 0

    # -- Load adoption report --
    adoption = _load_adoption_report(args.adoption_report)
    if adoption is None:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "message": "No adoption report found — cannot build quality metrics.",
                        "enabled": True,
                        "adoption_found": False,
                    },
                    indent=2,
                )
            )
        else:
            print(f"No adoption report found at {args.adoption_report}")
            print("Run check_adoption.py first to generate one.")
        return 0

    # -- Load audit report --
    audit = _load_audit_report(args.audit_report)

    # -- Load eval results --
    eval_results = _load_eval_results(args.results_dir)

    # -- Load evidence records --
    evidence_path = args.evidence_dir / "invocations.jsonl"
    evidence_records = parse_evidence_lines(evidence_path)

    # -- Join all data --
    metrics = join_quality_metrics(adoption, audit, eval_results, evidence_records)

    # -- Build report --
    report = build_quality_report(metrics)

    # -- Output --
    if args.json_output:
        print(_report_to_json(report))
    else:
        _print_human_report(report)

    return 0


# ── Output formatting ─────────────────────────────────────────────


def _report_to_json(report: QualityReport) -> str:
    """Serialize a :class:`QualityReport` to indented JSON."""
    data = asdict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _print_human_report(report: QualityReport) -> None:
    """Print a human-readable summary of the quality report."""
    print("=" * 60)
    print("  Quality Metrics Report")
    print(f"  Generated: {report.generated_at}")
    print("=" * 60)
    print()

    if not report.metrics:
        print("  No modes found in the adoption report.")
        print()
        return

    print(f"  Modes with evals:     {report.modes_with_evals}")
    print(f"  Modes without evals:  {report.modes_without_evals}")
    print(f"  Quality-adoption gaps: {report.gap_count}")
    print()

    if report.gap_count > 0:
        print("  Gaps detected:")
        for m in report.metrics:
            if m.quality_adoption_gap:
                eval_str = f"{m.eval_score:.2f}" if m.eval_score is not None else "N/A"
                print(
                    f"    ⚠ {m.category}/{m.mode}: "
                    f"eval={eval_str}, adoption={m.static_score:.2f}, "
                    f"state={m.adoption_state}"
                )
        print()

    print("  Per-mode breakdown:")
    print(f"  {'Category/Mode':<35} {'Eval':<8} {'Adopt':<8} {'State':<20} {'Gap':<5}")
    print(f"  {'─' * 35} {'─' * 8} {'─' * 8} {'─' * 20} {'─' * 5}")
    for m in report.metrics:
        eval_str = f"{m.eval_score:.2f}" if m.eval_score is not None else "─"
        gap_str = "⚠" if m.quality_adoption_gap else "✓"
        label = f"{m.category}/{m.mode}"
        print(
            f"  {label:<35} {eval_str:<8} {m.static_score:<8.2f} "
            f"{m.adoption_state:<20} {gap_str:<5}"
        )
    print()


if __name__ == "__main__":
    sys.exit(main())
