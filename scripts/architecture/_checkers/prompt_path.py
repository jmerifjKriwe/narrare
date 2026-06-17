"""RULE-02b · No direct PromptRegistry access outside core/prompts/.

Detects prompt-resolution-path violations (ADR-046 Component 1 / D.2 Module 1):

1. **Direct ``.resolve()`` on a registry receiver** — the actual resolution act.
   Any ``<registry>.resolve(...)`` call outside ``core/prompts/`` bypasses the
   PromptComposer cascade (and thus variable substitution, user overrides, and
   capability injection). This is the primary drift signal (CR-AUFG-02-05).

2. **PromptRegistry imports used for resolution** — a ``from
   narrare_core.prompts`` (or ``narrare_core.prompts.registry``) import of
   ``PromptRegistry`` outside ``core/prompts/`` that is NOT part of
   dependency-injection wiring.

**DI-wiring exemption:** the app-layer DI container
(``apps/api/narrare/_app/dependencies_prompts.py``) imports ``PromptRegistry`` to
*construct* the singleton (``PromptRegistry(project_root=...)``) and inject it into
``PromptComposer``. Construction is wiring, not resolution — such imports are
exempted. Any ``.resolve()`` call is still flagged regardless.

**Enforcement boundary:** only ``core/prompts/`` (and the ``core/agents/
capabilities/`` allowance from ADR-046) may import/resolve via ``PromptRegistry``.

See: ``docs/architecture/decisions/ADR-046-prompt-path-compliance.md`` (D.2 Module 1)
See: ``docs/_shared/CONSTRAINTS.md`` RULE-02b
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation

# ── Allowed locations ──────────────────────────────────────────────
# core/prompts/ owns prompt resolution; core/agents/capabilities/ may use
# registry-backed loaders that route through core/prompts/ (ADR-046 allowance).
_ALLOWED_PREFIXES = (
    "packages/core/narrare_core/prompts/",
    "packages/core/narrare_core/prompts\\",
    "packages/core/narrare_core/agents/capabilities/",
    "packages/core/narrare_core/agents/capabilities\\",
)

# Test files legitimately exercise PromptRegistry directly — exempt.
_TEST_PATTERNS = (
    "/tests/",
    "\\tests\\",
    "/test_",
    "\\test_",
    "_test.py",
    "/conftest.py",
)

# Modules that re-export PromptRegistry (importing from either is a violation).
_REGISTRY_EXPORT_MODULES = frozenset(
    {
        "narrare_core.prompts.registry",
        "narrare_core.prompts",
    }
)

_RULE = "RULE-02b"


# ── Helpers ────────────────────────────────────────────────────────


def _is_exempt(rel_path: str) -> bool:
    """Return True for paths outside the RULE-02b enforcement surface."""
    if any(rel_path.startswith(p) for p in _ALLOWED_PREFIXES):
        return True
    return any(pat in rel_path for pat in _TEST_PATTERNS)


def _is_registry_receiver(node: ast.expr) -> bool:
    """Return True if *node* is a receiver that holds a PromptRegistry.

    Matches:
    - ``PromptRegistry``            (Name)
    - ``prompt_registry`` / ``_prompt_registry`` / ``self._prompt_registry``
      (any Name/Attribute whose textual id/attr contains "registry")
    """
    # Direct class reference: PromptRegistry.resolve(...)
    if isinstance(node, ast.Name):
        if node.id == "PromptRegistry":
            return True
        return "registry" in node.id.lower()

    # Attribute access: self._prompt_registry.resolve(...)
    # or registry_holder.resolve(...)
    if isinstance(node, ast.Attribute):
        if "registry" in node.attr.lower():
            return True
        # Recurse for chained receivers (e.g. self.deps.registry)
        return _is_registry_receiver(node.value)

    return False


def _imports_prompt_registry(tree: ast.AST) -> list[ast.ImportFrom]:
    """Return ImportFrom nodes that bring ``PromptRegistry`` into scope."""
    hits: list[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if module not in _REGISTRY_EXPORT_MODULES:
            continue
        if any(alias.name == "PromptRegistry" for alias in node.names):
            hits.append(node)
    return hits


def _has_prompt_registry_construction(tree: ast.AST) -> bool:
    """Return True if the file constructs ``PromptRegistry(...)`` (DI wiring).

    A ``PromptRegistry(project_root=...)`` call is instantiation for dependency
    injection — wiring, not resolution. Its presence marks the file as a DI
    container, exempting the bare import from violation.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "PromptRegistry"
        ):
            return True
    return False


# ── Public API ─────────────────────────────────────────────────────


def check_prompt_registry_access(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """RULE-02b: No direct PromptRegistry access outside core/prompts/.

    Flags:
    1. ``<registry>.resolve(...)`` calls — the resolution act (always flagged).
    2. ``PromptRegistry`` imports — flagged unless the file constructs
       ``PromptRegistry(...)`` for DI wiring.

    Exempts ``core/prompts/``, ``core/agents/capabilities/``, test files, and
    ``if TYPE_CHECKING:`` blocks.
    """
    if _is_exempt(rel_path):
        return []

    tc_lines = compute_type_checking_lines(tree)
    violations: list[Violation] = []

    # --- Check 1: .resolve() on a registry receiver (the resolution act) ---
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "resolve":
            continue
        if node.lineno in tc_lines:
            continue
        if not _is_registry_receiver(node.func.value):
            continue
        approved, reason = is_approved_exception(source_lines, node.lineno)
        violations.append(
            Violation(
                file=Path(rel_path),
                line=node.lineno,
                rule=_RULE,
                detail=(
                    "Direct PromptRegistry.resolve() outside core/prompts/ — "
                    "resolve prompts via PromptComposer.build() instead"
                ),
                approved=approved,
                approval_reason=reason,
            )
        )

    # --- Check 2: PromptRegistry import (exempt DI construction) ---
    is_wiring = _has_prompt_registry_construction(tree)
    for imp in _imports_prompt_registry(tree):
        if imp.lineno in tc_lines:
            continue
        if is_wiring:
            # Import is consumed by PromptRegistry(...) construction (DI wiring).
            continue
        approved, reason = is_approved_exception(source_lines, imp.lineno)
        violations.append(
            Violation(
                file=Path(rel_path),
                line=imp.lineno,
                rule=_RULE,
                detail=(
                    "PromptRegistry imported outside core/prompts/ for "
                    "resolution — route through PromptComposer instead "
                    "(or construct the singleton in the DI container)"
                ),
                approved=approved,
                approval_reason=reason,
            )
        )

    return violations
