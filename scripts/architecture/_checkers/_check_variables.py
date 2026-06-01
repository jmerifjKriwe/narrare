"""RULE-VARS · Variable registration and usage checks.

Verifies:
- Every ``{{variable}}`` in bundled prompts is registered in either
  ``_SYSTEM_VARS`` or ``_USER_CONTENT_VARS`` (variable_registration)
- Every entry in ``_SYSTEM_VARS`` is actually used in at least one
  prompt template (variable_usage — detects dead registrations)

Exits: called from ``prompt_integrity.run_all_checks()``.
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

# Variable name substrings that indicate user-provided content
_USER_CONTENT_INDICATORS: frozenset[str] = frozenset(
    {
        "kb_",
        "content",
        "text",
        "name",
        "selection",
        "summary",
        "profile",
        "preferences",
    }
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\}\}")

# Variables that are system-level config (author-controlled, not attacker-controlled)
# and should NOT be flagged even if they match a user-content indicator substring.
_SYSTEM_VAR_WHITELIST: frozenset[str] = frozenset(
    {
        # System/config variables — controlled by the application, not user content
        "language",
        "genre",
        "tone",
        "word_target",
        "project_title",
        "author_name",
        "story_structure",
        "writing_language",
        "explanation_language",
        "name_type",
        "gender",
        "extend_length",
        "count",
        "event_count",
        "structure_type",
        "deepdive_category",
        "focus_categories",
        "check_types",
        "target_field",
        "target_field_description",
        "rewrite_mode_instructions",
        "co_author_focus_instructions",
        "category_focus_instructions",
        "tone_instructions",
        "culture_guidelines",
        "chapter_title",
        "chapter_titles",
        "timeline_position",
        "entity_type",
        "word_count",
        "template_structures",
    }
)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _extract_frozenset_strings(node: ast.AST) -> frozenset[str]:
    """Extract string values from a frozenset({...}) AST node."""
    strings: set[str] = set()

    # Handle frozenset({...}) call
    if isinstance(node, ast.Call):
        for arg in node.args:
            if isinstance(arg, ast.Set):
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        strings.add(elt.value)

    # Handle direct frozenset assignment
    if isinstance(node, ast.Set):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                strings.add(elt.value)

    return frozenset(strings)


def _parse_user_content_vars() -> frozenset[str]:
    """Parse _USER_CONTENT_VARS from variable_engine.py."""
    engine_path = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "variable_engine.py"
    if not engine_path.is_file():
        return frozenset()

    source = engine_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(engine_path))

    for node in ast.walk(tree):
        # Handle both ast.Assign (untyped) and ast.AnnAssign (type-annotated)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_USER_CONTENT_VARS":
                    return _extract_frozenset_strings(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_USER_CONTENT_VARS"
            and node.value is not None
        ):
            return _extract_frozenset_strings(node.value)

    return frozenset()


def _is_user_content_variable(name: str) -> bool:
    """Check if a variable name looks like user-provided content."""
    name_lower = name.lower()
    return any(indicator in name_lower for indicator in _USER_CONTENT_INDICATORS)


def _parse_system_vars() -> frozenset[str]:
    """Parse _SYSTEM_VARS from variable_engine.py."""
    engine_path = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "variable_engine.py"
    if not engine_path.is_file():
        return frozenset()

    source = engine_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(engine_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_SYSTEM_VARS":
                    return _extract_frozenset_strings(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_SYSTEM_VARS"
            and node.value is not None
        ):
            return _extract_frozenset_strings(node.value)

    return frozenset()


# ---------------------------------------------------------------------------
# 1. Variable registration check
# ---------------------------------------------------------------------------


def check_variable_registration(result: CheckResult) -> None:
    """Check every {{variable}} in prompt files is registered.

    Scans all prompt .md files in _bundled/ and verifies that every
    {{variable}} placeholder exists in either _SYSTEM_VARS or
    _USER_CONTENT_VARS. Unregistered variables produce WARNING-level
    findings.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    system_vars = _parse_system_vars()
    user_content_vars = _parse_user_content_vars()
    registered_vars = system_vars | user_content_vars

    if not registered_vars:
        return

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
            f"Unregistered variable '{{{{{var}}}}}' — not found in "
            f"_SYSTEM_VARS or _USER_CONTENT_VARS "
            f"(found in {len(files)} file(s): {', '.join(sample_files)})"
        )
        if len(files) > 3:
            detail += ", ..."

        result.approved_exceptions.append(
            Violation(
                file=Path(files[0]),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=detail,
                approved=True,
                approval_reason="Variable registration audit (D5.1)",
            )
        )


# ---------------------------------------------------------------------------
# 2. Variable usage check — every _SYSTEM_VARS entry used in at least one prompt
# ---------------------------------------------------------------------------


def check_variable_usage(result: CheckResult) -> None:
    """Check that every _SYSTEM_VARS entry is referenced in at least one prompt.

    Dead variables (registered but never used) are reported as WARNING.
    These may indicate outdated registrations or unused infrastructure.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    system_vars = _parse_system_vars()
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

    # Find dead variables
    dead_vars = sorted(system_vars - used_vars)
    if dead_vars:
        result.approved_exceptions.append(
            Violation(
                file=Path("packages/core/narrare_core/prompts/variable_engine.py"),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=(
                    f"Dead variable(s) in _SYSTEM_VARS — registered but never used "
                    f"in any prompt template: {', '.join(dead_vars)}"
                ),
                approved=True,
                approval_reason="Variable usage audit (D5.4)",
            )
        )


# ---------------------------------------------------------------------------
# 3. Template variable registration (user-content check)
# ---------------------------------------------------------------------------


def check_template_variables(result: CheckResult) -> None:
    """Scan prompt .md files for {{variables}} not in _USER_CONTENT_VARS.

    Flags variables that look like user content (contain kb_, content, text,
    name, selection, summary, profile, preferences) but are not registered
    in ``_USER_CONTENT_VARS`` in ``variable_engine.py``.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    registered_vars = _parse_user_content_vars()
    if not registered_vars:
        return

    # Collect all variables across all prompt files
    seen_unregistered: dict[str, list[str]] = {}  # var_name -> [files]

    for md_file in bundled_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        variables = _TEMPLATE_VAR_RE.findall(content)
        rel_path = relative_to_root(md_file)

        for var in set(variables):
            # Skip system/config variables
            if var in _SYSTEM_VAR_WHITELIST:
                continue

            # Only check variables that look like user content
            if not _is_user_content_variable(var):
                continue

            # Skip if already registered
            if var in registered_vars:
                continue

            # Track unregistered variables
            if var not in seen_unregistered:
                seen_unregistered[var] = []
            seen_unregistered[var].append(rel_path)

    # Report one violation per unregistered variable
    for var, files in sorted(seen_unregistered.items()):
        sample_files = files[:3]
        detail = (
            f"Template variable '{{{{{var}}}}}' looks like user content "
            f"but is not registered in _USER_CONTENT_VARS "
            f"(found in {len(files)} file(s): {', '.join(sample_files)})"
        )
        if len(files) > 3:
            detail += ", ..."

        result.approved_exceptions.append(
            Violation(
                file=Path(sample_files[0]),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=detail,
                approved=True,
                approval_reason="Variable registration migration pending",
            )
        )
