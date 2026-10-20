#!/usr/bin/env python3
"""Pin the review/report policy numbers stated in ``quality-gates.md``.

The thresholds used to be prose scattered across ``AGENTS.md``, the coordinator
agent and the quality-gates document, so the copies could drift apart (or be
silently loosened). The normative document now carries a machine-readable marker:

    <!-- review-policy: caps=3/250 report=2/80 -->

This gate pins those values in one place and enforces the wiring:

* the marker must exist, be well formed, and match ``EXPECTED_POLICY``;
* the normative document must keep the ``## Review & report policy`` heading and
  call the block normative;
* the pointing documents must reference that section and must not restate the
  numbers — neither ``≤N files``, nor ``N new [production] LOC``, nor a
  ``files/LOC`` pair. Detection is structural, so re-spacing or rewording a
  restatement does not slip through.

Pure text matching: no project imports, no I/O beyond reading the three files.

Usage:
    python scripts/check_review_policy_consistency.py [root]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

POLICY_DOC = Path("docs/development/quality-gates.md")
POINTING_DOCS: tuple[Path, ...] = (
    Path("AGENTS.md"),
    Path(".opencode/agents/NarrareDevCoordinator.md"),
)
EXPECTED_POLICY: dict[str, str] = {"caps": "3/250", "report": "2/80"}
HEADING = "## Review & report policy"
POINTER = "§Review & report policy"

_MARKER_RE = re.compile(
    r"<!--\s*review-policy:\s*caps\s*=\s*(?P<caps>\d+/\d+)\s+"
    r"report\s*=\s*(?P<report>\d+/\d+)\s*-->"
)
_MARKER_HINT_RE = re.compile(r"<!--\s*review-policy\b")
_CAPS_RE = re.compile(r"≤\s*\d+\s*files")
_LOC_RE = re.compile(r"\d+\s*new\s+(?:production\s+)?LOC")
_PAIR_RE = re.compile(r"\b\d{1,2}/\d{1,4}\b")


def parse_policy(text: str) -> dict[str, str]:
    """Return the marker values as ``{"caps": "A/B", "report": "C/D"}``.

    An absent or malformed marker yields an empty mapping; callers decide
    whether that is a violation.
    """
    match = _MARKER_RE.search(text)
    if match is None:
        return {}
    return {"caps": match.group("caps"), "report": match.group("report")}


def _restatements(text: str) -> list[str]:
    """Return the numeric restatements found in a pointing document."""
    found: list[str] = []
    for pattern in (_CAPS_RE, _LOC_RE, _PAIR_RE):
        found.extend(match.group(0) for match in pattern.finditer(text))
    return found


def find_policy_violations(root: Path) -> list[str]:
    """Return one human-readable line per policy consistency violation."""
    violations: list[str] = []

    policy_path = root / POLICY_DOC
    try:
        policy_text = policy_path.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"{POLICY_DOC}: cannot read the normative policy: {exc}")
        policy_text = ""

    policy = parse_policy(policy_text)
    if not policy:
        if _MARKER_HINT_RE.search(policy_text):
            violations.append(f"{POLICY_DOC}: review-policy marker is malformed")
        else:
            violations.append(f"{POLICY_DOC}: review-policy marker is missing")
    else:
        for key in ("caps", "report"):
            if policy[key] != EXPECTED_POLICY[key]:
                violations.append(
                    f"{POLICY_DOC}: marker {key}={policy[key]} does not match "
                    f"pinned {key}={EXPECTED_POLICY[key]}"
                )

    if HEADING not in policy_text:
        violations.append(f"{POLICY_DOC}: missing normative heading '{HEADING}'")
    if "normative" not in policy_text.lower():
        violations.append(f"{POLICY_DOC}: policy block is not marked normative")

    for rel in POINTING_DOCS:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"{rel}: cannot read the pointing document: {exc}")
            continue
        if POINTER not in text:
            violations.append(f"{rel}: must reference the policy section ('{POINTER}')")
        for restatement in _restatements(text):
            violations.append(
                f"{rel}: restates the review/report policy numerically ('{restatement}')"
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
        help="repository root to check (default: this script's parent repository)",
    )
    args = parser.parse_args(argv)

    violations = find_policy_violations(Path(args.root))
    if violations:
        print(f"❌ review/report policy: {len(violations)} violation(s)")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("✅ review/report policy marker, normative block and pointers agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
