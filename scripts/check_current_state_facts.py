#!/usr/bin/env python3
"""SSOT Fact Checker — validates CURRENT_STATE.md claims against reality.

Reads CURRENT_STATE.md, extracts numeric claims, and compares them against
actual counts from the codebase. Reports discrepancies clearly.

Exit code 0: all claims consistent.
Exit code 1: discrepancies found (warn-only — does NOT block CI).

Usage:
    just check-ssot
    uv run python scripts/check_current_state_facts.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT_STATE_PATH = ROOT / "docs" / "_shared" / "CURRENT_STATE.md"
CONSTRAINTS_PATH = ROOT / "docs" / "_shared" / "CONSTRAINTS.md"
ADR_INDEX_PATH = ROOT / "docs" / "architecture" / "decisions" / "INDEX.md"
FEATURES_DIR = ROOT / "docs" / "features"
FEATURE_INDEX_PATH = FEATURES_DIR / "INDEX.md"
BASELINE_PATH = ROOT / "scripts" / "architecture" / "ai-gate-baseline.json"
QUESTIONS_INDEX_PATH = ROOT / "docs" / "architecture" / "questions" / "INDEX.md"


# ── Claim extraction ─────────────────────────────────────────────


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_first_number(text: str, pattern: str) -> int | None:
    """Extract the first integer from lines matching *pattern*."""
    for line in text.splitlines():
        if re.search(pattern, line):
            nums = re.findall(r"\b(\d+)\b", line)
            # Return the first number that looks like a count (>1, reasonable)
            for n in nums:
                val = int(n)
                if val > 1:
                    return val
    return None


def extract_claims(cs_text: str) -> dict[str, int | None]:
    """Extract numeric claims from CURRENT_STATE.md."""
    claims: dict[str, int | None] = {}

    # Rule count: "Architecture rules: 23 rules"
    claims["rule_count"] = _extract_first_number(
        cs_text,
        r"Architecture rules:\s*\d+\s+rule",
    )

    # ADR count: "ADRs: 43" or "ADR-001 through ADR-043"
    claims["adr_count"] = _extract_first_number(cs_text, r"ADRs:\s*\d+")

    # Feature spec files: "87 individual files"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+individual\s+files", line)
        if m:
            claims["feature_spec_files"] = int(m.group(1))
            break
    else:
        claims["feature_spec_files"] = None

    # Registered feature entries: "77 registered entries"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+registered\s+entries", line)
        if m:
            claims["feature_registered"] = int(m.group(1))
            break
    else:
        claims["feature_registered"] = None

    # Exceptions in baseline: "14 in ai-gate-baseline.json"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+in\s+ai-gate-baseline\.json", line)
        if m:
            claims["exceptions_baseline"] = int(m.group(1))
            break
    else:
        claims["exceptions_baseline"] = None

    # Exceptions in CONSTRAINTS: "10 in CONSTRAINTS.md"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+in\s+CONSTRAINTS\.md\s+[§\w]", line)
        if m:
            claims["exceptions_constraints"] = int(m.group(1))
            break
    else:
        claims["exceptions_constraints"] = None

    # Backend test files: "567 test files"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+test\s+files\s*\([^)]*unit\s*\+\s*integration", line)
        if m:
            claims["backend_test_files"] = int(m.group(1))
            break
    else:
        # Fallback: look for "across NNN test files" with "Backend tests" context
        in_backend = False
        for line in cs_text.splitlines():
            if "Backend tests" in line:
                in_backend = True
            if in_backend:
                m = re.search(r"(\d+)\s+test\s+files", line)
                if m:
                    claims["backend_test_files"] = int(m.group(1))
                    break
        else:
            claims["backend_test_files"] = None

    # Frontend test files
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+test\s+files\s*\([^)]*Vitest", line)
        if m:
            claims["frontend_test_files"] = int(m.group(1))
            break
    else:
        in_frontend = False
        for line in cs_text.splitlines():
            if "Frontend tests" in line:
                in_frontend = True
            if in_frontend:
                m = re.search(r"(\d+)\s+test\s+files", line)
                if m:
                    claims["frontend_test_files"] = int(m.group(1))
                    break
        else:
            claims["frontend_test_files"] = None

    # Adoption debt items: "109 ratcheted baseline items"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+ratcheted\s+baseline\s+items", line)
        if m:
            claims["adoption_debt"] = int(m.group(1))
            break
    else:
        claims["adoption_debt"] = None

    # Open questions active: "3 active"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+active\s*\(Q-", line)
        if m:
            claims["open_questions_active"] = int(m.group(1))
            break
    else:
        claims["open_questions_active"] = None

    # Open questions resolved: "9 resolved"
    for line in cs_text.splitlines():
        m = re.search(r"(\d+)\s+resolved", line)
        if m:
            claims["open_questions_resolved"] = int(m.group(1))
            break
    else:
        claims["open_questions_resolved"] = None

    return claims


# ── Fact collection ──────────────────────────────────────────────


def count_rules(constraints_text: str) -> int:
    """Count RULE headings in CONSTRAINTS.md."""
    return len(re.findall(r"^### RULE-\S+", constraints_text, re.MULTILINE))


def count_adrs(adr_index_text: str) -> int:
    """Count ADR entries in INDEX.md."""
    return len(re.findall(r"^\| \[ADR-\d+\]", adr_index_text, re.MULTILINE))


def count_feature_spec_files() -> int:
    """Count .md files in docs/features/ excluding INDEX.md and _TEMPLATE.md."""
    if not FEATURES_DIR.exists():
        return 0
    return sum(1 for f in FEATURES_DIR.rglob("*.md") if f.name not in ("INDEX.md", "_TEMPLATE.md"))


def count_feature_registered(feature_index_text: str) -> int:
    """Count registered feature entries in INDEX.md table."""
    return len(re.findall(r"^\| \[[A-Z][A-Z0-9]+-[0-9]+\]", feature_index_text, re.MULTILINE))


def count_exceptions_baseline() -> int:
    """Count approved exceptions in ai-gate-baseline.json."""
    if not BASELINE_PATH.exists():
        return 0
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return len(data.get("approved_exceptions", []))


def count_exceptions_constraints(constraints_text: str) -> int:
    """Count exception rows in CONSTRAINTS.md §7 table."""
    in_section = False
    count = 0
    for line in constraints_text.splitlines():
        if "### All Approved Exceptions" in line:
            in_section = True
            continue
        if in_section:
            # Table data rows: | N | RULE-... |
            m = re.match(r"^\|\s*(\d+)\s*\|", line)
            if m:
                count += 1
            # End of table
            elif in_section and line.strip() == "" and count > 0:
                break
    return count


def count_backend_test_files() -> int:
    """Count test files under tests/."""
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return 0
    return sum(
        1
        for f in tests_dir.rglob("*.py")
        if f.name.startswith("test_") or f.name.endswith("_test.py")
    )


def count_frontend_test_files() -> int:
    """Count test files under packages/web/."""
    web_dir = ROOT / "packages" / "web"
    if not web_dir.exists():
        return 0
    patterns = ("*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx")
    return sum(1 for p in patterns for _ in web_dir.rglob(p))


def count_adoption_debt() -> int:
    """Count adoption debt items in baseline."""
    if not BASELINE_PATH.exists():
        return 0
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return len(data.get("adoption_debt", []))


def count_open_questions(questions_text: str) -> tuple[int, int]:
    """Count active and resolved questions from INDEX.md.

    Returns (active, resolved).

    Active questions are in the "Active Questions" section with status emojis
    (🟡, 🔴, 🔵). Resolved questions are in the "Resolved Questions" section
    with a different table format (no emoji, has resolution text).
    """
    lines = questions_text.splitlines()
    active = 0
    resolved = 0
    in_active = False
    in_resolved = False

    for line in lines:
        if "## Active Questions" in line:
            in_active = True
            in_resolved = False
            continue
        if "## Resolved Questions" in line:
            in_active = False
            in_resolved = True
            continue
        if line.startswith("## "):
            in_active = False
            in_resolved = False
            continue

        if in_active and re.match(r"^\| \[Q-\d+\]", line):
            # Count as active unless explicitly resolved (✅ in Status column)
            if "✅" in line:
                pass  # resolved — don't count as active
            else:
                active += 1

        if in_resolved and re.match(r"^\| \[Q-\d+\]", line):
            resolved += 1

    return active, resolved


# ── Comparison & reporting ───────────────────────────────────────


def main() -> int:
    if not CURRENT_STATE_PATH.exists():
        print(f"❌ CURRENT_STATE.md not found at {CURRENT_STATE_PATH}")
        return 1

    cs_text = _read(CURRENT_STATE_PATH)
    constraints_text = _read(CONSTRAINTS_PATH) if CONSTRAINTS_PATH.exists() else ""
    adr_index_text = _read(ADR_INDEX_PATH) if ADR_INDEX_PATH.exists() else ""
    feature_index_text = _read(FEATURE_INDEX_PATH) if FEATURE_INDEX_PATH.exists() else ""
    questions_text = _read(QUESTIONS_INDEX_PATH) if QUESTIONS_INDEX_PATH.exists() else ""

    # Extract claims
    claims = extract_claims(cs_text)

    # Collect facts
    facts: dict[str, int | None] = {
        "rule_count": count_rules(constraints_text),
        "adr_count": count_adrs(adr_index_text),
        "feature_spec_files": count_feature_spec_files(),
        "feature_registered": count_feature_registered(feature_index_text),
        "exceptions_baseline": count_exceptions_baseline(),
        "exceptions_constraints": count_exceptions_constraints(constraints_text),
        "backend_test_files": count_backend_test_files(),
        "frontend_test_files": count_frontend_test_files(),
        "adoption_debt": count_adoption_debt(),
    }
    q_active, q_resolved = count_open_questions(questions_text)
    facts["open_questions_active"] = q_active
    facts["open_questions_resolved"] = q_resolved

    # Compare
    labels: dict[str, str] = {
        "rule_count": "Architecture rules (RULE-XX)",
        "adr_count": "ADR entries in INDEX.md",
        "feature_spec_files": "Feature spec files (*.md)",
        "feature_registered": "Registered feature entries",
        "exceptions_baseline": "Exceptions in ai-gate-baseline.json",
        "exceptions_constraints": "Exceptions in CONSTRAINTS.md §7",
        "backend_test_files": "Backend test files (tests/)",
        "frontend_test_files": "Frontend test files (packages/web/)",
        "adoption_debt": "Adoption debt items",
        "open_questions_active": "Active open questions",
        "open_questions_resolved": "Resolved open questions",
    }

    discrepancies = 0
    missing_claims = 0

    print("📋 SSOT Fact Check — CURRENT_STATE.md vs Reality")
    print("=" * 55)

    for key in sorted(labels):
        label = labels[key]
        claimed = claims.get(key)
        actual = facts.get(key)

        if claimed is None:
            print(f"  ⚠️  {label}: claim not found in CURRENT_STATE.md")
            missing_claims += 1
            continue

        if actual is None:
            print(f"  ⚠️  {label}: could not compute actual value")
            continue

        if claimed == actual:
            print(f"  ✅ {label}: {claimed}")
        else:
            print(f"  ❌ {label}: claimed {claimed}, actual {actual}")
            discrepancies += 1

    print("=" * 55)
    if discrepancies == 0 and missing_claims == 0:
        print("✅ All claims consistent — CURRENT_STATE.md is up to date.")
        return 0

    parts: list[str] = []
    if discrepancies:
        parts.append(f"{discrepancies} discrepancy{'ies' if discrepancies != 1 else ''}")
    if missing_claims:
        parts.append(f"{missing_claims} missing claim{'s' if missing_claims != 1 else ''}")

    print(f"⚠️  {'; '.join(parts)} — update docs/_shared/CURRENT_STATE.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
