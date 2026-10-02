# packages/core/narrare_core/importing/splitting.py
"""Section splitting for Markdown headings and TXT chapter markers (pure).

The regexes are the SSOT of the v1 detection heuristics (ADR-091 / spec §5):
ATX h1/h2 lines split Markdown; "Chapter X"/"Kapitel X" lines (EN/DE,
Arabic or Roman numerals, case-insensitive) split plain text.
"""

from __future__ import annotations

import re

# ATX h1/h2 heading line: 1-2 '#' + whitespace + visible text.
ATX_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.MULTILINE)

# TXT chapter marker: optional indent, chapter|kapitel, Arabic or Roman
# numeral, optional trailing text on the same line (kept in the title).
CHAPTER_MARKER_RE = re.compile(
    r"^[ \t]*(?:chapter|kapitel)[ \t]+([0-9]+|[ivxlcdm]+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split a Markdown body on ATX h1/h2 heading lines.

    Returns (heading_text, section_body) pairs in document order. Text before
    the first heading is returned as ("", preamble) when non-empty after
    stripping. With no headings the whole text is a single ("", text) pair.
    """
    matches = list(ATX_HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), text[match.end() : end].strip()))
    return sections


def split_marker_sections(text: str) -> list[tuple[str, str]]:
    """Split plain text on "Chapter X"/"Kapitel X" marker lines.

    Returns (marker_line, section_body) pairs in document order; the whole
    marker line (trimmed) is the title. Preamble handling mirrors
    :func:`split_markdown_sections`.
    """
    matches = list(CHAPTER_MARKER_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((match.group(0).strip(), text[match.end() : end].strip()))
    return sections


def fallback_title(filename: str) -> str:
    """DemoLoader-style title from a filename stem (dashes → spaces, Title Case)."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    formatted = stem.replace("-", " ").title()
    return formatted or "Untitled Chapter"
