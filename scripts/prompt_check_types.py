#!/usr/bin/env python3
"""
Data structures and parsing for Narrare prompt structure validation.

Contains the Issue/PromptFile dataclasses and the parse_prompt_file function
used by all prompt check modules.  Separated per RULE-04 (modularize,
not compress).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003

# ── Parsing helpers ────────────────────────────────────────────

VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")
HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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
