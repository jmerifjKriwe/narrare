#!/usr/bin/env python3
"""
Individual check functions for Narrare prompt structure validation.

Contains check logic, data structures, and file parsing used by
check_prompt_structure.py.  Separated per RULE-04 (modularize, not compress).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003

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
}
VALID_LANGUAGES = {"en", "de", "fr"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")
HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
MAX_LINES = 300

# User-content variables that MUST be XML-wrapped for injection safety.
UNSAFE_USER_VARS = frozenset(
    {
        "existing_content",
        "chapter_text",
        "entry_content",
        "selection_text",
        "context_before",
        "context_after",
        "text_before",
        "text_after",
        "author_instructions",
        "conversation_history",
        "existing_answers",
    }
)

# Variables required per prompt_type category.
REQUIRED_VARS_BY_CATEGORY: dict[str, set[str]] = {
    "writing": {"user_preferences", "avoidance_patterns"},
    "kb": {"user_preferences", "avoidance_patterns"},
    "analysis": {"user_preferences", "avoidance_patterns"},
    "planning": {"user_preferences", "avoidance_patterns"},
    "generation": {"user_preferences", "avoidance_patterns"},
    "chat": {"user_preferences", "avoidance_patterns"},
}
CULTURE_GUIDELINES_CATEGORIES = {"writing", "planning"}
RAW_OUTPUT_TYPES = {"meta"}
RAW_OUTPUT_MODES = {"inline_suggest"}
META_EXEMPT_TYPES = {"meta"}


# ── Data structures ────────────────────────────────────────────


@dataclass
class Issue:
    """A single validation finding."""

    level: str  # "FAIL" or "WARN"
    file_path: str
    message: str


@dataclass
class PromptFile:
    """Parsed prompt file metadata."""

    path: Path
    rel_path: str  # relative to _bundled/
    frontmatter: dict[str, str] = field(default_factory=dict[str, str])
    content: str = ""
    variables: set[str] = field(default_factory=set[str])
    headings: list[str] = field(default_factory=list[str])
    line_count: int = 0
    has_frontmatter: bool = False
    has_system_prompt_heading: bool = False

    # Derived from path: category/locale/mode grouping.
    category: str = ""
    locale: str = ""
    mode: str = ""

    @property
    def prompt_type(self) -> str:
        return self.frontmatter.get("prompt_type", "")

    @property
    def prompt_language(self) -> str:
        return self.frontmatter.get("prompt_language", "")

    @property
    def prompt_version(self) -> str:
        return self.frontmatter.get("prompt_version", "")

    @property
    def variant(self) -> str:
        return self.frontmatter.get("variant", "")

    @property
    def is_system_md(self) -> bool:
        """True if this is a system.md prompt file (not tones, name-styles, etc.)."""
        return self.path.name == "system.md" or self.path.name.startswith("system.")

    @property
    def group_key(self) -> str:
        """Key for grouping across locales (e.g., 'kb/interview')."""
        parts = [self.category]
        if self.mode:
            parts.append(self.mode)
        return "/".join(parts)

    @property
    def display_path(self) -> str:
        """Short display path: category/locale/mode (without /system.md)."""
        parts = [self.category, self.locale]
        if self.mode:
            parts.append(self.mode)
        if self.variant:
            parts.append(f"({self.variant})")
        return "/".join(parts)


# ── Parsing ────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_prompt_file(path: Path, bundled_dir: Path) -> PromptFile:
    """Parse a single prompt file into a PromptFile struct."""
    rel = path.relative_to(bundled_dir)
    pf = PromptFile(path=path, rel_path=str(rel))

    text = path.read_text(encoding="utf-8")
    pf.content = text
    pf.line_count = len(text.splitlines())

    # Parse frontmatter.
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        pf.has_frontmatter = True
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                pf.frontmatter[key.strip()] = val.strip().strip('"').strip("'")

        content_after_fm = text[fm_match.end() :]
    else:
        content_after_fm = text

    # Extract variables from full text.
    pf.variables = set(VARIABLE_RE.findall(text))

    # Extract headings from content (after frontmatter).
    pf.headings = [m.group(1).strip() for m in HEADING_RE.finditer(content_after_fm)]
    pf.has_system_prompt_heading = any(
        h.lower().replace("-", " ") in ("system prompt", "system prompt") for h in pf.headings
    )

    # Derive category / locale / mode from path.
    parts = rel.parts
    #   meta/en/system.md → ("meta","en","system.md")
    #   writing/en/extend_chapter/system.md → deeper nesting
    #   writing/tones/quiet.md → non-system (no locale/mode)
    if len(parts) >= 2:
        pf.category = parts[0]
    if pf.is_system_md:
        if len(parts) >= 2:
            pf.locale = parts[1]
        if len(parts) >= 4:
            pf.mode = "/".join(parts[2:-1])
        elif len(parts) == 3:
            pf.mode = ""
    else:
        pf.locale = ""
        pf.mode = ""

    return pf


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
    if not has_system and pf.prompt_type not in META_EXEMPT_TYPES:
        issues.append(Issue("FAIL", pf.display_path, "Missing '## System Prompt' heading"))

    is_meta = pf.prompt_type in META_EXEMPT_TYPES
    is_inline_suggest = pf.mode == "inline_suggest" or pf.path.parent.name == "inline_suggest"

    # Output Format — exempt meta prompts and inline_suggest.
    has_output = any(
        "output format" in h or "ausgabeformat" in h or "format de sortie" in h
        for h in headings_lower
    )
    if not is_meta and not is_inline_suggest and not has_output:
        issues.append(Issue("WARN", pf.display_path, "Missing 'Output Format' section"))

    # Do NOT section — exempt meta prompts.
    has_do_not = any("do not" in h or "nicht" in h or "ne pas" in h for h in headings_lower)
    # Also check heading text broadly (e.g., "### Do NOT", "## Nicht").
    if (
        not is_meta
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
    """Check category-specific required variables."""
    category = group_key.split("/")[0]

    required = REQUIRED_VARS_BY_CATEGORY.get(category, set())
    for var in sorted(required):
        if var not in pf.variables:
            issues.append(
                Issue(
                    "WARN",
                    pf.display_path,
                    f"Missing required variable {{{{{var}}}}} for category '{category}'",
                )
            )

    if category in CULTURE_GUIDELINES_CATEGORIES and "culture_guidelines" not in pf.variables:
        issues.append(
            Issue(
                "WARN",
                pf.display_path,
                f"Missing {{{{culture_guidelines}}}} (required for {category} category)",
            )
        )


def check_security(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 4: User-content variables must be XML-wrapped."""
    if not pf.is_system_md:
        return

    for var in UNSAFE_USER_VARS:
        for i, line in enumerate(pf.content.splitlines(), 1):
            if f"{{{{{var}}}}}" not in line:
                continue
            # Check if the line contains XML wrapping around the variable.
            if re.search(
                r"<\w+[^>]*>.*\{\{" + re.escape(var) + r"\}\}.*</\w+>",
                line,
            ):
                continue
            issues.append(
                Issue(
                    "FAIL",
                    pf.display_path,
                    f"Variable {{{{{var}}}}} on line {i} is not wrapped "
                    f"in XML tags (user-content must be in "
                    f"<tag>{{{{var}}}}</tag> for safety)",
                )
            )


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
