#!/usr/bin/env python3
"""Intent-contract parity gate — first slice (throughput T14a).

Reads the Python declaration surfaces of a gateway-routed intent and reports every
disagreement among them as one list. It parses the sources with ``ast`` and imports
no project code, so it can run in the architecture gate before the packages are
importable.

Compared surfaces and families (T14a):

- key-set identity across ``LLMIntent`` (``enums``), ``INTENT_CATEGORY_MAP``
  (``categories``), ``INTENT_TO_CATEGORY``/``INTENT_TO_MODE`` (``route_intents``),
  ``ROUTE_CONFIGS`` (``route_configs``) and ``INTENT_PROFILES`` (``profiles``);
- category agreement and mode agreement between the two prompt-route surfaces
  (``route_intents`` and ``route_configs``).

**Not yet implemented (T14b seam).** Prompt-directory existence per locale,
prompt-surface-manifest block agreement and adoption-registry coverage are the
three remaining families of spec §4. Add them as further checks inside
:func:`find_disagreements`; the surface extraction in :func:`collect_facts` and
the exemption below stay as they are.

Two domains are deliberately outside the compared universe:

- :data:`EXEMPT_INTENTS` — ADR-025: ``EMBED`` is not gateway-routed.
- Intents declared in ``NON_ROUTEABLE_INTENTS`` (``route_table.py``) — they are
  declared non-routeable there, so they have no route-table entry by design.
  Key-set identity is asserted over the routeable universe; an intent that is not
  listed as non-routeable must appear in every surface.

``INTENT_CATEGORY_MAP`` groups intents for model selection (ADR-001), while
``INTENT_TO_CATEGORY`` names the bundled prompt directory. They are different
facts that share the word "category": measured today, five intents diverge —
``CHAT`` (``chat``/``writing``), ``SUMMARIZE`` (``planning``/``analysis``),
``EXTRACT`` and ``FACT_EXTRACT`` (``extraction``/``analysis``) and ``SUGGEST``
(``extraction``/``writing``). The gate therefore compares ``categories`` by key
set only; category *values* are compared among the surfaces that declare the
prompt-route category.

Usage:
    python scripts/check_intent_parity.py [root]

Exit codes:
    0: no disagreements.
    1: one line per disagreement (or an unreadable declaration surface).
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent

_CORE = Path("packages/core/narrare_core")
_ENUMS = _CORE / "llm" / "intents" / "_enums.py"
_CATEGORIES = _CORE / "llm" / "intent_categories.py"
_PROFILES = _CORE / "llm" / "intent_profiles.py"
_ROUTE_INTENTS = _CORE / "prompts" / "route_table_intents.py"
_ROUTE_TABLE = _CORE / "prompts" / "route_table.py"

# ADR-025: EMBED is an embedding operation, deliberately not gateway-routed.
EXEMPT_INTENTS: set[str] = {"EMBED"}

_SURFACES = ("enums", "categories", "route_intents", "route_configs", "profiles")
# `categories` declares the model-selection grouping (ADR-001), not the prompt
# route category; it participates in key-set identity only.
_CATEGORY_VALUE_SURFACES = tuple(surface for surface in _SURFACES if surface != "categories")


@dataclass(frozen=True, slots=True)
class IntentFact:
    """One surface's declaration of an intent."""

    intent: str
    category: str | None
    mode: str | None


type FactLike = IntentFact | Mapping[str, object]


def _parse_module(path: Path) -> ast.Module:
    """Parse *path*, raising ``RuntimeError`` so a broken surface never passes silently."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"cannot read declaration surface {path}: {exc}") from exc
    except SyntaxError as exc:
        raise RuntimeError(f"cannot parse declaration surface {path}: {exc}") from exc


def _module_assignments(tree: ast.Module) -> dict[str, ast.expr]:
    """Return top-level ``NAME = value`` / ``NAME: type = value`` assignments."""
    assignments: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assignments[node.target.id] = node.value
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
    return assignments


def _class_members(tree: ast.Module, class_name: str) -> dict[str, str]:
    """Return ``{MEMBER: "value"}`` for a ``StrEnum``-style class."""
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        members: dict[str, str] = {}
        for item in node.body:
            if not isinstance(item, ast.Assign | ast.AnnAssign) or item.value is None:
                continue
            if not isinstance(item.value, ast.Constant) or not isinstance(item.value.value, str):
                continue
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    members[target.id] = item.value.value
        return members
    return {}


def _attribute_name(node: ast.expr) -> str | None:
    return node.attr if isinstance(node, ast.Attribute) else None


def _string_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _attribute_dict(node: ast.expr | None) -> dict[str, ast.expr]:
    """Return ``{LLMIntent.X: value}`` entries from a dict literal."""
    if not isinstance(node, ast.Dict):
        return {}
    entries: dict[str, ast.expr] = {}
    for key, value in zip(node.keys, node.values, strict=True):
        if key is not None and (intent := _attribute_name(key)) is not None:
            entries[intent] = value
    return entries


def _string_dict(node: ast.expr | None) -> dict[str, str]:
    entries: dict[str, str] = {}
    for intent, value in _attribute_dict(node).items():
        text = _string_value(value)
        if text is not None:
            entries[intent] = text
    return entries


def _route_config(node: ast.expr) -> tuple[str | None, str | None]:
    """Extract ``(category, mode)`` from a ``PromptRouteConfig(...)`` call."""
    if not isinstance(node, ast.Call):
        return None, None
    category = _string_value(node.args[0]) if node.args else None
    mode = _string_value(node.args[1]) if len(node.args) > 1 else None
    for keyword in node.keywords:
        if keyword.arg == "category":
            category = _string_value(keyword.value)
        elif keyword.arg == "mode":
            mode = _string_value(keyword.value)
    return category, mode


def _kept(intent: str, non_routeable: set[str]) -> bool:
    return intent not in EXEMPT_INTENTS and intent not in non_routeable


def collect_facts(root: Path) -> dict[str, dict[str, IntentFact]]:
    """Read the five Python declaration surfaces under *root* into intent facts."""
    enums_tree = _parse_module(root / _ENUMS)
    categories_tree = _parse_module(root / _CATEGORIES)
    profiles_tree = _parse_module(root / _PROFILES)
    route_intents_tree = _parse_module(root / _ROUTE_INTENTS)
    route_table_tree = _parse_module(root / _ROUTE_TABLE)

    enum_members = _class_members(enums_tree, "LLMIntent")
    category_names = _class_members(categories_tree, "IntentCategory")
    category_entries = _attribute_dict(
        _module_assignments(categories_tree).get("INTENT_CATEGORY_MAP")
    )
    model_categories = {
        intent: category_names.get(attribute, attribute)
        for intent, value in category_entries.items()
        if (attribute := _attribute_name(value)) is not None
    }

    route_assignments = _module_assignments(route_intents_tree)
    route_categories = _string_dict(route_assignments.get("INTENT_TO_CATEGORY"))
    route_modes = _string_dict(route_assignments.get("INTENT_TO_MODE"))

    route_table_assignments = _module_assignments(route_table_tree)
    route_configs = {
        intent: _route_config(value)
        for intent, value in _attribute_dict(route_table_assignments.get("ROUTE_CONFIGS")).items()
    }
    non_routeable = set(_attribute_dict(route_table_assignments.get("NON_ROUTEABLE_INTENTS")))
    profiles = set(_attribute_dict(_module_assignments(profiles_tree).get("INTENT_PROFILES")))

    facts: dict[str, dict[str, IntentFact]] = {name: {} for name in _SURFACES}
    facts["enums"] = {
        intent: IntentFact(intent, None, None)
        for intent in enum_members
        if _kept(intent, non_routeable)
    }
    facts["categories"] = {
        intent: IntentFact(intent, category, None)
        for intent, category in model_categories.items()
        if _kept(intent, non_routeable)
    }
    facts["route_intents"] = {
        intent: IntentFact(intent, route_categories.get(intent), route_modes.get(intent))
        for intent in set(route_categories) | set(route_modes)
        if _kept(intent, non_routeable)
    }
    facts["route_configs"] = {
        intent: IntentFact(intent, category, mode)
        for intent, (category, mode) in route_configs.items()
        if _kept(intent, non_routeable)
    }
    facts["profiles"] = {
        intent: IntentFact(intent, None, None)
        for intent in profiles
        if _kept(intent, non_routeable)
    }
    return facts


def count_declared_intents(root: Path) -> int:
    """Return the number of ``LLMIntent`` members (including exempt intents)."""
    return len(_class_members(_parse_module(root / _ENUMS), "LLMIntent"))


def _fact_field(fact: FactLike, field: str) -> str | None:
    if isinstance(fact, IntentFact):
        return fact.category if field == "category" else fact.mode
    value = fact.get(field)
    return value if isinstance(value, str) else None


def _agreement(
    facts: Mapping[str, Mapping[str, FactLike]],
    intents: set[str],
    field: str,
    surfaces: Sequence[str],
) -> list[str]:
    """Report each intent whose *field* differs between any two of *surfaces*."""
    messages: list[str] = []
    for intent in sorted(intents):
        seen: list[tuple[str, str]] = []
        for surface in surfaces:
            fact = facts.get(surface, {}).get(intent)
            if fact is None:
                continue
            value = _fact_field(fact, field)
            if value is not None:
                seen.append((surface, value))
        for surface, value in seen[1:]:
            first_surface, first_value = seen[0]
            if value != first_value:
                messages.append(
                    f"{intent}: {field} disagreement between '{first_surface}' "
                    f"('{first_value}') and '{surface}' ('{value}')"
                )
                break
    return messages


def find_disagreements(facts: Mapping[str, Mapping[str, FactLike]]) -> list[str]:
    """Return every cross-surface disagreement, naming the intent and both surfaces."""
    surface_intents = {
        surface: {intent for intent in facts.get(surface, {}) if intent not in EXEMPT_INTENTS}
        for surface in _SURFACES
    }
    declared = surface_intents["enums"]
    messages: list[str] = []
    for surface in _SURFACES[1:]:
        for intent in sorted(declared - surface_intents[surface]):
            messages.append(f"{intent}: missing from '{surface}' surface (declared in 'enums')")
        for intent in sorted(surface_intents[surface] - declared):
            messages.append(f"{intent}: present in '{surface}' surface but missing from 'enums'")
    messages.extend(_agreement(facts, declared, "category", _CATEGORY_VALUE_SURFACES))
    messages.extend(_agreement(facts, declared, "mode", _SURFACES))
    return messages


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Intent-contract parity gate.")
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()

    try:
        facts = collect_facts(root)
        intents = count_declared_intents(root)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    disagreements = find_disagreements(facts)
    print(
        f"{intents} intents, {len(facts['route_configs'])} routed, "
        f"{len(disagreements)} disagreements"
    )
    for message in disagreements:
        print(message)
    return 1 if disagreements else 0


if __name__ == "__main__":
    sys.exit(main())
