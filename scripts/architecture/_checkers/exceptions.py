"""RULE-11 · No silent failures."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.types import Violation


def check_bare_except(rel_path: str, tree: ast.AST) -> list[Violation]:
    """No bare except: or except Exception: pass."""
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-11",
                    detail="Bare 'except:' clause — must catch specific exception type",
                )
            )
            continue
        if (
            isinstance(node.type, ast.Name)
            and node.type.id == "Exception"
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
        ):
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-11",
                    detail="'except Exception: pass' silently swallows all errors",
                )
            )
    return violations
