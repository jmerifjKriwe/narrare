"""PROMPT-INTEGRITY · Prompt content integrity checks (Gate 9).

Detects:
- Inline fallback prompts outside core/prompts/ that bypass MetaPromptLoader
- i18n gaps (EN prompts without DE/FR counterparts)
- Template variables not registered in _USER_CONTENT_VARS

All checks are advisory (approved=True) — they flag potential issues for
review, not CI-blocking violations.
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

_PROMPT_VAR_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_]*(PROMPT|SYSTEM_PROMPT|DEFAULT_SYSTEM)[A-Z0-9_]*$"
)

# Categories / sub-paths to skip for i18n checks
_I18N_SKIP_CATEGORIES: frozenset[str] = frozenset({"meta"})

_I18N_SKIP_SUBPATHS: frozenset[str] = frozenset(
    {
        "writing/tones/",  # language-neutral tone labels
        "generation/name-styles/",  # language-neutral name style lists
    }
)

_I18N_SKIP_FILES: frozenset[str] = frozenset(
    {
        "system.lite.md",  # EN-only documented
    }
)

_REQUIRED_LANGS: tuple[str, ...] = ("de", "fr")

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

_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


# ---------------------------------------------------------------------------
# 1. Inline fallback prompts
# ---------------------------------------------------------------------------


def check_inline_fallback_prompts(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """Scan Python files outside core/prompts/ for hardcoded prompt constants.

    Detects ALL_CAPS variable names containing PROMPT / SYSTEM_PROMPT /
    DEFAULT_SYSTEM that hold multi-line strings (>200 chars) — potential
    fallback prompts bypassing MetaPromptLoader.

    Excludes:
    - Files inside ``core/prompts/``
    - Test files (``test_`` or ``_test.py``)
    - ``__pycache__``
    - Files that already import/use ``MetaPromptLoader``
    """
    # Skip core/prompts/ itself
    if "core/prompts/" in rel_path or "narrare_core/prompts/" in rel_path:
        return []

    # Skip tests and cache
    parts = Path(rel_path).parts
    if any(p.startswith("test_") or p.endswith("_test.py") or p == "__pycache__" for p in parts):
        return []

    # If the file already uses MetaPromptLoader, it's properly handled
    full_source = "\n".join(source_lines)
    if "MetaPromptLoader" in full_source:
        return []

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            name = target.id
            if not _PROMPT_VAR_PATTERN.match(name):
                continue

            # Check for triple-quoted string (multi-line)
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                string_val = value.value
            elif isinstance(value, ast.JoinedStr):
                # f-strings can also be fallback prompts
                string_val = _extract_fstring_text(value)
            else:
                continue

            if len(string_val) <= 200:
                continue

            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="PROMPT-INTEGRITY",
                    detail=(
                        f"Potential inline fallback prompt '{name}' "
                        f"({len(string_val)} chars) outside core/prompts/ — "
                        f"should use MetaPromptLoader"
                    ),
                    approved=True,
                    approval_reason="Advisory — review if MetaPromptLoader bypass is intentional",
                )
            )

    return violations


def _extract_fstring_text(node: ast.JoinedStr) -> str:
    """Best-effort extraction of display text from an f-string AST node."""
    parts: list[str] = []
    for val in node.values:
        if isinstance(val, ast.Constant):
            parts.append(str(val.value))
        elif isinstance(val, ast.FormattedValue):
            parts.append("{{...}}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# 2. i18n completeness
# ---------------------------------------------------------------------------


def check_prompt_i18n_completeness(result: CheckResult) -> None:
    """Scan bundled prompt directories for i18n gaps.

    For each EN prompt file, checks that corresponding DE and FR files exist.
    Skips: meta category, writing/tones/, generation/name-styles/,
    system.lite.md (EN-only documented).
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    # Walk all EN files across all categories
    for en_file in bundled_dir.rglob("*.md"):
        # Only process EN files
        parts = en_file.relative_to(bundled_dir).parts
        if "en" not in parts:
            continue

        # Find the language position in path
        try:
            lang_idx = parts.index("en")
        except ValueError:
            continue

        # Skip: only process files directly under a language dir
        # e.g. category/en/mode/file.md
        if lang_idx < 1 or lang_idx >= len(parts) - 1:
            continue

        category = parts[0]

        # Skip meta category
        if category in _I18N_SKIP_CATEGORIES:
            continue

        # Skip specific sub-paths
        rel_path_str = str(Path(*parts[:lang_idx])) + "/"
        if any(skip in rel_path_str for skip in _I18N_SKIP_SUBPATHS):
            continue

        # Skip EN-only documented files
        if parts[-1] in _I18N_SKIP_FILES:
            continue

        # Check each required language
        for lang in _REQUIRED_LANGS:
            lang_parts = list(parts)
            lang_parts[lang_idx] = lang
            lang_file = bundled_dir / Path(*lang_parts)

            if not lang_file.exists():
                rel_path = relative_to_root(en_file)
                result.files_checked += 1
                result.approved_exceptions.append(
                    Violation(
                        file=Path(rel_path),
                        line=0,
                        rule="PROMPT-INTEGRITY",
                        detail=(
                            f"EN prompt exists but {lang.upper()} counterpart "
                            f"missing: {Path(*lang_parts)}"
                        ),
                        approved=True,
                        approval_reason=("i18n migration pending (CR-AUFG-04-07/04-10)"),
                    )
                )


# ---------------------------------------------------------------------------
# 3. Template variable registration
# ---------------------------------------------------------------------------


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


def _is_user_content_variable(name: str) -> bool:
    """Check if a variable name looks like user-provided content."""
    name_lower = name.lower()
    return any(indicator in name_lower for indicator in _USER_CONTENT_INDICATORS)


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
