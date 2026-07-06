#!/usr/bin/env python3
"""Context-file freshness gate.

Lookup/context files in ``.opencode/context/narrare-dev/`` declare an
``Updated:`` date in their YAML frontmatter. AI agents load files marked
``Priority: critical`` first and treat them as current — so a stale
``Updated:`` date silently degrades agent decisions. review-04 AUFG-04-14
found files where the frontmatter date lagged behind the file's actual
edits by weeks.

This gate enforces **Strategy 3** from review-04's causes section: a
context file must not declare an ``Updated:`` date that is implausibly
old. Two checks:

1. **Hard fail (blocking)**: ``Updated:`` is more than
   ``--max-age-days`` (default 60) in the past. Files this stale are
   almost certainly wrong; bump the date (and the content) before merge.
2. **Soft warn (non-blocking)**: ``Updated:`` is more than
   ``--warn-age-days`` (default 30) in the past. Surfaces drift early
   without blocking.

The gate intentionally compares against the *declared* date only, not the
filesystem mtime. Comparing against mtime is a trap: writing the file
always refreshes mtime to "now", which makes the check tautological.
The declared date is the author's claim about content currency — that is
the useful signal.

Exit codes:
    0: No file exceeds the hard age limit (warnings may still print).
    1: At least one file is older than ``--max-age-days``.

Usage:
    python scripts/check_context_freshness.py
    python scripts/check_context_freshness.py --json
    python scripts/check_context_freshness.py --max-age-days 45 --warn-age-days 21
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTEXT_DIR = ROOT / ".opencode" / "context" / "narrare-dev"

DEFAULT_MAX_AGE_DAYS = 60
DEFAULT_WARN_AGE_DAYS = 30

_UPDATED_RE = re.compile(r"Updated:\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?", re.IGNORECASE)


@dataclass(frozen=True)
class FreshnessFinding:
    """One staleness finding against a context file."""

    file: str
    declared: str
    age_days: int
    severity: str  # "critical" | "warning"

    def as_json(self) -> dict[str, str]:
        return asdict(self)


def _extract_updated(content: str) -> str | None:
    m = _UPDATED_RE.search(content)
    return m.group(1) if m else None


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.as_posix()


def find_findings(
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    *,
    today: dt.date | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    warn_age_days: int = DEFAULT_WARN_AGE_DAYS,
) -> list[FreshnessFinding]:
    """Return staleness findings, sorted by severity then file.

    A file with no ``Updated:`` field is skipped (freshness is opt-in via
    the frontmatter). A declared date in the future is treated as fresh.
    """
    if not context_dir.is_dir():
        return []
    today = today or dt.date.today()
    findings: list[FreshnessFinding] = []
    for path in sorted(context_dir.rglob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        declared_str = _extract_updated(content)
        if not declared_str:
            continue
        try:
            declared = dt.date.fromisoformat(declared_str)
        except ValueError:
            continue
        if declared > today:
            # Over-eager future bump: harmless, self-corrects. Not a finding.
            continue
        age_days = (today - declared).days
        if age_days > max_age_days:
            severity = "critical"
        elif age_days > warn_age_days:
            severity = "warning"
        else:
            continue
        findings.append(
            FreshnessFinding(
                file=_display(path),
                declared=declared_str,
                age_days=age_days,
                severity=severity,
            )
        )
    # Critical first, then by file path for stable output.
    findings.sort(key=lambda f: (0 if f.severity == "critical" else 1, f.file))
    return findings


def _print_human(findings: list[FreshnessFinding], *, max_age: int, warn_age: int) -> None:
    critical = [f for f in findings if f.severity == "critical"]
    warnings = [f for f in findings if f.severity == "warning"]
    if not findings:
        print(
            "✅ Context freshness check passed — all `Updated:` frontmatter "
            f"dates are within {warn_age} days."
        )
        return
    if critical:
        print(
            f"❌ {len(critical)} context file(s) declare an `Updated:` date "
            f"older than {max_age} days — these are almost certainly stale:\n"
        )
        for f in critical:
            print(f"  • {f.file}  (declared {f.declared}, {f.age_days} days old)")
    if warnings:
        if critical:
            print()
        print(
            f"⚠️  {len(warnings)} context file(s) declare an `Updated:` date "
            f"older than {warn_age} days (non-blocking, review recommended):\n"
        )
        for f in warnings:
            print(f"  • {f.file}  (declared {f.declared}, {f.age_days} days old)")
    print()
    print(
        "Fix: open each file and set `Updated: <today's date>` (YYYY-MM-DD) "
        "in the YAML frontmatter, after confirming the content is still current."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "Context-file freshness gate"
    )
    parser.add_argument("--json", action="store_true", help="JSON output for CI.")
    parser.add_argument(
        "--context-dir",
        type=Path,
        default=DEFAULT_CONTEXT_DIR,
        help="Override the context directory (mainly for tests).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Hard-fail threshold in days (default {DEFAULT_MAX_AGE_DAYS}).",
    )
    parser.add_argument(
        "--warn-age-days",
        type=int,
        default=DEFAULT_WARN_AGE_DAYS,
        help=f"Warning threshold in days (default {DEFAULT_WARN_AGE_DAYS}).",
    )
    args = parser.parse_args(argv)

    findings = find_findings(
        args.context_dir,
        max_age_days=args.max_age_days,
        warn_age_days=args.warn_age_days,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "passed": not any(f.severity == "critical" for f in findings),
                    "findings": [f.as_json() for f in findings],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        _print_human(
            findings,
            max_age=args.max_age_days,
            warn_age=args.warn_age_days,
        )

    return 1 if any(f.severity == "critical" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
