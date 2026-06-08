"""RULE-18 · Configurable defaults — no hardcoded constants.

Detects numeric constants and timeouts that should live in
configuration rather than source code.

Patterns checked:

1. Module-/class-level integer/float constants > max_allowed
2. Hardcoded ``timeout=`` keyword arguments in function calls
4. Percentage dicts without ``ClassVar`` annotation

Pattern 3 (init defaults) was intentionally excluded from the
design — constructor defaults are configuration points and must
not be flagged.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation

# Values considered "trivial" — never flagged regardless of threshold.
_TRIVIAL_VALUES: frozenset[float] = frozenset({0.0, 0.5, 1.0, 2.0})


# ---------------------------------------------------------------------------
# Parent-map helpers (built once per file, reused by patterns)
# ---------------------------------------------------------------------------


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Build a child → parent mapping for the entire AST."""
    parent_map: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


def _is_inside_function(
    node: ast.AST,
    parent_map: dict[ast.AST, ast.AST],
) -> bool:
    """True when *node* sits inside a ``FunctionDef`` or ``AsyncFunctionDef``."""
    current: ast.AST | None = node
    while current in parent_map:
        parent = parent_map[current]
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
        current = parent
    return False


def _get_enclosing_class(
    node: ast.AST,
    parent_map: dict[ast.AST, ast.AST],
) -> ast.ClassDef | None:
    """Return the nearest enclosing ``ClassDef``, or ``None``."""
    current: ast.AST | None = node
    while current in parent_map:
        parent = parent_map[current]
        if isinstance(parent, ast.ClassDef):
            return parent
        current = parent
    return None


# ---------------------------------------------------------------------------
# Public helper functions (required by design spec)
# ---------------------------------------------------------------------------


def _is_trivial_constant(val: object) -> bool:
    """True for 0.0, 0.5, 1.0, 2.0, or any value with ``|value| < 0.5``."""
    if isinstance(val, (int, float)):
        fval = float(val)
        return fval in _TRIVIAL_VALUES or abs(fval) < 0.5
    return False


def _is_config_class(class_node: ast.ClassDef) -> bool:
    """True when the class name contains Config, Settings, Limits, or Profile."""
    keywords = ("Config", "Settings", "Limits", "Profile")
    return any(kw in class_node.name for kw in keywords)


def _has_percentage_values(dict_node: ast.Dict) -> bool:
    """True when the ``Dict`` has at least one ``float`` value in the 0.0-1.0 range."""
    for val in dict_node.values:
        if (
            isinstance(val, ast.Constant)
            and isinstance(val.value, float)
            and 0.0 <= val.value <= 1.0
        ):
            return True
    return False


def _is_classvar_assignment(node: ast.AST, tree: ast.AST) -> bool:
    """Check if the assignment carries a ``ClassVar`` annotation.

    Only ``ast.AnnAssign`` nodes can carry annotations.
    Plain ``ast.Assign`` nodes never have ``ClassVar``.
    """
    if not isinstance(node, ast.AnnAssign):
        return False
    ann = node.annotation
    # ``ClassVar`` or ``typing.ClassVar``
    if isinstance(ann, ast.Name) and ann.id == "ClassVar":
        return True
    if isinstance(ann, ast.Attribute) and ann.attr == "ClassVar":
        return True
    # ``ClassVar[...]`` or ``typing.ClassVar[...]``
    if isinstance(ann, ast.Subscript):
        inner = ann.value
        if isinstance(inner, ast.Name) and inner.id == "ClassVar":
            return True
        if isinstance(inner, ast.Attribute) and inner.attr == "ClassVar":
            return True
    return False


def _matches_allowed_pattern(name: str, patterns: list[str]) -> bool:
    """True when *name* contains any of the allowed pattern substrings."""
    return any(p in name for p in patterns)


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check_hardcoded_constants(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    config: dict[str, object],
) -> list[Violation]:
    """Detect hardcoded numeric constants that should be configurable.

    Returns a list of :class:`Violation` instances for every detected
    hard-coded value.  Approved inline exceptions (``# narrare: allow``)
    are marked with ``approved=True``.
    """
    # --- Fast-path: skip test & conftest files ---
    basename = Path(rel_path).name
    if basename.startswith("test_") or basename.startswith("conftest"):
        return []

    # --- Skip ignored modules ---
    raw_ignored = config.get("ignored_modules", [])
    if isinstance(raw_ignored, list) and rel_path in raw_ignored:
        return []

    # --- Parse configuration ---
    raw_max = config.get("max_allowed_constant", 5)
    max_allowed: float = float(raw_max) if isinstance(raw_max, (int, float)) else 5.0

    raw_patterns = config.get("allowed_patterns", [])
    allowed_patterns: list[str] = []
    if isinstance(raw_patterns, list):
        for item in raw_patterns:  # pyright: ignore[reportUnknownVariableType]
            if isinstance(item, str):
                allowed_patterns.append(item)

    tc_lines = compute_type_checking_lines(tree)
    parent_map = _build_parent_map(tree)
    violations: list[Violation] = []

    # =============================================================
    # Pattern 1: Module-/class-level integer/float constants
    # =============================================================
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        # Only module-level or class-level (skip function bodies)
        if _is_inside_function(node, parent_map):
            continue
        if node.lineno in tc_lines:
            continue

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            value_node = node.value

            # Must be a numeric literal
            if not isinstance(value_node, ast.Constant):
                continue
            if not isinstance(value_node.value, (int, float)):
                continue

            val = float(value_node.value)

            # --- Exceptions ---
            if _is_trivial_constant(val):
                continue
            if _matches_allowed_pattern(name, allowed_patterns):
                continue
            enclosing = _get_enclosing_class(node, parent_map)
            if enclosing is not None and _is_config_class(enclosing):
                continue

            # Flag only when strictly above threshold
            if val <= max_allowed:
                continue

            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-18",
                    detail=(
                        f"Module-level constant '{name}' = {value_node.value} "
                        f"is a hardcoded value (>{max_allowed:.0f}) "
                        f"— move to configuration"
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )

    # =============================================================
    # Pattern 2: Hardcoded timeouts in function calls
    # =============================================================
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if node.lineno in tc_lines:
            continue

        for kw in node.keywords:
            if kw.arg != "timeout":
                continue
            # Only flag literal constants — variable refs are fine
            if not isinstance(kw.value, ast.Constant):
                continue
            val = kw.value.value
            if not isinstance(val, (int, float)):
                continue
            if float(val) <= max_allowed:
                continue

            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-18",
                    detail=(
                        f"Hardcoded timeout={val} in function call "
                        f"(>{max_allowed:.0f}) — use configurable timeout"
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )

    # =============================================================
    # Pattern 4: Percentage dicts without ClassVar
    # =============================================================
    for node in ast.walk(tree):
        dict_node: ast.Dict | None = None
        target_name = ""

        if isinstance(node, ast.Assign):
            if not isinstance(node.value, ast.Dict):
                continue
            dict_node = node.value
            for t in node.targets:
                if isinstance(t, ast.Name):
                    target_name = t.id
                    break
        elif isinstance(node, ast.AnnAssign):
            # AnnAssign with ClassVar → exempt
            if _is_classvar_assignment(node, tree):
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            dict_node = node.value
            if isinstance(node.target, ast.Name):
                target_name = node.target.id
        else:
            continue

        assert dict_node is not None  # guaranteed by checks above

        if not _has_percentage_values(dict_node):
            continue
        if node.lineno in tc_lines:
            continue
        if target_name and _matches_allowed_pattern(target_name, allowed_patterns):
            continue

        approved, reason = is_approved_exception(source_lines, node.lineno)
        violations.append(
            Violation(
                file=Path(rel_path),
                line=node.lineno,
                rule="RULE-18",
                detail=(
                    f"Percentage dict '{target_name}' without ClassVar annotation "
                    f"— use ClassVar for typed constant dicts"
                ),
                approved=approved,
                approval_reason=reason,
            )
        )

    return violations
