"""Narrare Architecture Constraint Checker — rule checkers."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from scripts.architecture.agent_checks import (
    check_agent_imports,
    check_agent_instantiation,
)
from scripts.architecture.helpers import is_approved_exception, relative_to_root
from scripts.architecture.types import CheckResult, Violation

# =====================================================================
# RULE-01 · LLM calls go through the Gateway
# =====================================================================


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

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
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
) -> list[Violation]:
    """No direct HTTP calls to LLM provider endpoints."""
    if any(rel_path.startswith(m.rstrip("/")) for m in allowed_modules):
        return []

    violations: list[Violation] = []
    for i, line in enumerate(source_lines, 1):
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


# =====================================================================
# RULE-02 · Prompts built in core/prompts/ only
# =====================================================================


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


# =====================================================================
# RULE-04 · File size limits
# =====================================================================


def check_file_size(
    rel_path: str,
    source_lines: list[str],
    limits: dict[str, int],
) -> list[Violation]:
    """Hard file size limits by file type."""
    line_count = len(source_lines)
    file_name = Path(rel_path).name

    limit = limits.get("default", 400)
    if file_name.startswith("router"):
        limit = limits.get("router", 150)
    elif file_name.endswith("_service.py") or file_name == "service.py":
        limit = limits.get("service", 300)
    elif file_name.endswith("_repo.py") or file_name == "repository.py":
        limit = limits.get("repository", 250)
    elif file_name == "contracts.py":
        limit = limits.get("contracts", 200)
    elif file_name == "models.py":
        limit = limits.get("models", 200)
    elif file_name.endswith("_schemas.py") or file_name == "schemas.py":
        limit = limits.get("schemas", 200)
    elif file_name.endswith("_agent.py") or file_name == "agent.py":
        limit = limits.get("agent", 200)
    elif file_name == "gateway.py":
        limit = limits.get("gateway", 300)
    elif file_name == "composer.py":
        limit = limits.get("composer", 250)

    if line_count > limit:
        return [
            Violation(
                file=Path(rel_path),
                line=line_count,
                rule="RULE-04",
                detail=f"File has {line_count} lines (hard limit: {limit}). Split required.",
            )
        ]
    return []


# =====================================================================
# RULE-11 · No silent failures
# =====================================================================


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


# =====================================================================
# RULE-TEST-01 · No bare MagicMock() in tests
# =====================================================================


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
        + check_llm_urls(rel_path, source_lines, allowed_llm, forbidden_urls)
        + check_agent_imports(rel_path, tree, source_lines, allowed_agents)
        + check_agent_instantiation(rel_path, tree, source_lines, allowed_agents)
        + check_prompt_building(rel_path, tree, source_lines, allowed_prompts)
        + check_bare_except(rel_path, tree)
        + check_file_size(rel_path, source_lines, size_limits)
        + check_bare_magic_mock(rel_path, tree, source_lines)
    )

    for v in all_violations:
        if v.approved:
            result.approved_exceptions.append(v)
        else:
            result.violations.append(v)
