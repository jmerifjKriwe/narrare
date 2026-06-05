"""RULE-INTENT · Intent consistency and route governance checks.

Verifies the three-way PromptComposer route classification from ``routes.py``:
- **Routeable** intents (in ``_INTENT_TO_MODE``) must have a bundled EN target.
- **Context-mode-required** intents (in ``_CONTEXT_MODE_REQUIRED_INTENTS``)
  are in the category map but have no default mode — callers must supply one.
- **Non-routeable** intents (in ``_NON_ROUTEABLE_INTENTS``) are explicitly
  excluded from PromptComposer routing with documented rationale.

Every LLMIntent must have exactly one of these three governance decisions.

INFRA-012: new violations fail CI; pre-existing gaps are ratcheted via baseline.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.architecture.helpers import ROOT
from scripts.architecture.types import CheckResult, Violation


def _parse_routes_dict(
    source: str,
    dict_name: str,
) -> dict[str, str]:
    """Extract a ``{LLMIntent.X: "value"}`` dict from routes.py via regex.

    Returns a mapping of *intent_value* → *string_value* (e.g.
    ``{"write": "writing"}``).
    """
    result: dict[str, str] = {}

    in_dict = False
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{dict_name}:"):
            in_dict = True
            continue
        if in_dict and stripped == "}":
            in_dict = False
            continue
        if not in_dict:
            continue

        # Match: LLMIntent.FOO: "value"
        # Value char class: a-z, _, /, 0-9, - (hyphen for e.g. "beta_reader_deepdive")
        m = re.match(r"LLMIntent\.([A-Z_]+):\s*\"([a-z_/0-9-]*)\"", stripped)
        if m:
            enum_name = m.group(1)
            value = m.group(2)
            result[enum_name.lower()] = value

    return result


def _parse_routes_rationale_dict(
    source: str,
    dict_name: str,
) -> dict[str, str]:
    """Extract a dict with rationale strings from routes.py.

    Handles both ``"..."`` and ``("...")`` formats. Catches multi-line
    parenthesized strings (extracts just the enum name with a placeholder).
    """
    result: dict[str, str] = {}

    in_dict = False
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{dict_name}:"):
            in_dict = True
            continue
        if in_dict and stripped == "}":
            in_dict = False
            continue
        if not in_dict:
            continue

        # Format 1: LLMIntent.FOO: ("multi line...") -- parenthesized
        m = re.match(r"LLMIntent\.([A-Z_]+):\s*\(\s*$", stripped)
        if m:
            enum_name = m.group(1)
            result[enum_name.lower()] = "(baselined)"
            continue

        # Format 2: LLMIntent.FOO: ("single line..."),   -- parenthesized, inline
        m = re.match(r"LLMIntent\.([A-Z_]+):\s*\(\"(.+)\"\)", stripped)
        if m:
            enum_name = m.group(1)
            value = m.group(2)
            result[enum_name.lower()] = value
            continue

        # Format 3: LLMIntent.FOO: "value",
        m = re.match(r"LLMIntent\.([A-Z_]+):\s*\"(.+)\"", stripped)
        if m:
            enum_name = m.group(1)
            value = m.group(2)
            result[enum_name.lower()] = value
            continue

    return result


def _parse_intent_values(source: str) -> set[str]:
    """Extract all LLMIntent string values from intents.py.

    Returns a set of lowercase-intent-values (e.g. ``{"write", "analyse"}``).
    """
    values: set[str] = set()
    for line in source.splitlines():
        m = re.match(r"^\s+([A-Z][A-Z_0-9]+)\s*=\s*\"([a-z_]+)\"\s*#?", line)
        if m and m.group(1) != "EMBED":
            values.add(m.group(2))
    return values


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def check_intent_consistency(result: CheckResult) -> None:
    """Verify every LLMIntent has a PromptComposer route governance decision.

    Three-way governance:
    1. **Routeable** — in ``_INTENT_TO_MODE`` → must have bundled EN target.
    2. **Context-mode-required** — in ``_CONTEXT_MODE_REQUIRED_INTENTS`` →
       requires caller-supplied mode.
    3. **Non-routeable** — in ``_NON_ROUTEABLE_INTENTS`` → explicitly excluded
       with documented rationale.

    INFRA-012: new findings are blocking violations. Baseline-listed items are
    approved exceptions for legacy gaps.
    """
    intents_path = ROOT / "packages" / "core" / "narrare_core" / "llm" / "intents.py"
    routes_path = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "routes.py"
    bundled_root = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"

    if not intents_path.is_file() or not routes_path.is_file():
        return

    routes_src = routes_path.read_text(encoding="utf-8")
    intents_src = intents_path.read_text(encoding="utf-8")

    all_intents = _parse_intent_values(intents_src)
    if not all_intents:
        return

    # Parse all four governance dicts from routes.py
    category_map = _parse_routes_dict(routes_src, "_INTENT_TO_CATEGORY")
    mode_map = _parse_routes_dict(routes_src, "_INTENT_TO_MODE")
    context_required = _parse_routes_rationale_dict(routes_src, "_CONTEXT_MODE_REQUIRED_INTENTS")
    non_routeable = _parse_routes_rationale_dict(routes_src, "_NON_ROUTEABLE_INTENTS")

    routeable_intents: set[str] = set(mode_map.keys())
    context_mode_intents: set[str] = set(context_required.keys())
    non_routeable_intents: set[str] = set(non_routeable.keys())

    for intent_val in sorted(all_intents):
        # Determine governance status
        in_routeable = intent_val in routeable_intents
        in_context = intent_val in context_mode_intents
        in_non_routeable = intent_val in non_routeable_intents
        in_category = intent_val in category_map

        governance_count = sum([in_routeable, in_context, in_non_routeable])

        # --- Check 1: Exactly one governance classification ---
        if governance_count == 0:
            detail = (
                f"LLMIntent '{intent_val}' has no route governance decision — "
                f"add to _INTENT_TO_MODE, _CONTEXT_MODE_REQUIRED_INTENTS, "
                f"or _NON_ROUTEABLE_INTENTS in routes.py"
            )
            result.violations.append(
                Violation(
                    file=Path("packages/core/narrare_core/prompts/routes.py"),
                    line=0,
                    rule="PROMPT-ROUTE",
                    detail=detail,
                )
            )
            continue

        if governance_count > 1:
            detail = (
                f"LLMIntent '{intent_val}' has {governance_count} governance "
                f"classifications — must be in exactly one of _INTENT_TO_MODE, "
                f"_CONTEXT_MODE_REQUIRED_INTENTS, or _NON_ROUTEABLE_INTENTS"
            )
            result.violations.append(
                Violation(
                    file=Path("packages/core/narrare_core/prompts/routes.py"),
                    line=0,
                    rule="PROMPT-ROUTE",
                    detail=detail,
                )
            )
            continue

        # --- Check 2: Routeable intents must have a category mapping ---
        if in_routeable and not in_category:
            result.violations.append(
                Violation(
                    file=Path("packages/core/narrare_core/prompts/routes.py"),
                    line=0,
                    rule="PROMPT-ROUTE",
                    detail=(
                        f"LLMIntent '{intent_val}' has a mode mapping but no "
                        f"category mapping in _INTENT_TO_CATEGORY"
                    ),
                )
            )

        # --- Check 3: Routeable intents must have a bundled EN target ---
        if in_routeable and in_category:
            category = category_map[intent_val]
            mode = mode_map[intent_val]
            if mode:
                bundled_path = bundled_root / category / "en" / mode / "system.md"
                if not bundled_path.exists():
                    result.violations.append(
                        Violation(
                            file=Path(str(bundled_path.relative_to(ROOT))),
                            line=0,
                            rule="PROMPT-ROUTE",
                            detail=(
                                f"Routeable LLMIntent '{intent_val}' "
                                f"(category={category}, mode={mode}) has no "
                                f"bundled EN prompt target: "
                                f"_bundled/{category}/en/{mode}/system.md"
                            ),
                        )
                    )

        # --- Check 4: Context-mode-required intents must have a category ---
        if in_context and not in_category:
            result.violations.append(
                Violation(
                    file=Path("packages/core/narrare_core/prompts/routes.py"),
                    line=0,
                    rule="PROMPT-ROUTE",
                    detail=(
                        f"LLMIntent '{intent_val}' is context-mode-required but "
                        f"has no category mapping in _INTENT_TO_CATEGORY"
                    ),
                )
            )

        # --- Check 5: Non-routeable intents should have rationale ---
        if in_non_routeable:
            rationale = non_routeable.get(intent_val, "")
            if not rationale:
                result.violations.append(
                    Violation(
                        file=Path("packages/core/narrare_core/prompts/routes.py"),
                        line=0,
                        rule="PROMPT-ROUTE",
                        detail=(
                            f"LLMIntent '{intent_val}' is non-routeable but has "
                            f"no rationale string in _NON_ROUTEABLE_INTENTS"
                        ),
                    )
                )
