"""Prompt integrity regression tests.

These tests prevent regressions when prompts are added or changed.
They enforce **RULE-02** (prompts are built in ``core/prompts/`` only)
and verify structural integrity of bundled prompt files.

All tests are pure unit tests: no LLM, no DB, no network.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ._prompt_helpers import (
    BUNDLED_ROOT,
    PROJECT_ROOT,
    PROMPTS_DIR,
    find_prompt_constants,
    get_bundled_prompts,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known acceptable exceptions: inline prompt constants that are allowed
# outside core/prompts/ despite violating RULE-02.
# Format: relative-path-from-project-root → set of variable names
_INLINE_PROMPT_EXCEPTIONS: dict[str, set[str]] = {
    "packages/core/narrare_core/memory/mem0_client.py": {
        "WRITING_PREFERENCE_EXTRACTION_PROMPT",
    },
    "apps/api/narrare/consistency/prompt_builder.py": {
        "CONSISTENCY_SYSTEM_PROMPT",
    },
    "apps/api/narrare/kb/extraction_service.py": {
        "_DEFAULT_SYSTEM_PROMPT",
    },
}

# Declarative role-definition patterns across supported languages.
# Used by test_bundled_prompts_have_role_definition and _has_role_definition().
_ROLE_PATTERNS: tuple[str, ...] = (
    "You are",
    "Your role",
    "Du bist",
    "Deine Aufgabe",
    "Tu es",
    "Ton rôle",
    "Vous êtes",
    "Votre rôle",
)

# Directories to skip when scanning for inline prompt violations.
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        "tests",
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
        ".tox",
        "dist",
        "build",
        ".eggs",
    }
)


# ---------------------------------------------------------------------------
# Test 1: No inline fallback prompts outside core/prompts/
# ---------------------------------------------------------------------------


class TestNoInlineFallbackPrompts:
    """RULE-02 enforcement: no prompt strings outside ``core/prompts/``."""

    def test_no_inline_fallback_prompts_without_meta(self) -> None:
        """Python files outside ``core/prompts/`` must not define large prompt constants.

        Variables whose name contains ``PROMPT`` (case-insensitive) with string
        values exceeding 200 characters are considered inline prompt definitions.
        They are only acceptable when:

        1. The file also imports/uses ``MetaPromptLoader`` (properly handled), **or**
        2. The variable is listed in ``_INLINE_PROMPT_EXCEPTIONS``.

        Known acceptable exceptions:

        - ``mem0_client.py:WRITING_PREFERENCE_EXTRACTION_PROMPT`` — mem0-internal,
          different system (per approved exception in CONSTRAINTS.md).
        """
        violations: list[str] = []

        for py_file in _iter_source_python_files():
            rel = py_file.relative_to(PROJECT_ROOT)
            rel_str = str(rel)

            # core/prompts/ is the allowed location (RULE-02)
            try:
                py_file.relative_to(PROMPTS_DIR)
                continue
            except ValueError:
                pass

            constants = find_prompt_constants(py_file)
            if not constants:
                continue

            # If the file uses MetaPromptLoader → properly handled
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "MetaPromptLoader" in source:
                continue

            # Check against known exceptions
            allowed_vars = _INLINE_PROMPT_EXCEPTIONS.get(rel_str, set())

            for name, lineno, _content in constants:
                if name in allowed_vars:
                    continue
                violations.append(
                    f"{rel_str}:{lineno} — {name} (define in core/prompts/ or use MetaPromptLoader)"
                )

        assert not violations, (
            "RULE-02 violations — inline prompt constants found outside core/prompts/:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Test 2: Bundled prompts have role definitions
# ---------------------------------------------------------------------------


def _has_role_definition(content: str) -> bool:
    """Check whether *content* contains a role definition.

    Matches two kinds of role definitions:

    1. **Declarative patterns** — ``You are``, ``Du bist``, ``Tu es``, etc.
    2. **Second-person sentences** — Lines starting with ``Du `` or ``Tu ``
       that define what the AI does (e.g. "Du führst eine Tiefenanalyse…",
       "Tu fournis une analyse approfondie…").
    """
    # Check declarative patterns first
    if any(pattern in content for pattern in _ROLE_PATTERNS):
        return True

    # Check for second-person role-defining sentences at line start.
    # These are common in German/French prompts where the role is defined
    # by behaviour ("You perform X…") rather than identity ("You are X").
    for line in content.splitlines():
        stripped = line.strip()
        # Skip empty lines, headings, and template variables
        if not stripped or stripped.startswith("#") or stripped.startswith("{{"):
            continue
        # German: "Du führst…", "Du analysierst…", etc.
        if stripped.startswith("Du ") and len(stripped) > 20:
            return True
        # French: "Tu fournis…", "Tu analyse…", etc.
        if stripped.startswith("Tu ") and len(stripped) > 20:
            return True

    return False


class TestBundledPromptsHaveRoleDefinition:
    """Every bundled system prompt must define the AI's role."""

    def test_bundled_prompts_have_role_definition(self) -> None:
        """Each bundled prompt must contain a role definition.

        Role definitions include patterns like ``You are``, ``Your role``,
        ``Du bist``, ``Tu es``, etc.

        Skips:

        - ``meta/`` category (tested separately)
        - ``system.lite.md`` (intentionally compact)
        - Supplementary files without ``prompt_type`` frontmatter
          (tone files, name-style files)
        """
        if not BUNDLED_ROOT.is_dir():
            pytest.skip("Bundled prompts directory not found")

        violations: list[str] = []

        for md_file in get_bundled_prompts():
            rel = md_file.relative_to(BUNDLED_ROOT)
            rel_str = str(rel)

            # Skip meta/ category — covered by test_meta_prompt_version_consistency
            if rel.parts[0] == "meta":
                continue

            # Skip system.lite.md — intentionally compact
            if md_file.name == "system.lite.md":
                continue

            content = md_file.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            metadata, content_lines = parse_frontmatter(lines)

            # Only check actual prompt files (have prompt_type frontmatter).
            # Tones, name-styles and other supplementary files don't define roles.
            if "prompt_type" not in metadata:
                continue

            content_text = "\n".join(content_lines)

            if not _has_role_definition(content_text):
                violations.append(
                    f"{rel_str} — no role definition found "
                    f"(expected declarative pattern like "
                    f"'You are', 'Du bist', 'Tu es' or "
                    f"second-person sentence starting with 'Du '/'Tu ')"
                )

        assert not violations, "Bundled prompts missing role definitions:\n" + "\n".join(
            f"  - {v}" for v in violations
        )


# ---------------------------------------------------------------------------
# Test 3: Meta-prompt version consistency
# ---------------------------------------------------------------------------


class TestMetaPromptVersionConsistency:
    """All meta-prompt language versions must be synchronised."""

    def test_meta_prompt_version_consistency(self) -> None:
        """Meta-prompts (en, de, fr) must share the same ``prompt_version``.

        Also verifies that all language versions contain:

        - A role-definition sentence (``Your role`` / ``Deine Aufgabe`` /
          ``Ton rôle``)
        - Conflict resolution instructions referencing the outline
          (``outline`` / ``Gliederung`` / ``plan``)
        """
        languages = ("en", "de", "fr")
        versions: dict[str, str] = {}
        contents: dict[str, str] = {}

        for lang in languages:
            path = BUNDLED_ROOT / "meta" / lang / "system.md"
            if not path.is_file():
                pytest.skip(f"Meta-prompt for '{lang}' not found at {path}")

            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            metadata, content_lines = parse_frontmatter(lines)

            versions[lang] = metadata.get("prompt_version", "MISSING")
            contents[lang] = "\n".join(content_lines)

        # --- All prompt_versions must match ---
        unique_versions = set(versions.values())
        assert len(unique_versions) == 1, (
            f"Meta-prompt versions are inconsistent: {versions}. "
            f"All languages must share the same prompt_version."
        )

        # --- Role definition (Your role / Deine Aufgabe / Ton rôle) ---
        role_markers: dict[str, str] = {
            "en": "Your role",
            "de": "Deine Aufgabe",
            "fr": "Ton rôle",
        }
        for lang, marker in role_markers.items():
            assert marker in contents[lang], (
                f"Meta-prompt '{lang}' is missing '{marker}' role definition"
            )

        # --- Conflict resolution (outline / Gliederung / plan) ---
        conflict_markers: dict[str, str] = {
            "en": "outline",
            "de": "Gliederung",
            "fr": "plan",
        }
        for lang, marker in conflict_markers.items():
            assert marker in contents[lang], (
                f"Meta-prompt '{lang}' is missing conflict resolution "
                f"(expected '{marker}' in content)"
            )


# ---------------------------------------------------------------------------
# Test 4: Lite meta-prompt has essential content
# ---------------------------------------------------------------------------


class TestLitePromptHasEssentials:
    """The lite meta-prompt must contain key behavioural instructions."""

    def test_lite_prompt_has_essentials(self) -> None:
        """Lite meta-prompt must reference core concepts.

        Checks for:

        - ``fiction`` or ``narrative`` — fiction content guidelines
        - ``avoidance`` — avoidance patterns reference
        """
        lite_path = BUNDLED_ROOT / "meta" / "en" / "system.lite.md"
        if not lite_path.is_file():
            pytest.skip(f"Lite meta-prompt not found at {lite_path}")

        text = lite_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        _metadata, content_lines = parse_frontmatter(lines)
        content = "\n".join(content_lines).lower()

        checks: list[tuple[str, str, list[str]]] = [
            ("fiction guidelines", "fiction or narrative", ["fiction", "narrative"]),
            ("avoidance patterns", "avoidance", ["avoidance"]),
        ]

        failures: list[str] = []
        for category, description, keywords in checks:
            if not any(kw in content for kw in keywords):
                failures.append(f"{category}: expected '{description}' in lite meta-prompt")

        assert not failures, "Lite meta-prompt is missing essential content:\n" + "\n".join(
            f"  - {f}" for f in failures
        )


# ---------------------------------------------------------------------------
# Utility: iterate Python source files (excluding tests, venv, etc.)
# ---------------------------------------------------------------------------


def _iter_source_python_files() -> list[Path]:
    """Collect Python source files from ``apps/`` and ``packages/``.

    Excludes test directories, virtualenvs, and cache/build artefacts.
    """
    files: list[Path] = []
    scan_dirs = [
        PROJECT_ROOT / "apps",
        PROJECT_ROOT / "packages",
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for py_file in scan_dir.rglob("*.py"):
            parts = py_file.relative_to(PROJECT_ROOT).parts
            if any(part in _EXCLUDED_DIR_NAMES for part in parts):
                continue
            files.append(py_file)

    return sorted(files)
