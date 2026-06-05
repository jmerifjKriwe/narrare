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

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "INTENT_TO_CATEGORY":
                categories = parse_intent_dict(node.value)
            elif target.id == "INTENT_TO_MODE":
                modes = parse_intent_dict(node.value)

    result: dict[str, dict[str, Any]] = {}
    for intent in set(categories) | set(modes):
        result[intent] = {
            "category": categories.get(intent, ""),
            "mode": modes.get(intent, ""),
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

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "NON_ROUTEABLE_INTENTS":
                return set(parse_intent_dict(node.value).keys())
    return set()


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
