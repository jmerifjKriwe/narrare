#!/usr/bin/env python3
"""CURRENT_STATE volatility-policy checker.

``docs/_shared/CURRENT_STATE.md`` is a human handoff document, not a metrics
registry. This checker enforces ADR-076's policy (CURRENT_STATE.md volatility):

* reject volatile generated count claims;
* require links/commands for fresh authoritative facts.

It additionally enforces a "Last Updated" temporal invariant: no ``Date:``
entry in the "## Last Updated" section may be set to a future date ("dated
forward"), since a future date is a false fact — it reads as authoritative but
describes work that has not happened yet. This closes the gap left by a purely
hand-maintained date, which could otherwise be set forward unhindered.

Exit code 0: CURRENT_STATE follows the policy.
Exit code 1: policy violations found.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT_STATE_PATH = ROOT / "docs" / "_shared" / "CURRENT_STATE.md"

# "Last Updated" temporal invariant — a ``Date: YYYY-MM-DD`` entry in the
# "## Last Updated" section must never be set to a future date. A "dated
# forward" entry is a false fact: it reads as authoritative but describes work
# that has not happened yet. Purely hand-maintained dates can otherwise slip
# forward unhindered; this rejects that class of bug.
LAST_UPDATED_DATE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})\b")


ForbiddenPattern = tuple[str, re.Pattern[str]]
RequiredAuthority = tuple[str, tuple[str, ...]]


FORBIDDEN_VOLATILE_COUNT_PATTERNS: tuple[ForbiddenPattern, ...] = (
    (
        "Knowledge Graph node/edge/risk count",
        re.compile(
            r"\b(?:knowledge graph|KG)\b.*\b\d[\d,]*\s+(?:nodes?|edges?)\b"
            r"|\b\d[\d,]*\s+(?:nodes?|edges?)\b.*\b(?:knowledge graph|KG)\b"
            r"|\b(?:risk score|risk)\s*[:=]\s*(?:high|medium|low)?\s*\(?\d+(?:\.\d+)?\)?",
            re.IGNORECASE,
        ),
    ),
    (
        "Backend/frontend test-file count",
        re.compile(
            r"\b(?:backend|frontend)\s+tests?\b.*\b\d[\d,]*\s+test\s+files?\b"
            r"|\b\d[\d,]*\s+test\s+files?\b.*\b(?:unit\s*\+\s*integration|vitest|backend|frontend)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ADR/feature/question/exception inventory count",
        re.compile(
            r"\bADRs?\s*:\s*\d+\b"
            r"|\bADR-\d+\s+through\s+ADR-\d+\b"
            r"|\b\d+\s+individual\s+files\b"
            r"|\b\d+\s+registered\s+entries\b"
            r"|\b\d+\s+in\s+(?:ai-gate-baseline\.json|CONSTRAINTS\.md)\b"
            r"|\b\d+\s+active\s*\(Q-"
            r"|\bOpen questions\b.*\b\d+\s+resolved\b"
            r"|\b\d+\s+resolved\b.*\b(?:questions?|Q-)",
            re.IGNORECASE,
        ),
    ),
    (
        "Adoption-debt/health-score count",
        re.compile(
            r"\b\d+\s+ratcheted\s+baseline\s+items\b"
            r"|\badoption debt\b.*\b\d+\b"
            r"|\bhealth\s+(?:score|status)\b.*\b\d+(?:\.\d+)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Router/agent/module/migration inventory count",
        re.compile(
            # Alt 1: explicit "(current )?<kind> inventory … N" claim, anywhere.
            r"\b(?:current\s+)?(?:agent|router|module|migration)\s+inventory\b.*\b\d+\b"
            # Alt 2: bare "N agents/routers/modules/migrations" only counts as a
            # volatile inventory when it opens a list entry (line start, optional
            # "- "/"* " bullet), e.g. "- 7 agents: beta_reader". In running prose
            # ("…1 agent call…", "3 routers configured") it is narrative, not an
            # inventory — matching it produced false positives (CI run #465).
            # Lookbehind keeps rejecting hyphen-preceded tokens ("ADR-054 migration").
            r"|^\s*(?:[-*]\s*)?(?<![-\w])\b\d+\s+(?:agents?|routers?|modules?|migrations?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Architecture rule count or reproduced RULE text",
        re.compile(
            r"\bArchitecture rules?:\s*\d+\s+rules?\b"
            r"|^\s*(?:[-*]\s*)?RULE-\d+[a-z]?\s*[·:-]\s+(?!see\b).{20,}",
            re.IGNORECASE,
        ),
    ),
)

REQUIRED_AUTHORITY_REFERENCES: tuple[RequiredAuthority, ...] = (
    ("Architecture rules/exceptions", ("docs/_shared/CONSTRAINTS.md",)),
    ("ADR index", ("docs/architecture/decisions/INDEX.md",)),
    ("Feature specs index", ("docs/features/INDEX.md",)),
    ("Open questions index", ("docs/architecture/questions/INDEX.md",)),
    ("Adoption gate command", ("just check-adoption",)),
    ("System health command", ("just check-health",)),
    (
        "Knowledge Graph stats command",
        (
            "code-review-graph_list_graph_stats_tool",
            "code-review-graph stats tool",
            "list_graph_stats_tool",
        ),
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_forbidden_volatile_counts(cs_text: str) -> list[tuple[int, str, str]]:
    """Return ``(line_number, label, line)`` for forbidden volatile count claims."""
    findings: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(cs_text.splitlines(), start=1):
        for label, pattern in FORBIDDEN_VOLATILE_COUNT_PATTERNS:
            if pattern.search(line):
                findings.append((line_number, label, line.strip()))
                break
    return findings


def find_missing_authority_references(cs_text: str) -> list[tuple[str, tuple[str, ...]]]:
    """Return required authority families absent from CURRENT_STATE.md."""
    return [
        (label, accepted)
        for label, accepted in REQUIRED_AUTHORITY_REFERENCES
        if not any(token in cs_text for token in accepted)
    ]


def find_future_dated_entries(cs_text: str, today: date) -> list[tuple[int, str]]:
    """Return ``(line_number, date_str)`` for ``Date: YYYY-MM-DD`` entries set
    after ``today`` (a "dated forward" false fact).

    Only well-formed, calendar-valid ISO dates are evaluated; malformed dates
    are skipped (out of scope for this temporal invariant).
    """
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(cs_text.splitlines(), start=1):
        match = LAST_UPDATED_DATE_RE.match(line)
        if match is None:
            continue
        try:
            entry_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if entry_date > today:
            findings.append((line_number, match.group(1)))
    return findings


def main() -> int:
    if not CURRENT_STATE_PATH.exists():
        print(f"❌ CURRENT_STATE.md not found at {CURRENT_STATE_PATH}")
        return 1

    cs_text = _read(CURRENT_STATE_PATH)
    forbidden_counts = find_forbidden_volatile_counts(cs_text)
    missing_authorities = find_missing_authority_references(cs_text)
    today = date.today()
    future_dated_entries = find_future_dated_entries(cs_text, today)

    print("📋 SSOT Check — CURRENT_STATE.md Volatility Policy")
    print("=" * 55)

    if forbidden_counts:
        print("❌ Forbidden volatile count claims:")
        for line_number, label, line in forbidden_counts:
            print(f"  - line {line_number}: {label}: {line}")
    else:
        print("✅ No forbidden volatile count claims found.")

    if missing_authorities:
        print("❌ Missing required authority references/commands:")
        for label, accepted in missing_authorities:
            options = " or ".join(f"`{token}`" for token in accepted)
            print(f"  - {label}: add {options}")
    else:
        print("✅ Required authority references/commands are present.")

    if future_dated_entries:
        print("❌ 'Last Updated' entries dated after today (dated forward):")
        for line_number, date_str in future_dated_entries:
            print(f"  - line {line_number}: Date: {date_str} (today is {today.isoformat()})")
    else:
        print("✅ No 'Last Updated' entry is dated in the future.")

    print("=" * 55)

    if forbidden_counts or missing_authorities or future_dated_entries:
        print(
            "⚠️  CURRENT_STATE.md violates the volatility policy — "
            "replace counts with authoritative sources/commands and/or "
            "correct any future-dated 'Last Updated' entries."
        )
        return 1

    print("✅ CURRENT_STATE.md follows the volatility policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
