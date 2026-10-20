#!/usr/bin/env python3
"""AST and YAML readers for the eight intent declaration surfaces.

The parity gate (:mod:`scripts.check_intent_parity`) and the feature
scaffolder (:mod:`scripts.scaffold_intent`) read the same declarations: five
Python modules through ``ast`` and two governance files through ``yaml``.
Sharing that reading layer previously happened through the gate's private
helpers, which made one script's internals another script's API. The readers
live here now — public, single-purpose, imported by both consumers; neither
consumer imports the other.

Every reader fails loudly: an unreadable or malformed surface raises
``RuntimeError`` instead of returning an empty result that would let a broken
surface pass a gate.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, cast

import yaml

if TYPE_CHECKING:
    from pathlib import Path


def parse_module(path: Path) -> ast.Module:
    """Parse *path*, raising ``RuntimeError`` so a broken surface never passes silently."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"cannot read declaration surface {path}: {exc}") from exc
    except SyntaxError as exc:
        raise RuntimeError(f"cannot parse declaration surface {path}: {exc}") from exc


def module_assignments(tree: ast.Module) -> dict[str, ast.expr]:
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


def class_members(tree: ast.Module, class_name: str) -> dict[str, str]:
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


def attribute_name(node: ast.expr) -> str | None:
    """Return the attribute of ``LLMIntent.X``, or ``None`` for any other node."""
    return node.attr if isinstance(node, ast.Attribute) else None


def string_value(node: ast.expr | None) -> str | None:
    """Return the value of a string constant, or ``None`` for any other node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def attribute_dict(node: ast.expr | None) -> dict[str, ast.expr]:
    """Return ``{LLMIntent.X: value}`` entries from a dict literal."""
    if not isinstance(node, ast.Dict):
        return {}
    entries: dict[str, ast.expr] = {}
    for key, value in zip(node.keys, node.values, strict=True):
        if key is not None and (intent := attribute_name(key)) is not None:
            entries[intent] = value
    return entries


def string_dict(node: ast.expr | None) -> dict[str, str]:
    """Return ``{LLMIntent.X: "value"}`` entries, dropping non-string values."""
    entries: dict[str, str] = {}
    for intent, value in attribute_dict(node).items():
        text = string_value(value)
        if text is not None:
            entries[intent] = text
    return entries


def _entry_key(node: ast.expr) -> str | None:
    """Return the intent key of ``LLMIntent.X`` or of a string literal."""
    name = attribute_name(node)
    return name if name is not None else string_value(node)


def dict_entries(tree: ast.Module, variable_name: str) -> dict[str, ast.expr]:
    """Return a module-level mapping including writes after its dict literal.

    Starts from the literal bound to *variable_name* (enum-member and string
    keys) and then walks the module body in source order: a single-target
    ``NAME[key] = value`` assignment overwrites the key (last write wins) and
    ``del NAME[key]`` removes it. Keys in any other form are skipped, exactly as
    the literal reader skips them, so the caller's key-set comparison still
    reports the resulting absence.
    """
    entries: dict[str, ast.expr] = {}
    literal = module_assignments(tree).get(variable_name)
    if isinstance(literal, ast.Dict):
        for key, value in zip(literal.keys, literal.values, strict=True):
            name = _entry_key(key) if key is not None else None
            if name is not None:
                entries[name] = value
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Subscript) or not _subscripts(target, variable_name):
                continue
            if (name := _entry_key(target.slice)) is not None:
                entries[name] = node.value
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if not isinstance(target, ast.Subscript) or not _subscripts(target, variable_name):
                    continue
                if (name := _entry_key(target.slice)) is not None:
                    entries.pop(name, None)
    return entries


def _subscripts(node: ast.Subscript, variable_name: str) -> bool:
    """Return whether *node* subscripts the module-level name *variable_name*."""
    return isinstance(node.value, ast.Name) and node.value.id == variable_name


def route_config(node: ast.expr) -> tuple[str | None, str | None]:
    """Extract ``(category, mode)`` from a ``PromptRouteConfig(...)`` call."""
    if not isinstance(node, ast.Call):
        return None, None
    category = string_value(node.args[0]) if node.args else None
    mode = string_value(node.args[1]) if len(node.args) > 1 else None
    for keyword in node.keywords:
        if keyword.arg == "category":
            category = string_value(keyword.value)
        elif keyword.arg == "mode":
            mode = string_value(keyword.value)
    return category, mode


def allowed_context_modes(node: ast.expr) -> tuple[str, ...]:
    """Extract ``allowed_context_modes`` from a ``PromptRouteConfig(...)`` call."""
    if not isinstance(node, ast.Call):
        return ()
    for keyword in node.keywords:
        if keyword.arg != "allowed_context_modes":
            continue
        value = keyword.value
        if isinstance(value, ast.Call) and value.args:
            value = value.args[0]
        if not isinstance(value, ast.Set | ast.Tuple | ast.List):
            return ()
        return tuple(mode for element in value.elts if (mode := string_value(element)) is not None)
    return ()


def load_yaml(path: Path) -> dict[str, object]:
    """Load a governance YAML mapping, raising ``RuntimeError`` rather than passing silently."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"cannot read governance surface {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RuntimeError(f"cannot parse governance surface {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"governance surface {path} is not a YAML mapping")
    # The mapping shape is checked above; ``safe_load`` is untyped, so isinstance
    # narrows only to ``dict[Unknown, Unknown]`` and the cast states the string-key
    # contract the governance files document.
    return cast("dict[str, object]", data)


def mapping_entries(value: object) -> list[dict[str, object]]:
    """Return the dict members of a YAML sequence (other members are ignored)."""
    if not isinstance(value, list):
        return []
    # Same untyped-source boundary as ``load_yaml``: the sequence shape is checked,
    # the element type comes from YAML and is narrowed per member below.
    entries = cast("list[object]", value)
    return [cast("dict[str, object]", item) for item in entries if isinstance(item, dict)]
