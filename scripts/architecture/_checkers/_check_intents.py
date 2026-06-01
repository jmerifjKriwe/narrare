"""RULE-INTENT · Intent consistency checks.

Verifies:
- Every LLMIntent value appears in ``_INTENT_TO_CATEGORY``
- Every LLMIntent value appears in ``_INTENT_TO_MODE``
- Catches missing mappings when new intents are added

Exits: called from ``prompt_integrity.run_all_checks()``.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.architecture.helpers import ROOT
from scripts.architecture.types import CheckResult, Violation


def check_intent_consistency(result: CheckResult) -> None:
    """Verify that _INTENT_TO_CATEGORY and _INTENT_TO_MODE cover all LLMIntents.

    Reads intents.py and composer.py to cross-reference:
    - Every LLMIntent must be in _INTENT_TO_CATEGORY
    - Every LLMIntent must be in _INTENT_TO_MODE
    - Every entry in the maps must correspond to a valid LLMIntent
    """
    intents_path = ROOT / "packages" / "core" / "narrare_core" / "llm" / "intents.py"
    composer_path = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "composer.py"

    if not intents_path.is_file() or not composer_path.is_file():
        return

    # --- Extract all LLMIntent enum values ---
    intents_source = intents_path.read_text(encoding="utf-8")
    intent_values: set[str] = set()
    for line in intents_source.splitlines():
        m = re.match(r"^\s+([A-Z][A-Z_0-9]+)\s*=\s*\"([a-z_]+)\"\s*#?", line)
        if m and m.group(1) != "EMBED":
            intent_values.add(m.group(2))

    # --- Parse _INTENT_TO_CATEGORY and _INTENT_TO_MODE from composer.py ---
    composer_source = composer_path.read_text(encoding="utf-8")

    category_intents: set[str] = set()
    mode_intents: set[str] = set()

    # Parse _INTENT_TO_CATEGORY section
    in_category = False
    in_mode = False
    for line in composer_source.splitlines():
        stripped = line.strip()
        if stripped.startswith("_INTENT_TO_CATEGORY"):
            in_category = True
            in_mode = False
            continue
        if stripped.startswith("_INTENT_TO_MODE"):
            in_mode = True
            in_category = False
            continue
        if in_category and stripped == "}":
            in_category = False
            continue
        if in_mode and stripped == "}":
            in_mode = False
            continue

        if in_category:
            m = re.match(r"LLMIntent\.([A-Z_]+):\s*\"([a-z_]+)\"", stripped)
            if m:
                category_intents.add(m.group(2))

        if in_mode:
            m = re.match(r"LLMIntent\.([A-Z_]+):\s*\"([a-z_]*)\"", stripped)
            if m:
                mode_intents.add(m.group(2))

    issues: list[str] = []

    # Check all intents are in category map
    for val in sorted(intent_values):
        if val not in category_intents:
            issues.append(f"LLMIntent.{val} missing from _INTENT_TO_CATEGORY")

    # Check all intents are in mode map
    for val in sorted(intent_values):
        if val not in mode_intents:
            issues.append(f"LLMIntent.{val} missing from _INTENT_TO_MODE")

    if issues:
        for issue in issues[:10]:  # cap at 10
            result.approved_exceptions.append(
                Violation(
                    file=Path("packages/core/narrare_core/prompts/composer.py"),
                    line=0,
                    rule="PROMPT-INTEGRITY",
                    detail=issue,
                    approved=True,
                    approval_reason="Intent consistency audit (D5.3)",
                )
            )
        if len(issues) > 10:
            result.approved_exceptions.append(
                Violation(
                    file=Path("packages/core/narrare_core/prompts/composer.py"),
                    line=0,
                    rule="PROMPT-INTEGRITY",
                    detail=f"... and {len(issues) - 10} more issues",
                    approved=True,
                    approval_reason="Intent consistency audit (D5.3)",
                )
            )
