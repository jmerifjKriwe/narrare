"""RULE-19 · Bare AsyncSession in dependency factories."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import is_approved_exception
from scripts.architecture.types import Violation


def check_bare_async_session(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """No bare AsyncSession parameter in dependency factory functions.

    RULE-19: In ``dependencies.py`` files under ``apps/api/``, function
    parameters must use ``SessionDep`` (an ``Annotated`` alias that
    includes ``Depends()``), not bare ``AsyncSession``.  FastAPI treats
    a bare ``AsyncSession`` annotation as a query parameter, causing
    422 errors in production.

    Valid annotations:
    - ``session: SessionDep``
    - ``session: Annotated[AsyncSession, Depends(get_async_session)]``

    Invalid (violation):
    - ``session: AsyncSession``
    """
    file_path = Path(rel_path)
    if file_path.name != "dependencies.py":
        return []
    if not rel_path.startswith("apps/api/"):
        return []

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        # Check both positional and keyword-only parameters
        for arg in (*node.args.args, *node.args.kwonlyargs):
            annotation = arg.annotation
            if annotation is None:
                continue
            # Bare AsyncSession:  session: AsyncSession
            # → ast.Name(id='AsyncSession')
            if isinstance(annotation, ast.Name) and annotation.id == "AsyncSession":
                approved, reason = is_approved_exception(source_lines, node.lineno)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule="RULE-19",
                        detail=(
                            "Bare AsyncSession parameter in dependency factory "
                            "— use SessionDep instead"
                        ),
                        approved=approved,
                        approval_reason=reason,
                    )
                )
            # ast.Subscript (e.g. Annotated[AsyncSession, Depends(...)]) is fine
            # ast.Name(id='SessionDep') is fine
    return violations
