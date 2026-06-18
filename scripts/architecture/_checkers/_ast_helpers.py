"""AST helpers for parsing Narrare Core Python sources.

Used by architecture checkers to inspect route_table.py, intents.py,
and variable_registry.py without importing Core at runtime.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "extract_frozenset_strings",
    "parse_frozenset_names",
    "parse_intent_dict",
    "parse_non_routeable_intents",
    "parse_route_configs_context_modes",
    "parse_route_table_dicts",
    "parse_str_enum_members",
]


def parse_str_enum_members(path: Path) -> dict[str, str]:
    """Parse ``class MyEnum(StrEnum):`` members → {NAME: "value"}."""
    if not path.is_file():
        return {}

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    members: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant):
                        members[target.id] = str(item.value.value)
    return members


def _named_assigns(tree: ast.AST) -> list[tuple[str, ast.expr]]:
    """Yield ``(name, value)`` pairs from both Assign and AnnAssign nodes.

    Handles both plain assignments (``X = ...``) and annotated assignments
    (``X: type = ...``).  This is required because ``route_table.py`` uses
    annotated assignments (``INTENT_TO_CATEGORY: dict[...] = {...}``) while
    test fixtures use plain assignments.
    """
    result: list[tuple[str, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result.append((target.id, node.value))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            result.append((node.target.id, node.value))
    return result


def parse_route_table_dicts(path: Path) -> dict[str, dict[str, Any]]:
    """Parse INTENT_TO_CATEGORY and INTENT_TO_MODE from route_table.py."""
    if not path.is_file():
        return {}

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    categories: dict[str, str] = {}
    modes: dict[str, str] = {}

    for name, value in _named_assigns(tree):
        if name == "INTENT_TO_CATEGORY":
            categories = parse_intent_dict(value)
        elif name == "INTENT_TO_MODE":
            modes = parse_intent_dict(value)

    result: dict[str, dict[str, Any]] = {}
    for intent in set(categories) | set(modes):
        # Use None for intents absent from INTENT_TO_MODE (aggregate flows with
        # default_mode=None).  Empty string "" means the intent IS in
        # INTENT_TO_MODE but explicitly set to "" (the forbidden root-mode per
        # ADR-049 D3).  This distinction lets the PROMPT-ROOT-MODE gate
        # differentiate forbidden root-mode from exempt aggregate flows.
        result[intent] = {
            "category": categories.get(intent, ""),
            "mode": modes.get(intent),
            "has_explicit_mode": intent in modes,
        }
    return result


def parse_intent_dict(node: ast.expr) -> dict[str, str]:
    """Parse ``{LLMIntent.X: "value", ...}`` → {"X": "value"}."""
    result: dict[str, str] = {}
    if not isinstance(node, ast.Dict):
        return result
    for key, val in zip(node.keys, node.values, strict=True):
        if isinstance(key, ast.Attribute) and isinstance(val, ast.Constant):
            result[key.attr] = str(val.value)
    return result


def parse_non_routeable_intents(path: Path) -> set[str]:
    """Parse NON_ROUTEABLE_INTENTS dict keys from route_table.py."""
    if not path.is_file():
        return set()

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    for name, value in _named_assigns(tree):
        if name == "NON_ROUTEABLE_INTENTS":
            return set(parse_intent_dict(value).keys())
    return set()


def parse_route_configs_context_modes(path: Path) -> dict[str, frozenset[str]]:
    """Parse ``ROUTE_CONFIGS`` and extract ``allowed_context_modes`` per intent.

    Returns ``{intent_name: frozenset[str]}`` — only intents that declare
    ``allowed_context_modes`` are included.  Intents without the kwarg are
    absent from the result.

    Used by the ADR-049 Phase D ORPHAN-TEMPLATE and PROMPT-CONTEXT-MODES gates
    to determine which context-mode templates are legitimately reachable.
    """
    if not path.is_file():
        return {}

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    result: dict[str, frozenset[str]] = {}

    for name, value in _named_assigns(tree):
        if name != "ROUTE_CONFIGS":
            continue
        if not isinstance(value, ast.Dict):
            continue
        for key, val in zip(value.keys, value.values, strict=True):
            if key is None:
                continue
            intent_name = _route_config_intent_name(key)
            if intent_name is None:
                continue
            modes = _route_config_allowed_context_modes(val)
            if modes:
                result[intent_name] = modes
    return result


def _route_config_intent_name(key: ast.expr) -> str | None:
    """Extract the intent name from a ROUTE_CONFIGS dict key.

    Handles ``LLMIntent.WRITE`` → ``"WRITE"``.
    """
    if isinstance(key, ast.Attribute):
        return key.attr
    return None


def _route_config_allowed_context_modes(val: ast.expr) -> frozenset[str]:
    """Extract ``allowed_context_modes`` from a ``PromptRouteConfig(...)`` call."""
    if not isinstance(val, ast.Call):
        return frozenset()
    for kw in val.keywords:
        if kw.arg == "allowed_context_modes":
            return extract_frozenset_strings(kw.value)
    return frozenset()


def parse_frozenset_names(path: Path) -> dict[str, frozenset[str]]:
    """Parse the three variable registry frozensets from variable_registry.py."""
    if not path.is_file():
        return {}

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    sets: dict[str, frozenset[str]] = {}
    target_names = {"USER_CONTENT_VARS", "SYSTEM_VARS", "FEATURE_DYNAMIC_VARS"}

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id in target_names
                and node.value is not None
            ):
                sets[node.target.id] = extract_frozenset_strings(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in target_names:
                    sets[target.id] = extract_frozenset_strings(node.value)
    return sets


def extract_frozenset_strings(node: ast.expr) -> frozenset[str]:
    """Extract string values from a frozenset({...}) or set({...}) AST node."""
    strings: set[str] = set()
    if isinstance(node, ast.Call):
        for arg in getattr(node, "args", []):
            if isinstance(arg, (ast.Set, ast.List)):
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        strings.add(elt.value)
    elif isinstance(node, ast.Set):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                strings.add(elt.value)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        strings.update(extract_frozenset_strings(node.left))
        strings.update(extract_frozenset_strings(node.right))
    return frozenset(strings)
