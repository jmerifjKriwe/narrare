#!/usr/bin/env python3
"""Intent-contract parity gate — the six families (throughput T14a/T14b).

Reads the eight declaration surfaces of a gateway-routed intent and reports every
disagreement among them as one list. The reading layer (``ast`` for the Python
surfaces, ``yaml`` for the two governance files) lives in
:mod:`scripts._intent_surface_reader`, shared with the feature scaffolder; this
module holds the intent facts and the comparisons. It imports no project package,
so it can run in the architecture gate before the packages are importable.

Compared surfaces and families:

- key-set identity across ``LLMIntent`` (``enums``), ``INTENT_CATEGORY_MAP``
  (``categories``), ``INTENT_TO_CATEGORY``/``INTENT_TO_MODE`` (``route_intents``),
  ``ROUTE_CONFIGS`` (``route_configs``) and ``INTENT_PROFILES`` (``profiles``);
- category agreement and mode agreement between the two prompt-route surfaces
  (``route_intents`` and ``route_configs``);
- presence agreement between each lookup table and the route table: an
  ``INTENT_TO_MODE`` entry exists exactly when ``ROUTE_CONFIGS[i].default_mode``
  is not ``None`` (likewise ``INTENT_TO_CATEGORY`` and ``default_category``).
  A removed entry is thus a disagreement, not a silently absent value, and an
  entry where the route table declares no value is a disagreement too;
- prompt-template existence for every routed ``(intent, required locale)`` pair,
  using the intent's resolved category and mode (T14b);
- prompt-surface-manifest agreement: one ``routeable: true`` block per routed
  intent, with matching ``category``/``mode`` (T14b);
- adoption-registry coverage: an entry for every routed intent's prompt path and
  no entry that no routed intent or context mode resolves (T14b).

Required locales follow ADR-026 Phase 5 and mirror
``scripts/adoption/scorer._required_locales_for``: ``en``, ``de`` and ``fr`` for
the localized-required categories (``meta``, ``universal``,
``universal_rules``), ``en`` for every feature category. Requiring ``de``/``fr``
for feature prompts would contradict the EN-only policy the tree implements and
fail on the pristine tree, so the gate compares against the policy, not against
a literal three-locale grid.

Two domains are deliberately outside the compared universe:

- :data:`EXEMPT_INTENTS` — ADR-025: ``EMBED`` is not gateway-routed.
- Intents declared in ``NON_ROUTEABLE_INTENTS`` (``route_table.py``) — they are
  declared non-routeable there, so they have no route-table entry by design.
  Key-set identity is asserted over the routeable universe; an intent that is not
  listed as non-routeable must appear in every surface.
- Manifest blocks with ``routeable: false`` — they are the governance declaration
  of an intentionally unrouted intent (SENTIMENT, GENERATE, …) and are not part
  of the routed block set.

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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import _intent_surface_reader as surfaces  # noqa: E402

_CORE = Path("packages/core/narrare_core")
_ENUMS = _CORE / "llm" / "intents" / "_enums.py"
_CATEGORIES = _CORE / "llm" / "intent_categories.py"
_PROFILES = _CORE / "llm" / "intent_profiles.py"
_ROUTE_INTENTS = _CORE / "prompts" / "route_table_intents.py"
_ROUTE_TABLE = _CORE / "prompts" / "route_table.py"
_BUNDLED = _CORE / "prompts" / "_bundled"
_MANIFEST = Path("scripts/architecture/prompt-surface-manifest.yaml")
_ADOPTION_REGISTRY = Path("scripts/architecture/adoption-registry.yaml")

_MANIFEST_LABEL = "prompt-surface-manifest.yaml"
_REGISTRY_LABEL = "adoption-registry.yaml"

_LOCALES = ("en", "de", "fr")
# ADR-026 Phase 5, mirrored from scripts/adoption/scorer._required_locales_for.
_LOCALIZED_REQUIRED_CATEGORIES = frozenset({"meta", "universal", "universal_rules"})

# ADR-025: EMBED is an embedding operation, deliberately not gateway-routed.
EXEMPT_INTENTS: set[str] = {"EMBED"}

_DECLARED_SURFACES = ("enums", "categories", "route_intents", "route_configs", "profiles")
# `categories` declares the model-selection grouping (ADR-001), not the prompt
# route category; it participates in key-set identity only.
_CATEGORY_VALUE_SURFACES = tuple(
    surface for surface in _DECLARED_SURFACES if surface != "categories"
)


@dataclass(frozen=True, slots=True)
class IntentFact:
    """One surface's declaration of an intent."""

    intent: str
    category: str | None
    mode: str | None


type FactLike = IntentFact | Mapping[str, object]


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _required_locales(category: str) -> tuple[str, ...]:
    """Return the locales a category's prompts must provide (ADR-026 Phase 5)."""
    return _LOCALES if category in _LOCALIZED_REQUIRED_CATEGORIES else ("en",)


def _manifest_facts(root: Path) -> tuple[dict[str, IntentFact], dict[str, IntentFact]]:
    """Return ``(routeable blocks, duplicate blocks)`` from the manifest."""
    blocks = surfaces.mapping_entries(surfaces.load_yaml(root / _MANIFEST).get("routes"))
    facts: dict[str, IntentFact] = {}
    duplicates: dict[str, IntentFact] = {}
    for block in blocks:
        if block.get("routeable") is not True:
            continue
        intent = _text(block.get("intent"))
        if intent is None:
            continue
        fact = IntentFact(intent, _text(block.get("category")), _text(block.get("mode")))
        if intent in facts:
            duplicates[intent] = fact
        else:
            facts[intent] = fact
    return facts, duplicates


def _registry_facts(root: Path) -> dict[str, IntentFact]:
    """Return the registry's ``{category}/{mode}`` compliance entries."""
    compliance = surfaces.load_yaml(root / _ADOPTION_REGISTRY).get("prompt_path_compliance")
    if not isinstance(compliance, dict):
        return {}
    facts: dict[str, IntentFact] = {}
    for key in cast("dict[object, object]", compliance):
        if not isinstance(key, str):
            continue
        category, separator, mode = key.partition("/")
        facts[key] = IntentFact(key, category if separator else None, mode if separator else None)
    return facts


def _prompt_dir_facts(root: Path, route_configs: Mapping[str, IntentFact]) -> dict[str, IntentFact]:
    """Return one fact per ``(intent, locale)`` whose template file exists."""
    facts: dict[str, IntentFact] = {}
    for intent, fact in route_configs.items():
        if fact.category is None or fact.mode is None:
            continue
        for locale in _required_locales(fact.category):
            path = root / _BUNDLED / fact.category / locale / fact.mode / "system.md"
            if path.is_file():
                facts[f"{intent}:{locale}"] = IntentFact(intent, fact.category, fact.mode)
    return facts


def _kept(intent: str, non_routeable: set[str]) -> bool:
    return intent not in EXEMPT_INTENTS and intent not in non_routeable


def collect_facts(root: Path) -> dict[str, dict[str, IntentFact]]:
    """Read the five Python declaration surfaces under *root* into intent facts."""
    enums_tree = surfaces.parse_module(root / _ENUMS)
    categories_tree = surfaces.parse_module(root / _CATEGORIES)
    profiles_tree = surfaces.parse_module(root / _PROFILES)
    route_intents_tree = surfaces.parse_module(root / _ROUTE_INTENTS)
    route_table_tree = surfaces.parse_module(root / _ROUTE_TABLE)

    enum_members = surfaces.class_members(enums_tree, "LLMIntent")
    category_names = surfaces.class_members(categories_tree, "IntentCategory")
    category_entries = surfaces.attribute_dict(
        surfaces.module_assignments(categories_tree).get("INTENT_CATEGORY_MAP")
    )
    model_categories = {
        intent: category_names.get(attribute, attribute)
        for intent, value in category_entries.items()
        if (attribute := surfaces.attribute_name(value)) is not None
    }

    route_assignments = surfaces.module_assignments(route_intents_tree)
    route_categories = surfaces.string_dict(route_assignments.get("INTENT_TO_CATEGORY"))
    route_modes = surfaces.string_dict(route_assignments.get("INTENT_TO_MODE"))

    route_table_assignments = surfaces.module_assignments(route_table_tree)
    route_config_nodes = surfaces.attribute_dict(route_table_assignments.get("ROUTE_CONFIGS"))
    route_configs = {
        intent: surfaces.route_config(value) for intent, value in route_config_nodes.items()
    }
    non_routeable = set(
        surfaces.attribute_dict(route_table_assignments.get("NON_ROUTEABLE_INTENTS"))
    )
    profiles = set(
        surfaces.attribute_dict(surfaces.module_assignments(profiles_tree).get("INTENT_PROFILES"))
    )

    facts: dict[str, dict[str, IntentFact]] = {name: {} for name in _DECLARED_SURFACES}
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
    # Presence surfaces: the two lookup tables are kept apart from the merged
    # ``route_intents`` fact so an absent entry stays distinguishable from a
    # present entry whose route table value is ``None``.
    facts["intent_to_category"] = {
        intent: IntentFact(intent, category, None)
        for intent, category in route_categories.items()
        if _kept(intent, non_routeable)
    }
    facts["intent_to_mode"] = {
        intent: IntentFact(intent, None, mode)
        for intent, mode in route_modes.items()
        if _kept(intent, non_routeable)
    }
    facts["profiles"] = {
        intent: IntentFact(intent, None, None)
        for intent in profiles
        if _kept(intent, non_routeable)
    }
    facts["route_context_modes"] = {
        f"{intent}:{mode}": IntentFact(intent, category, mode)
        for intent, node in route_config_nodes.items()
        if _kept(intent, non_routeable) and (category := surfaces.route_config(node)[0]) is not None
        for mode in surfaces.allowed_context_modes(node)
    }
    facts["manifest"], facts["manifest_duplicates"] = _manifest_facts(root)
    facts["adoption_registry"] = _registry_facts(root)
    facts["prompt_dirs"] = _prompt_dir_facts(root, facts["route_configs"])
    return facts


def count_declared_intents(root: Path) -> int:
    """Return the number of ``LLMIntent`` members (including exempt intents)."""
    return len(surfaces.class_members(surfaces.parse_module(root / _ENUMS), "LLMIntent"))


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


def _presence_disagreements(
    facts: Mapping[str, Mapping[str, FactLike]],
    presence_surface: str,
    field: str,
    label: str,
) -> list[str]:
    """Report lookup-table entries whose existence contradicts the route table.

    Presence is compared explicitly instead of treating a missing entry as a
    ``None`` value: ``INTENT_TO_MODE`` must have an entry exactly when
    ``ROUTE_CONFIGS[i].default_mode`` is not ``None``.
    """
    if presence_surface not in facts:
        return []
    declared = facts[presence_surface]
    messages: list[str] = []
    for intent, fact in sorted(facts.get("route_configs", {}).items()):
        expected = _fact_field(fact, field)
        entry = declared.get(intent)
        actual = _fact_field(entry, field) if entry is not None else None
        if expected is None:
            if entry is not None:
                messages.append(
                    f"{intent}: present in '{label}' surface ('{actual}') "
                    f"but 'route_configs' declares no {field}"
                )
        elif entry is None:
            messages.append(
                f"{intent}: missing from '{label}' surface "
                f"but 'route_configs' declares {field} '{expected}'"
            )
    return messages


def _prompt_dir_disagreements(facts: Mapping[str, Mapping[str, FactLike]]) -> list[str]:
    """Report routed intents whose required-locale prompt template is absent."""
    if "prompt_dirs" not in facts:
        return []
    present = facts["prompt_dirs"]
    messages: list[str] = []
    for intent, fact in sorted(facts.get("route_configs", {}).items()):
        category = _fact_field(fact, "category")
        mode = _fact_field(fact, "mode")
        if category is None or mode is None:
            continue
        for locale in _required_locales(category):
            if f"{intent}:{locale}" in present:
                continue
            path = _BUNDLED / category / locale / mode / "system.md"
            messages.append(f"{intent}: missing prompt template for locale '{locale}' at '{path}'")
    return messages


def _manifest_disagreements(facts: Mapping[str, Mapping[str, FactLike]]) -> list[str]:
    """Report manifest block coverage and value disagreement against the route table."""
    if "manifest" not in facts:
        return []
    manifest = facts["manifest"]
    routed = facts.get("route_configs", {})
    messages: list[str] = []
    for intent in sorted(set(routed) - set(manifest)):
        messages.append(f"{intent}: missing block in {_MANIFEST_LABEL} for a routed intent")
    for intent in sorted(set(manifest) - set(routed)):
        messages.append(f"{intent}: block in {_MANIFEST_LABEL} has no route entry")
    for intent in sorted(set(routed) & set(manifest)):
        for field in ("category", "mode"):
            expected = _fact_field(routed[intent], field)
            actual = _fact_field(manifest[intent], field)
            if expected != actual:
                messages.append(
                    f"{intent}: {field} disagreement between 'route_configs' "
                    f"('{expected}') and {_MANIFEST_LABEL} ('{actual}')"
                )
    for intent in sorted(facts.get("manifest_duplicates", {})):
        messages.append(f"{intent}: duplicate block in {_MANIFEST_LABEL}")
    return messages


def _adoption_registry_disagreements(facts: Mapping[str, Mapping[str, FactLike]]) -> list[str]:
    """Report missing registry entries for routed intents and entries nothing resolves."""
    if "adoption_registry" not in facts:
        return []
    registry = facts["adoption_registry"]
    required: dict[str, str] = {}
    resolvable: set[str] = set()
    for intent, fact in facts.get("route_configs", {}).items():
        category = _fact_field(fact, "category")
        mode = _fact_field(fact, "mode")
        if category is None or mode is None:
            continue
        key = f"{category}/{mode}"
        required[key] = intent
        resolvable.add(key)
    for fact in facts.get("route_context_modes", {}).values():
        category = _fact_field(fact, "category")
        mode = _fact_field(fact, "mode")
        if category is not None and mode is not None:
            resolvable.add(f"{category}/{mode}")
    messages: list[str] = []
    for key in sorted(set(required) - set(registry)):
        messages.append(f"{required[key]}: missing entry '{key}' in {_REGISTRY_LABEL}")
    for key in sorted(set(registry) - resolvable):
        messages.append(f"{key}: entry in {_REGISTRY_LABEL} matches no routed intent or mode")
    return messages


def find_disagreements(facts: Mapping[str, Mapping[str, FactLike]]) -> list[str]:
    """Return every cross-surface disagreement, naming the intent and both surfaces."""
    surface_intents = {
        surface: {intent for intent in facts.get(surface, {}) if intent not in EXEMPT_INTENTS}
        for surface in _DECLARED_SURFACES
    }
    declared = surface_intents["enums"]
    messages: list[str] = []
    for surface in _DECLARED_SURFACES[1:]:
        for intent in sorted(declared - surface_intents[surface]):
            messages.append(f"{intent}: missing from '{surface}' surface (declared in 'enums')")
        for intent in sorted(surface_intents[surface] - declared):
            messages.append(f"{intent}: present in '{surface}' surface but missing from 'enums'")
    messages.extend(_agreement(facts, declared, "category", _CATEGORY_VALUE_SURFACES))
    messages.extend(_agreement(facts, declared, "mode", _DECLARED_SURFACES))
    messages.extend(
        _presence_disagreements(facts, "intent_to_category", "category", "INTENT_TO_CATEGORY")
    )
    messages.extend(_presence_disagreements(facts, "intent_to_mode", "mode", "INTENT_TO_MODE"))
    messages.extend(_prompt_dir_disagreements(facts))
    messages.extend(_manifest_disagreements(facts))
    messages.extend(_adoption_registry_disagreements(facts))
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
