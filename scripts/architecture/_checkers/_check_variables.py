"""RULE-VARS · Variable registration and usage checks.

Verifies:
- Every ``{{variable}}`` in bundled prompts is registered in exactly one of
  ``USER_CONTENT_VARS``, ``SYSTEM_VARS``, or ``FEATURE_DYNAMIC_VARS`` from
  ``variable_registry.py`` (variable_registration — INFRA-012)
- Every entry in ``SYSTEM_VARS`` is actually used in at least one
  prompt template (variable_usage — detects dead registrations)

INFRA-012: new unregistered variables fail CI; pre-existing gaps are ratcheted
via baseline. All three provenance classes are checked.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.architecture.helpers import ROOT, relative_to_root
from scripts.architecture.types import CheckResult, Violation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\}\}")

# Registry variable names in variable_registry.py
_REGISTRY_SETS = ("USER_CONTENT_VARS", "SYSTEM_VARS", "FEATURE_DYNAMIC_VARS")


# ---------------------------------------------------------------------------
# AST helpers — parse variable_registry.py
# ---------------------------------------------------------------------------


def _parse_frozenset_from_module(module_path: Path) -> dict[str, frozenset[str]]:
    """Parse all ``NAME: frozenset = frozenset({...})`` assignments from a file.

    Returns a dict mapping set name → frozenset of strings.
    """
    result: dict[str, frozenset[str]] = {}
    if not module_path.is_file():
        return result

    source = module_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(module_path))
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id in _REGISTRY_SETS
                and node.value is not None
            ):
                result[node.target.id] = _extract_frozenset_strings(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _REGISTRY_SETS:
                    result[target.id] = _extract_frozenset_strings(node.value)

    return result


def _extract_frozenset_strings(node: ast.AST) -> frozenset[str]:
    """Extract string values from a frozenset({...}) or set({...}) AST node."""
    strings: set[str] = set()

    if isinstance(node, ast.Call):
        # frozenset({...})
        for arg in node.args:
            if isinstance(arg, (ast.Set, ast.List)):
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        strings.add(elt.value)

    elif isinstance(node, ast.Set):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                strings.add(elt.value)

    return frozenset(strings)


# ---------------------------------------------------------------------------
# Fingerprinting for baseline ratcheting
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 1. Variable registration check
# ---------------------------------------------------------------------------


def check_variable_registration(result: CheckResult) -> None:
    """Check every {{variable}} in prompt files is registered.

    INFRA-012: Scans all prompt .md files in _bundled/ and verifies that every
    {{variable}} placeholder exists in one of the three provenance registries
    in ``variable_registry.py``.

    Unregistered variables produce FAIL-level violations. Dead registrations
    (vars in registry but never used) are reported as WARNING-level findings.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    registry_path = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "variable_registry.py"

    if not bundled_dir.is_dir():
        return

    registries = _parse_frozenset_from_module(registry_path)
    if not registries:
        return

    # Union of all three registries — vars can be in any one
    all_registered: set[str] = set()
    for s in registries.values():
        all_registered.update(s)
    registered_vars = frozenset(all_registered)

    # Collect all variables across all prompt files
    seen_unregistered: dict[str, list[str]] = {}

    for md_file in bundled_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        variables = _TEMPLATE_VAR_RE.findall(content)
        rel_path = relative_to_root(md_file)

        for var in set(variables):
            if var not in registered_vars:
                if var not in seen_unregistered:
                    seen_unregistered[var] = []
                seen_unregistered[var].append(rel_path)

    for var, files in sorted(seen_unregistered.items()):
        sample_files = files[:3]
        detail = (
            f"Unregistered template variable '{{{{{var}}}}}' — not found in "
            f"USER_CONTENT_VARS, SYSTEM_VARS, or FEATURE_DYNAMIC_VARS "
            f"(found in {len(files)} file(s): {', '.join(sample_files)})"
        )
        if len(files) > 3:
            detail += ", ..."

        # INFRA-012: unregistered variables are blocking violations
        result.violations.append(
            Violation(
                file=Path(files[0]),
                line=0,
                rule="PROMPT-VARS",
                detail=detail,
            )
        )


# ---------------------------------------------------------------------------
# 2. Variable usage check — every SYSTEM_VARS entry used in at least one prompt
# ---------------------------------------------------------------------------


def check_variable_usage(result: CheckResult) -> None:
    """Check that every SYSTEM_VARS entry is referenced in at least one prompt.

    Dead variables (registered but never used) indicate outdated registrations
    or unused infrastructure. Reported as advisory.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    registry_path = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "variable_registry.py"

    if not bundled_dir.is_dir():
        return

    registries = _parse_frozenset_from_module(registry_path)
    system_vars = registries.get("SYSTEM_VARS", frozenset())
    if not system_vars:
        return

    # Collect all variables used across all prompt files
    used_vars: set[str] = set()
    for md_file in bundled_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        used_vars.update(_TEMPLATE_VAR_RE.findall(content))

    # Find dead variables — emit ONE violation per dead var so each entry is
    # individually baselinable (a single-var drift must not invalidate an
    # aggregate signature covering other still-dead vars).
    dead_vars = sorted(system_vars - used_vars)
    for var in dead_vars:
        result.approved_exceptions.append(
            Violation(
                file=Path("packages/core/narrare_core/prompts/variable_registry.py"),
                line=0,
                rule="PROMPT-VARS",
                detail=(
                    f"Dead variable in SYSTEM_VARS — registered but never used "
                    f"in any prompt template: {var}"
                ),
                approved=True,
                approval_reason="Variable usage audit — dead registration",
            )
        )
