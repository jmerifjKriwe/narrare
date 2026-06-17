"""RULE-02 · Prompts built in core/prompts/ only.

RULE-02b (ADR-046 D.2 Module 2): also detects app-layer prompt loaders — modules
under ``apps/`` that load template files from ``_bundled/`` and perform manual
``{{variable}}`` substitution, reimplementing the PromptComposer cascade in the
wrong architectural layer.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation


def check_prompt_building(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    prompt_allowed: list[str],
) -> list[Violation]:
    """No f-string prompt assembly outside core/prompts/."""
    if any(rel_path.startswith(m.rstrip("/")) for m in prompt_allowed):
        return []

    prompt_var_names = {
        "system_prompt",
        "user_prompt",
        "prompt",
        "system_message",
        "user_message",
    }

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id.lower() not in prompt_var_names:
                continue
            if isinstance(node.value, ast.JoinedStr):  # f-string
                approved, reason = is_approved_exception(source_lines, node.lineno)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule="RULE-02",
                        detail=f"f-string prompt assembly in '{target.id}' outside core/prompts/",
                        approved=approved,
                        approval_reason=reason,
                    )
                )
    return violations


# ── RULE-02b (ADR-046 D.2 Module 2): app-layer prompt loaders ──────

_RULE_02B = "RULE-02b"


def _imports_importlib_resources(tree: ast.AST) -> bool:
    """Return True if the file imports ``importlib.resources`` (or ``importlib``)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "importlib.resources" or module.startswith("importlib.resources"):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    return True
    return False


def _has_bundled_string_literal(tree: ast.AST) -> bool:
    """Return True if any string literal references a ``_bundled`` path."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "_bundled" in node.value
        ):
            return True
    return False


def _manual_substitution_replaces(tree: ast.AST) -> list[ast.Call]:
    """Return ``.replace("{{...")`` calls (manual template-variable substitution)."""
    hits: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "replace":
            continue
        if not node.args:
            continue
        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
            and first.value.startswith("{{")
        ):
            hits.append(node)
    return hits


def check_app_layer_prompt_loader(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """RULE-02b: no app-layer prompt loaders (ADR-046 D.2 Module 2).

    Only applies to files under ``apps/``. Flags:

    1. ``importlib.resources`` import **combined with** a ``_bundled`` string
       literal — an app-layer module loading bundled prompt templates directly.
    2. ``.replace("{{...")`` calls — manual ``{{variable}}`` template substitution
       that reimplements the governed variable engine outside ``core/prompts/``.
    3. Filenames matching ``*_prompt_loader.py`` or ``_prompt_*.py`` — the
       loader naming pattern from the CR-02 audit (CR-AUFG-02-06).

    Prompt loading and ``{{variable}}`` substitution are exclusively
    ``core/prompts/`` responsibilities (RULE-02b violation 2).
    """
    if not rel_path.startswith("apps/"):
        return []

    tc_lines = compute_type_checking_lines(tree)
    violations: list[Violation] = []
    emitted_lines: set[int] = set()

    def _emit(line: int, detail: str) -> None:
        if line in emitted_lines:
            return
        emitted_lines.add(line)
        approved, reason = is_approved_exception(source_lines, line)
        violations.append(
            Violation(
                file=Path(rel_path),
                line=line,
                rule=_RULE_02B,
                detail=detail,
                approved=approved,
                approval_reason=reason,
            )
        )

    # --- Check 1: importlib.resources + _bundled reference ---
    # An app-layer file that imports importlib.resources AND references a
    # "_bundled" path is loading bundled prompt templates directly (CR-AUFG-02-06).
    if _imports_importlib_resources(tree) and _has_bundled_string_literal(tree):
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if node.lineno in tc_lines:
                continue
            is_importlib_import = isinstance(node, ast.Import) and any(
                a.name == "importlib" or a.name.startswith("importlib.") for a in node.names
            )
            is_importlib_from = isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "importlib.resources"
            )
            if is_importlib_import or is_importlib_from:
                _emit(
                    node.lineno,
                    "App-layer prompt loader: importlib.resources + "
                    "'_bundled' reference — prompt loading is "
                    "core/prompts/ responsibility",
                )
                break

    # --- Check 2: manual {{variable}} substitution via .replace() ---
    for call in _manual_substitution_replaces(tree):
        if call.lineno in tc_lines:
            continue
        _emit(
            call.lineno,
            'App-layer manual template substitution (.replace("{{...")) — '
            "use PromptComposer/PromptContext variable engine instead",
        )

    # --- Check 3: loader filename pattern ---
    basename = rel_path.rsplit("/", 1)[-1]
    if basename.endswith("_prompt_loader.py") or basename.startswith("_prompt_"):
        # Report at module level (line 1).
        _emit(
            1,
            f"App-layer prompt-loader filename '{basename}' — prompt loading "
            "belongs in core/prompts/",
        )

    return violations
