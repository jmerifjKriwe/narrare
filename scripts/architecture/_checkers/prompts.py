"""RULE-02 · Prompts built in core/prompts/ only."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import is_approved_exception
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
