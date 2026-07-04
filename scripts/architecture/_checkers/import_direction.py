"""RULE-07 · Dependency direction is one-way. core/ never imports from apps/."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation

# Priority-ordered prefix map: first match wins.
# narrare_core must come before narrare (since ``narrare_core`` starts with ``narrare``).
_PREFIX_MAP: list[tuple[str, str]] = [
    ("narrare_core", "core"),
    ("packages.core", "core"),
    ("apps.api", "api"),
    ("narrare", "api"),
    ("packages.web", "web"),
    ("apps.web", "web"),
]


# Forbidden directions: source_layer -> set of forbidden target_layers
_FORBIDDEN: dict[str, set[str]] = {
    "core": {"api", "web"},
    "api": {"web"},
}


def _get_source_layer(rel_path: str) -> str | None:
    """Determine the architectural layer of the file being checked.

    Returns ``None`` for files that should be skipped (scripts/, tests/, …).
    """
    if rel_path.startswith("packages/core/"):
        return "core"
    if rel_path.startswith("apps/api/"):
        return "api"
    if rel_path.startswith(("apps/web/", "packages/web/")):
        return "web"
    return None


def _get_import_target(module_name: str) -> str | None:
    """Determine which architectural layer an import targets.

    Uses the priority-ordered ``_PREFIX_MAP`` for longest-prefix matching.
    Returns ``None`` for third-party/stdlib imports.
    """
    for prefix, layer in _PREFIX_MAP:
        if module_name == prefix or module_name.startswith(prefix + "."):
            return layer
    return None


def check_import_direction(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """Enforce RULE-07: dependency direction is one-way.

    Forbidden directions::

        core/ → api/  ❌  (core never imports from apps/)
        core/ → web/  ❌
        api/  → web/  ❌

    TYPE_CHECKING blocks and ``# narrare: allow`` inline markers are respected.
    """
    source_layer = _get_source_layer(rel_path)
    if source_layer is None:
        return []  # scripts, tests, and unknown files are unrestricted

    forbidden_targets = _FORBIDDEN.get(source_layer)
    if forbidden_targets is None:
        return []  # no outbound restrictions for this layer

    tc_lines = compute_type_checking_lines(tree)
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if node.lineno in tc_lines:
            continue  # skip TYPE_CHECKING-only imports

        # Collect module names from both import forms
        if isinstance(node, ast.Import):
            module_names = [alias.name for alias in node.names]
        else:
            module_names = [node.module or ""]

        for module_name in module_names:
            target_layer = _get_import_target(module_name)
            if target_layer is None:
                continue
            if target_layer not in forbidden_targets:
                continue

            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-07",
                    detail=(
                        f"Import direction violation: '{rel_path}' ({source_layer}) "
                        f"imports from '{module_name}' ({target_layer}) — "
                        f"{source_layer}/ must not import from {target_layer}/"
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )

    return violations
