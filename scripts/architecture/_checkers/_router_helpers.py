"""Shared helpers for router-level architecture checks.

Provides router file identification and route handler name extraction
from AST trees.  Used by ``router_queries.py`` and potentially other
router-focused checkers.
"""

from __future__ import annotations

import ast
from pathlib import Path


def is_router_file(rel_path: str) -> bool:
    """Check if the file is a router under ``apps/api/narrare/``."""
    if not rel_path.startswith("apps/api/narrare/"):
        return False
    name = Path(rel_path).name
    return name == "router.py" or name.startswith("router_")


def get_route_handler_names(tree: ast.AST) -> set[str]:
    """Return names of functions decorated with ``@router.*`` decorators."""
    handlers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.decorator_list:
            continue
        for deco in node.decorator_list:
            func = deco.func if isinstance(deco, ast.Call) else deco
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "router"
            ):
                handlers.add(node.name)
    return handlers
