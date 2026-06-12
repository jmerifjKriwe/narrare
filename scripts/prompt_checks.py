#!/usr/bin/env python3
"""
Individual check functions for Narrare prompt structure validation.

Contains check logic and validation constants used by
check_prompt_structure.py.  Data structures and parsing live in
prompt_check_types.py.  Separated per RULE-04 (modularize, not compress).
"""

from __future__ import annotations

import re

from prompt_check_types import Issue, PromptFile
from prompt_governance_checks import check_prompt_governance
from prompt_vars import (
    MODE_EXEMPT_VARS,
    MODE_REQUIRED_VARS,
    REQUIRED_VARS_BY_CATEGORY,
    SHOULD_VARS_BY_CATEGORY,
)

# ── Constants ──────────────────────────────────────────────────

VALID_PROMPT_TYPES = {
    "meta",
    "writing",
    "kb",
    "analysis",
    "planning",
    "generation",
    "wiki",
    "chat",
    "universal",
}
VALID_LANGUAGES = {"en", "de", "fr"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAX_LINES = 300

RAW_OUTPUT_TYPES = {"meta"}
RAW_OUTPUT_MODES = {"inline_suggest"}
META_EXEMPT_TYPES = {"meta"}
UNIVERSAL_EXEMPT_TYPES = {"universal"}


# ── Checks ─────────────────────────────────────────────────────


def check_frontmatter(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 1: YAML frontmatter validation for system.md files."""
    if not pf.is_system_md:
        return

    if not pf.has_frontmatter:
        issues.append(Issue("FAIL", pf.display_path, "Missing YAML frontmatter"))
        return

    # prompt_type
    pt = pf.prompt_type
    if not pt:
        issues.append(Issue("FAIL", pf.display_path, "Missing 'prompt_type' in frontmatter"))
    elif pt not in VALID_PROMPT_TYPES:
        valid = ", ".join(sorted(VALID_PROMPT_TYPES))
        issues.append(
            Issue(
                "FAIL",
                pf.display_path,
                f"Invalid prompt_type '{pt}' (must be one of: {valid})",
            )
        )

    # prompt_language
    pl = pf.prompt_language
    if not pl:
        issues.append(Issue("FAIL", pf.display_path, "Missing 'prompt_language' in frontmatter"))
    elif pl not in VALID_LANGUAGES:
        valid = ", ".join(sorted(VALID_LANGUAGES))
        issues.append(
            Issue(
                "FAIL",
                pf.display_path,
                f"Invalid prompt_language '{pl}' (must be one of: {valid})",
            )
        )

    # prompt_version
    pv = pf.prompt_version
    if not pv:
        issues.append(Issue("FAIL", pf.display_path, "Missing 'prompt_version' in frontmatter"))
    elif not SEMVER_RE.match(pv):
        issues.append(
            Issue(
                "FAIL",
                pf.display_path,
                f"Invalid prompt_version '{pv}' (must match semver: X.Y.Z)",
            )
        )


def check_required_sections(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 2: Required sections in system.md files."""
    if not pf.is_system_md:
        return

    headings_lower = [h.lower() for h in pf.headings]

    has_system = any("system prompt" in h or "system-prompt" in h for h in headings_lower)
    if (
        not has_system
        and pf.prompt_type not in META_EXEMPT_TYPES
        and pf.prompt_type not in UNIVERSAL_EXEMPT_TYPES
    ):
        issues.append(Issue("FAIL", pf.display_path, "Missing '## System Prompt' heading"))

    is_meta = pf.prompt_type in META_EXEMPT_TYPES
    is_universal = pf.prompt_type in UNIVERSAL_EXEMPT_TYPES
    is_inline_suggest = pf.mode == "inline_suggest" or pf.path.parent.name == "inline_suggest"

    # Output Format — exempt meta prompts, universal rules, and inline_suggest.
    has_output = any(
        "output format" in h or "ausgabeformat" in h or "format de sortie" in h
        for h in headings_lower
    )
    if not is_meta and not is_universal and not is_inline_suggest and not has_output:
        issues.append(Issue("WARN", pf.display_path, "Missing 'Output Format' section"))

    # Do NOT section — exempt meta prompts and universal rules.
    has_do_not = any("do not" in h or "nicht" in h or "ne pas" in h for h in headings_lower)
    # Also check heading text broadly (e.g., "### Do NOT", "## Nicht").
    if (
        not is_meta
        and not is_universal
        and not has_do_not
        and not re.search(
            r"^#+\s+(?:Do\s+NOT|[Nn]icht|[ÀA]\s+ne\s+PAS)",
            pf.content,
            re.MULTILINE,
        )
    ):
        issues.append(Issue("WARN", pf.display_path, "Missing 'Do NOT' section"))


def check_variable_consistency(prompts: list[PromptFile], issues: list[Issue]) -> None:
    """Check 3: Variable consistency across locales for system.md files."""
    groups: dict[str, dict[str, PromptFile]] = {}
    for pf in prompts:
        if not pf.is_system_md or not pf.locale:
            continue
        key = pf.group_key
        groups.setdefault(key, {})[pf.locale] = pf

    for group_key, locale_files in sorted(groups.items()):
        if len(locale_files) < 2:
            for _locale, pf in locale_files.items():
                _check_required_vars(pf, group_key, issues)
            continue

        # Collect all variables across locales.
        all_vars_by_locale: dict[str, set[str]] = {
            loc: pf.variables for loc, pf in locale_files.items()
        }
        all_vars: set[str] = set()
        for v in all_vars_by_locale.values():
            all_vars |= v

        # Check each locale for missing variables.
        for locale, pf in sorted(locale_files.items()):
            missing: set[str] = all_vars - pf.variables
            if missing:
                present_in: list[str] = [
                    loc for loc, vs in all_vars_by_locale.items() if loc != locale and missing & vs
                ]
                present_str = ", ".join(sorted(present_in)) if present_in else "other locales"
                missing_display = ", ".join("{{" + v + "}}" for v in sorted(missing))
                issues.append(
                    Issue(
                        "WARN",
                        pf.display_path,
                        f"Missing variables: {missing_display} (present in {present_str})",
                    )
                )

        # Check required variables per category.
        for _locale, pf in locale_files.items():
            _check_required_vars(pf, group_key, issues)


def _check_required_vars(pf: PromptFile, group_key: str, issues: list[Issue]) -> None:
    """Check category-specific required, mode-specific, and should variables."""
    category = group_key.split("/")[0]

    # Check if this mode has exempted variables.
    exempt_vars = MODE_EXEMPT_VARS.get(category, {}).get(pf.mode, set())

    # 1. MUST: base category variables (WARN — existing behaviour).
    required = REQUIRED_VARS_BY_CATEGORY.get(category, set())
    for var in sorted(required):
        if var in exempt_vars:
            continue
        if var not in pf.variables:
            issues.append(
                Issue(
                    "WARN",
                    pf.display_path,
                    f"Missing required variable {{{{{var}}}}} for category '{category}'",
                )
            )

    # 2. MUST: mode-specific variables (FAIL — hard requirement per mode).
    if pf.mode:
        mode_vars = MODE_REQUIRED_VARS.get(category, {}).get(pf.mode, set())
        for var in sorted(mode_vars):
            if var not in pf.variables:
                issues.append(
                    Issue(
                        "FAIL",
                        pf.display_path,
                        f"Missing mode-required variable {{{{{var}}}}} "
                        f"for mode '{pf.mode}' in '{category}'",
                    )
                )

    # 3. SHOULD: recommended variables (WARN — not blocking).
    should_vars = SHOULD_VARS_BY_CATEGORY.get(category, set())
    for var in sorted(should_vars):
        if var in exempt_vars:
            continue
        if var not in pf.variables:
            issues.append(
                Issue(
                    "WARN",
                    pf.display_path,
                    f"Missing recommended variable {{{{{var}}}}} "
                    f"for category '{category}' (SHOULD)",
                )
            )


def check_security(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 4: Prompt security and CR-01 governance gates."""
    check_prompt_governance(pf, issues)


def check_file_size(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 5: No prompt file should exceed 300 lines."""
    if pf.line_count > MAX_LINES:
        issues.append(
            Issue(
                "FAIL",
                pf.display_path,
                f"File exceeds {MAX_LINES} lines ({pf.line_count} lines) "
                f"— split into smaller modules (RULE-04)",
            )
        )
