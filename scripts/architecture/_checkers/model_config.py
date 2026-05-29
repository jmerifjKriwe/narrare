"""RULE-18 · No hardcoded model configuration in routers / dependencies."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation


def check_hardcoded_model_config(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """No hardcoded ``provider_name`` in ``ResolvedModelConfig()`` calls.

    RULE-18: In ``*.py`` files under ``apps/api/``, calls to
    ``ResolvedModelConfig(provider_name=<string_literal>)`` are flagged
    because the provider should always be resolved at runtime via the
    settings cascade (``ModelRoutingResolver``), never baked into the
    source code.

    Flagged values include ``"default"`` (the placeholder that caused
    the original bug) and any known provider name from the registry
    (``"anthropic"``, ``"openai"``, …).  In practice *every* string
    literal is flagged — the provider must come from configuration, not
    from source.

    Variable references (``provider_name=settings.provider``) are
    allowed.  Calls inside ``if TYPE_CHECKING:`` blocks are skipped.
    """
    if not rel_path.startswith("apps/api/"):
        return []

    tc_lines = compute_type_checking_lines(tree)

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if node.lineno in tc_lines:
            continue

        # Match ResolvedModelConfig(...) — direct name reference.
        if not (isinstance(node.func, ast.Name) and node.func.id == "ResolvedModelConfig"):
            continue

        for kw in node.keywords:
            if kw.arg != "provider_name":
                continue
            # Only flag string-literal values.  Variable references are fine.
            if not isinstance(kw.value, ast.Constant):
                continue
            if not isinstance(kw.value.value, str):
                continue

            value = kw.value.value
            approved, reason = is_approved_exception(source_lines, node.lineno)
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-18",
                    detail=(
                        f"Hardcoded provider_name='{value}' in "
                        f"ResolvedModelConfig — must come from settings cascade"
                    ),
                    approved=approved,
                    approval_reason=reason,
                )
            )

    return violations
