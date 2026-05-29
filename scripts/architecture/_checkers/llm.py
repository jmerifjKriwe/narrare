"""RULE-01 · LLM calls go through the Gateway."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation


def check_llm_imports(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    allowed_modules: list[str],
    forbidden_imports: list[str],
) -> list[Violation]:
    """No direct LLM imports outside allowed modules."""
    if any(rel_path.startswith(m.rstrip("/")) for m in allowed_modules):
        return []

    tc_lines = compute_type_checking_lines(tree)
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            if node.lineno in tc_lines:
                continue
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                root_module = name.split(".")[0]
                if root_module in forbidden_imports:
                    approved, reason = is_approved_exception(source_lines, node.lineno)
                    violations.append(
                        Violation(
                            file=Path(rel_path),
                            line=node.lineno,
                            rule="RULE-01",
                            detail=f"Direct LLM import '{name}' outside gateway",
                            approved=approved,
                            approval_reason=reason,
                        )
                    )
    return violations


def check_llm_urls(
    rel_path: str,
    source_lines: list[str],
    allowed_modules: list[str],
    forbidden_urls: list[str],
    tree: ast.AST | None = None,
) -> list[Violation]:
    """No direct HTTP calls to LLM provider endpoints."""
    if any(rel_path.startswith(m.rstrip("/")) for m in allowed_modules):
        return []

    tc_lines: set[int] = set()
    if tree is not None:
        tc_lines = compute_type_checking_lines(tree)

    violations: list[Violation] = []
    for i, line in enumerate(source_lines, 1):
        if i in tc_lines:
            continue
        for url in forbidden_urls:
            if url in line:
                approved, reason = is_approved_exception(source_lines, i)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=i,
                        rule="RULE-01",
                        detail=f"Direct HTTP call to LLM endpoint '{url}'",
                        approved=approved,
                        approval_reason=reason,
                    )
                )
    return violations
