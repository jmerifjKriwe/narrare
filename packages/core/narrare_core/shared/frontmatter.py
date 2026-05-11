"""
Frontmatter parsing utilities.

Single implementation used by all modules that read Markdown files
with YAML frontmatter. Replaces the three competing implementations
in the previous codebase.

Format:
    ---
    key: value
    list:
      - item1
      - item2
    ---

    Markdown content here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<yaml>.*?)\n---\s*\n?(?P<content>.*)",
    re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class ParsedFrontmatter:
    """Result of parsing a Markdown file with YAML frontmatter."""

    metadata: dict[str, Any]
    content: str
    has_frontmatter: bool

    def get(self, key: str, default: Any = None) -> Any:
        """Get a metadata value with an optional default."""
        return self.metadata.get(key, default)

    def require(self, key: str) -> Any:
        """Get a required metadata value, raising KeyError if missing."""
        if key not in self.metadata:
            raise KeyError(f"Required frontmatter key missing: '{key}'")
        return self.metadata[key]


def parse_frontmatter(text: str) -> ParsedFrontmatter:
    """
    Parse YAML frontmatter from a Markdown string.

    Args:
        text: Raw Markdown content, optionally starting with --- frontmatter ---.

    Returns:
        ParsedFrontmatter with metadata dict and remaining content.
        If no frontmatter is found, metadata is empty and content is the full text.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return ParsedFrontmatter(metadata={}, content=text, has_frontmatter=False)

    try:
        raw = yaml.safe_load(match.group("yaml"))
        metadata: dict[str, Any] = raw if isinstance(raw, dict) else {}  # pyright: ignore[reportUnknownVariableType]
    except yaml.YAMLError:
        metadata = {}

    return ParsedFrontmatter(
        metadata=metadata,
        content=match.group("content").strip(),
        has_frontmatter=True,
    )


def strip_frontmatter(text: str) -> str:
    """
    Remove YAML frontmatter from a Markdown string.

    Args:
        text: Raw Markdown content.

    Returns:
        Content without frontmatter header.
    """
    return parse_frontmatter(text).content


def extract_section(text: str, section_name: str) -> str | None:
    """
    Extract a named Markdown section (## Section Name) from content.

    Searches for the section header (case-insensitive) and returns
    everything from after the header until the next ## header or end of file.

    Args:
        text: Markdown content (frontmatter already stripped).
        section_name: Section header to find (without ##).

    Returns:
        Section content, or None if not found.
    """
    # Build pattern for the section header — allow variations
    # e.g. "System Prompt", "System-Prompt", "Systemprompt"
    normalized = re.escape(section_name.strip())
    pattern = re.compile(
        rf"^##\s+{normalized}\s*$\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()
