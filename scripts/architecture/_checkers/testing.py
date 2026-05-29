"""RULE-TEST-01 · No bare MagicMock() in tests."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import is_approved_exception
from scripts.architecture.types import Violation


def check_bare_magic_mock(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """No bare MagicMock() without spec= in test files."""
    if not rel_path.startswith("tests/") or "tests/fakes/" in rel_path:
        return []

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "MagicMock":
            has_spec = any(kw.arg == "spec" for kw in node.keywords)
            if not has_spec:
                approved, reason = is_approved_exception(source_lines, node.lineno)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule="RULE-TEST-01",
                        detail=(
                            "Bare MagicMock() without spec= — use Fake class or MagicMock(spec=...)"
                        ),
                        approved=approved,
                        approval_reason=reason,
                    )
                )
    return violations
