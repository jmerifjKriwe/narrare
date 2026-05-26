"""RULE-01b Agent constraint checkers — Agent imports and instantiation.

These checks enforce that pydantic_ai.Agent may only be imported and
instantiated in ``core/agents/``, with approved exceptions via
``# narrare: allow-agent`` comments.

See CONSTRAINTS.md RULE-01b and ADR-015.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import compute_type_checking_lines, is_approved_exception
from scripts.architecture.types import Violation


def _has_narrare_agent_imports(tree: ast.AST) -> bool:
    """Check if the file imports any class from narrare_core.agents.*."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module and node.module.startswith("narrare_core.agents."):
            return True
    return False


# =====================================================================
# RULE-01b · Agent import check — only in core/agents/
# =====================================================================


def check_agent_imports(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    agent_allowed_modules: list[str],
) -> list[Violation]:
    """No 'from pydantic_ai import Agent' outside core/agents/.

    Rule RULE-01b: pydantic_ai.Agent may only be imported in core/agents/.
    Exceptions with '# narrare: allow-agent reason="..."' are permitted
    (e.g. core/llm/gateway.py, setup/provider_service.py).
    """
    if any(rel_path.startswith(m.rstrip("/")) for m in agent_allowed_modules):
        return []

    tc_lines = compute_type_checking_lines(tree)
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.lineno in tc_lines:
            continue
        if node.module and node.module.startswith("pydantic_ai"):
            for alias in node.names:
                if alias.name == "Agent":
                    approved, reason = is_approved_exception(source_lines, node.lineno)
                    violations.append(
                        Violation(
                            file=Path(rel_path),
                            line=node.lineno,
                            rule="RULE-01b",
                            detail=(
                                "'from pydantic_ai import Agent' outside "
                                "core/agents/. Add '# narrare: allow-agent' "
                                "with reason if this is an approved exception."
                            ),
                            approved=approved,
                            approval_reason=reason,
                        )
                    )
    return violations


# =====================================================================
# RULE-01b · Agent instantiation check — Agent() / .run() / .run_sync()
# =====================================================================


def check_agent_instantiation(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    agent_allowed_modules: list[str],
) -> list[Violation]:
    """No Agent(...) constructor calls or .run()/.run_sync() outside core/agents/.

    Rule RULE-01b: Agent objects must be created and run in core/agents/.
    Exceptions with '# narrare: allow-agent reason="..."' are permitted.
    """
    if any(rel_path.startswith(m.rstrip("/")) for m in agent_allowed_modules):
        return []

    has_narrare_imports = _has_narrare_agent_imports(tree)
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Agent(...) constructor — direct call to class named "Agent"
        if isinstance(node.func, ast.Name) and node.func.id == "Agent":
            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-01b",
                    detail=(
                        "Agent(...) instantiation outside core/agents/. "
                        "Add '# narrare: allow-agent' with reason "
                        "if this is an approved exception."
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )
            continue

        # .run() on variables whose name contains "agent"
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and "agent" in node.func.value.id.lower()
            and not has_narrare_imports
        ):
            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-01b",
                    detail=(
                        "Agent .run() call outside core/agents/. "
                        "Add '# narrare: allow-agent' with reason "
                        "if this is an approved exception."
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )
            continue

        # .run_sync() on variables whose name contains "agent"
        # (pydantic-ai Agent method — not e.g. connection.run_sync)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "run_sync"
            and isinstance(node.func.value, ast.Name)
            and "agent" in node.func.value.id.lower()
            and not has_narrare_imports
        ):
            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-01b",
                    detail=(
                        "Agent .run_sync() call outside core/agents/. "
                        "Add '# narrare: allow-agent' with reason "
                        "if this is an approved exception."
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )

    return violations
