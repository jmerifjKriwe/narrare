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
from scripts.architecture._checkers.hardcoded_values import check_hardcoded_constants
from scripts.architecture._checkers.inline_prompts import check_inline_prompts
from scripts.architecture._checkers.llm import check_llm_imports, check_llm_urls
from scripts.architecture._checkers.model_config import check_hardcoded_model_config
from scripts.architecture._checkers.prompts import check_prompt_building
from scripts.architecture._checkers.router_queries import check_router_queries
from scripts.architecture._checkers.sessions import check_bare_async_session
from scripts.architecture._checkers.testing import check_bare_magic_mock
from scripts.architecture.agent_checks import (
    check_agent_imports,
    check_agent_instantiation,
)
from scripts.architecture.helpers import relative_to_root
from scripts.architecture.types import CheckResult, Violation

# Track which inline-approvals we've already validated against pyproject.toml
# (avoids duplicate violations when _validate_exception_consistency is called
#  once per file from scan_file).
_validated_keys: set[tuple[str, str]] = set()

__all__ = [
    "check_bare_async_session",
    "check_bare_except",
    "check_bare_magic_mock",
    "check_file_size",
    "check_hardcoded_constants",
    "check_hardcoded_model_config",
    "check_inline_prompts",
    "check_llm_imports",
    "check_llm_urls",
    "check_prompt_building",
    "check_router_queries",
    "scan_file",
]


# =====================================================================
# Exception consistency — validate inline markers vs pyproject.toml
# =====================================================================


def _validate_exception_consistency(
    result: CheckResult,
    config: dict[str, Any],
    start_index: int = 0,
) -> None:
    """Validate that all approved exceptions are registered in pyproject.toml.

    ADR-028: pyproject.toml is the SSOT for architecture exceptions.
    Every inline ``# narrare: allow`` marker must have a corresponding entry
    in ``[tool.narrare.architecture.exceptions]``.

    Only checks exceptions from *start_index* onward so callers can
    incrementally validate newly-added approvals without re-scanning.
    """
    exceptions_config: dict[str, Any] = config.get("exceptions", {}) or {}  # type: ignore[no-redef]
    raw_entries: list[dict[str, Any]] = exceptions_config.get("entries", []) or []

    # Build a set of (rule, filepath) from pyproject.toml
    registered: set[tuple[str, str]] = set()
    for entry in raw_entries:
        rule: str = entry.get("rule", "")
        filepath: str = entry.get("file", "")
        registered.add((rule, filepath))

    # Check every approved inline exception against the register
    for exc in result.approved_exceptions[start_index:]:
        key = (exc.rule, relative_to_root(exc.file))
        if key not in registered and key not in _validated_keys:
            _validated_keys.add(key)
            result.violations.append(
                Violation(
                    file=exc.file,
                    line=exc.line,
                    rule=exc.rule,
                    detail=(
                        f"Inline # narrare: allow marker found for {exc.rule} "
                        f"but no matching entry in pyproject.toml "
                        f"[tool.narrare.architecture.exceptions]. "
                        f"See ADR-028."
                    ),
                )
            )


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
    hardcoded_config: dict[str, Any] = config.get("configurable_defaults", {}) or {}

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
        + check_router_queries(rel_path, tree, source_lines)
        + check_hardcoded_model_config(rel_path, tree, source_lines)
        + check_hardcoded_constants(rel_path, tree, source_lines, hardcoded_config)
    )

    approved_before = len(result.approved_exceptions)

    for v in all_violations:
        if v.approved:
            result.approved_exceptions.append(v)
        else:
            result.violations.append(v)

    # Validate inline markers against pyproject.toml (ADR-028)
    _validate_exception_consistency(result, config, start_index=approved_before)
