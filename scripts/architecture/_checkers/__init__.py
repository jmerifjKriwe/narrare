"""Narrare Architecture Constraint Checker — checker subpackage.

Each module in this package contains focused rule checkers.
``scan_file`` orchestrates all checkers for a single file.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from scripts.architecture._checkers.exceptions import check_bare_except
from scripts.architecture._checkers.file_size import check_file_size
from scripts.architecture._checkers.inline_prompts import check_inline_prompts
from scripts.architecture._checkers.llm import check_llm_imports, check_llm_urls
from scripts.architecture._checkers.model_config import check_hardcoded_model_config
from scripts.architecture._checkers.prompts import check_prompt_building
from scripts.architecture._checkers.sessions import check_bare_async_session
from scripts.architecture._checkers.testing import check_bare_magic_mock
from scripts.architecture.agent_checks import (
    check_agent_imports,
    check_agent_instantiation,
)
from scripts.architecture.helpers import relative_to_root
from scripts.architecture.types import CheckResult, Violation

__all__ = [
    "check_bare_async_session",
    "check_bare_except",
    "check_bare_magic_mock",
    "check_file_size",
    "check_hardcoded_model_config",
    "check_inline_prompts",
    "check_llm_imports",
    "check_llm_urls",
    "check_prompt_building",
    "scan_file",
]


# =====================================================================
# Scanner — orchestrates all checks on a single file
# =====================================================================


def scan_file(
    py_file: Path,
    config: dict[str, Any],
    result: CheckResult,
) -> None:
    """Run all rule checks on a single Python file."""
    rel_path = relative_to_root(py_file)

    if any(part in rel_path for part in [".venv", "migrations", "node_modules"]):
        return

    try:
        source = py_file.read_text(encoding="utf-8")
    except OSError:
        return

    source_lines = source.splitlines()
    result.files_checked += 1

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as e:
        result.violations.append(
            Violation(
                file=py_file, line=e.lineno or 0, rule="SYNTAX", detail=f"Syntax error: {e.msg}"
            )
        )
        return

    allowed_llm: list[str] = config.get("llm_allowed_modules", []) or []
    allowed_prompts: list[str] = config.get("prompt_allowed_modules", []) or []
    allowed_agents: list[str] = config.get("agent_allowed_modules", []) or []
    forbidden_imports: list[str] = config.get("forbidden_llm_imports", []) or []
    forbidden_urls: list[str] = config.get("forbidden_llm_urls", []) or []
    size_limits: dict[str, int] = config.get("file_size_limits", {}) or {}

    all_violations = (
        check_llm_imports(rel_path, tree, source_lines, allowed_llm, forbidden_imports)
        + check_llm_urls(rel_path, source_lines, allowed_llm, forbidden_urls, tree)
        + check_agent_imports(rel_path, tree, source_lines, allowed_agents)
        + check_agent_instantiation(rel_path, tree, source_lines, allowed_agents)
        + check_prompt_building(rel_path, tree, source_lines, allowed_prompts)
        + check_inline_prompts(rel_path, tree, source_lines)
        + check_bare_except(rel_path, tree)
        + check_file_size(rel_path, source_lines, size_limits)
        + check_bare_magic_mock(rel_path, tree, source_lines)
        + check_bare_async_session(rel_path, tree, source_lines)
        + check_hardcoded_model_config(rel_path, tree, source_lines)
    )

    for v in all_violations:
        if v.approved:
            result.approved_exceptions.append(v)
        else:
            result.violations.append(v)
