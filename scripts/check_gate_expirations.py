#!/usr/bin/env python3
"""
Narrare Gate Exception Expiry Checker.

Reads scripts/gate-exceptions.json and validates that all active exceptions
are within their valid period. Warns on approaching review dates and fails
on expired exceptions.

Exit codes:
  0: All exceptions within valid period.
  1: At least one exception has expired.
  2: At least one exception expired more than 30 days ago (critical).

Usage:
  python scripts/check_gate_expirations.py              # human-readable
  python scripts/check_gate_expirations.py --json       # JSON for CI

See: ADR-098 (docs/architecture/decisions/) — the gate-exception registry
authority is scripts/gate-exceptions.json, anchored by ADR-098.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCEPTIONS_PATH = REPO_ROOT / "scripts" / "gate-exceptions.json"
CRITICAL_EXPIRY_DAYS = 30


class ExceptionStatus(StrEnum):
    """Status of an exception relative to its date boundaries."""

    VALID = "valid"
    REVIEW_DUE = "review_due"
    EXPIRED = "expired"
    CRITICALLY_EXPIRED = "critically_expired"
    INACTIVE = "inactive"


# ── Data structures ────────────────────────────────────────────


@dataclass
class ExceptionEntry:
    """Parsed gate exception entry from the JSON registry."""

    id: str
    gate: str
    description: str
    set_date: date
    expires: date
    review_after: date
    status: str
    approved_by: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExceptionEntry:
        """Create an ExceptionEntry from a raw JSON dict."""
        return cls(
            id=data["id"],
            gate=data["gate"],
            description=data["description"],
            set_date=date.fromisoformat(data["set_date"]),
            expires=date.fromisoformat(data["expires"]),
            review_after=date.fromisoformat(data["review_after"]),
            status=data["status"],
            approved_by=data["approved_by"],
        )


@dataclass
class ExceptionAssessment:
    """Assessment result for a single exception entry."""

    entry: ExceptionEntry
    status: ExceptionStatus
    message: str

    @property
    def is_ok(self) -> bool:
        """True if this exception does not cause a CI failure."""
        return self.status in (
            ExceptionStatus.VALID,
            ExceptionStatus.REVIEW_DUE,
            ExceptionStatus.INACTIVE,
        )


@dataclass
class ExpiryReport:
    """Aggregated report of all exception assessments."""

    assessments: list[ExceptionAssessment] = field(default_factory=list[ExceptionAssessment])

    @property
    def has_expired(self) -> bool:
        """True if any active exception has expired."""
        return any(
            a.status == ExceptionStatus.EXPIRED
            for a in self.assessments
            if a.entry.status == "active"
        )

    @property
    def has_critical(self) -> bool:
        """True if any active exception has been expired for more than 30 days."""
        return any(
            a.status == ExceptionStatus.CRITICALLY_EXPIRED
            for a in self.assessments
            if a.entry.status == "active"
        )

    @property
    def active_count(self) -> int:
        return sum(1 for a in self.assessments if a.entry.status == "active")

    @property
    def exit_code(self) -> int:
        """Determine the exit code from the report."""
        if self.has_critical:
            return 2
        if self.has_expired:
            return 1
        return 0


# ── Core logic ─────────────────────────────────────────────────


def load_exceptions(path: Path = EXCEPTIONS_PATH) -> list[ExceptionEntry]:
    """Load and parse gate exceptions from the JSON registry.

    Raises SystemExit if the file cannot be read or parsed.
    """
    if not path.exists():
        print(f"ERROR: Exceptions file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    entries: list[ExceptionEntry] = []
    for raw in data.get("exceptions", []):
        try:
            entries.append(ExceptionEntry.from_dict(raw))
        except (KeyError, ValueError, TypeError) as exc:
            print(f"ERROR: Invalid exception entry: {exc}", file=sys.stderr)
            sys.exit(1)

    return entries


def assess_exception(entry: ExceptionEntry, today: date) -> ExceptionAssessment:
    """Assess the status of a single exception entry against today's date."""
    if entry.status != "active":
        return ExceptionAssessment(
            entry=entry,
            status=ExceptionStatus.INACTIVE,
            message=f"Inactive exception: {entry.id}",
        )

    if today > entry.expires:
        days_over = (today - entry.expires).days
        if days_over > CRITICAL_EXPIRY_DAYS:
            return ExceptionAssessment(
                entry=entry,
                status=ExceptionStatus.CRITICALLY_EXPIRED,
                message=(
                    f"CRITICAL: Exception '{entry.id}' (gate {entry.gate}) expired "
                    f"{days_over} days ago (>{CRITICAL_EXPIRY_DAYS}d). Must be renewed or resolved."
                ),
            )
        return ExceptionAssessment(
            entry=entry,
            status=ExceptionStatus.EXPIRED,
            message=(
                f"ERROR: Exception '{entry.id}' (gate {entry.gate}) expired "
                f"{days_over} day(s) ago on {entry.expires}. Must be renewed or resolved."
            ),
        )

    if today > entry.review_after:
        return ExceptionAssessment(
            entry=entry,
            status=ExceptionStatus.REVIEW_DUE,
            message=(
                f"WARNING: Exception '{entry.id}' (gate {entry.gate}) review due. "
                f"Review after {entry.review_after}, expires {entry.expires}."
            ),
        )

    return ExceptionAssessment(
        entry=entry,
        status=ExceptionStatus.VALID,
        message=(
            f"OK: Exception '{entry.id}' (gate {entry.gate}) is valid. "
            f"Review after {entry.review_after}, expires {entry.expires}."
        ),
    )


def run_assessments(today: date | None = None) -> ExpiryReport:
    """Load exceptions and assess them all.

    Args:
        today: Override today's date for testing. Defaults to date.today().
    """
    effective_today = today or date.today()
    entries = load_exceptions()

    report = ExpiryReport()
    for entry in entries:
        assessment = assess_exception(entry, effective_today)
        report.assessments.append(assessment)

    return report


# ── Output formatting ──────────────────────────────────────────


def _status_icon(status: ExceptionStatus) -> str:
    """Return a display icon for an exception status."""
    icons: dict[ExceptionStatus, str] = {
        ExceptionStatus.VALID: "✅",
        ExceptionStatus.REVIEW_DUE: "⚠️ ",
        ExceptionStatus.EXPIRED: "❌",
        ExceptionStatus.CRITICALLY_EXPIRED: "🔴",
        ExceptionStatus.INACTIVE: "⏸️ ",
    }
    return icons.get(status, "❓")


def print_human_report(report: ExpiryReport) -> None:
    """Print a human-readable expiry report to stdout."""
    print("=" * 70)
    print("  NARRARE GATE EXCEPTION EXPIRY CHECK")
    print("=" * 70)
    print()

    if not report.assessments:
        print("No exceptions registered.")
        return

    # Summary table
    print(f"{'ID':<25} {'Gate':<6} {'Status':<10} {'Review After':<14} {'Expires':<12}")
    print("-" * 70)
    for assessment in report.assessments:
        entry = assessment.entry
        active_status = assessment.status.value if entry.status == "active" else "inactive"
        print(
            f"{entry.id:<25} {entry.gate:<6} {active_status:<10} "
            f"{entry.review_after.isoformat():<14} {entry.expires.isoformat():<12}"
        )

    print()
    print("Details:")
    print("-" * 70)
    for assessment in report.assessments:
        icon = _status_icon(assessment.status)
        print(f"  {icon} {assessment.message}")

    print()
    print("=" * 70)
    if report.has_critical:
        print("RESULT: CRITICAL — exception(s) expired >30d. Exit code 2.")
    elif report.has_expired:
        print("RESULT: FAILED — exception(s) expired. Must renew or resolve. Exit code 1.")
    elif any(
        a.status == ExceptionStatus.REVIEW_DUE
        for a in report.assessments
        if a.entry.status == "active"
    ):
        print("RESULT: PASSED with warnings — review-due exception(s). Exit code 0.")
    else:
        print("RESULT: PASSED — all exceptions within valid period. Exit code 0.")


def print_json_report(report: ExpiryReport) -> None:
    """Print a JSON-formatted report for CI pipeline consumption."""
    output = {
        "exit_code": report.exit_code,
        "has_expired": report.has_expired,
        "has_critical": report.has_critical,
        "active_count": report.active_count,
        "assessments": [
            {
                "id": a.entry.id,
                "gate": a.entry.gate,
                "status": a.status.value,
                "message": a.message,
                "expires": a.entry.expires.isoformat(),
                "review_after": a.entry.review_after.isoformat(),
            }
            for a in report.assessments
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ── CLI entry point ────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Narrare Gate Exception Expiry Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  All exceptions within valid period\n"
            "  1  At least one exception has expired\n"
            "  2  At least one exception expired >30 days (critical)\n"
            "\n"
            "Examples:\n"
            "  python scripts/check_gate_expirations.py\n"
            "  python scripts/check_gate_expirations.py --json\n"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI consumption)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run all exception expiry checks and return the exit code."""
    args = parse_args(argv)
    report = run_assessments()

    if args.json:
        print_json_report(report)
    else:
        print_human_report(report)

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
