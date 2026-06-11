"""RULE-19 extension · No direct SQLAlchemy queries in router files.

Routers must delegate immediately to services/repositories.  Direct
``session.execute()``, ``session.scalars()``, ``session.scalar()`` calls,
bare ``select()`` / ``insert()`` / ``update()`` / ``delete()`` usage, or
``func.*()`` calls in route handler functions indicate a layer violation.

Allowed (no violation):
  - Imports inside ``if TYPE_CHECKING:`` blocks
  - Dependency factory functions (``_get_*`` pattern) — they wire DI,
    they don't execute queries.

Forbidden (violation):
  - ``session.execute/scalars/scalar(...)`` calls in route handlers
  - ``select/insert/update/delete(...)`` (SQLAlchemy constructors) in handlers
  - ``func.count/func.max/...()`` (SQLAlchemy function) calls in handlers
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture._checkers._router_helpers import (
    get_route_handler_names,
    is_router_file,
)
from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation

_SESSION_QUERY_METHODS = frozenset({"execute", "scalars", "scalar"})
_QUERY_CONSTRUCTORS = frozenset({"select", "insert", "update", "delete"})
_SQLA_FUNC_OBJECT_NAME = "func"


def _check_call(
    call: ast.Call,
    rel_path: str,
    source_lines: list[str],
) -> Violation | None:
    """Check a single ``ast.Call`` node for forbidden SQLAlchemy patterns."""
    func = call.func

    # Pattern 1: session.execute/scalars/scalar(...)
    if isinstance(func, ast.Attribute) and func.attr in _SESSION_QUERY_METHODS:
        approved, reason = is_approved_exception(source_lines, call.lineno)
        obj = func.value.id if isinstance(func.value, ast.Name) else "<expr>"
        return Violation(
            file=Path(rel_path),
            line=call.lineno,
            rule="RULE-19",
            detail=(
                f"Direct SQLAlchemy query in router — "
                f"{obj}.{func.attr}(). "
                f"Move queries to Repository classes."
            ),
            approved=approved,
            approval_reason=reason,
        )

    # Pattern 2: select/insert/update/delete() constructors
    if isinstance(func, ast.Name) and func.id in _QUERY_CONSTRUCTORS:
        approved, reason = is_approved_exception(source_lines, call.lineno)
        return Violation(
            file=Path(rel_path),
            line=call.lineno,
            rule="RULE-19",
            detail=(
                f"SQLAlchemy query constructor '{func.id}()' "
                f"in router. Query construction belongs in "
                f"Repository classes."
            ),
            approved=approved,
            approval_reason=reason,
        )

    # Pattern 3: func.count/func.max/...() — SQLAlchemy function calls
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == _SQLA_FUNC_OBJECT_NAME
    ):
        approved, reason = is_approved_exception(source_lines, call.lineno)
        return Violation(
            file=Path(rel_path),
            line=call.lineno,
            rule="RULE-19",
            detail=(
                f"SQLAlchemy function call 'func.{func.attr}()' "
                f"in router. Query functions belong in "
                f"Repository classes."
            ),
            approved=approved,
            approval_reason=reason,
        )

    return None


def check_router_queries(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """Detect direct SQLAlchemy queries in router files.

    Only scans route handler functions (``@router.get``, ``@router.post`` etc.).
    Skips dependency factories (``_get_*``), TYPE_CHECKING blocks, and
    module-level code.
    """
    if not is_router_file(rel_path):
        return []

    tc_lines = compute_type_checking_lines(tree)
    handler_names = get_route_handler_names(tree)
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        if node.name not in handler_names:
            continue

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if child.lineno in tc_lines:
                continue
            v = _check_call(child, rel_path, source_lines)
            if v is not None:
                violations.append(v)

    return violations
