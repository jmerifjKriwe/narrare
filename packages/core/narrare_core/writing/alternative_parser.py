"""Alternative parser — extracts structured alternatives from LLM output.

Pure-function state machine that parses ``<alternative label="...">`` XML
tags from complete text.  No XML library dependency.  Used for server-side
validation and testing — the frontend has its own SSE-aware parser that
handles streaming chunks.

State machine: OPENING_TAG → CONTENT → CLOSING_TAG → NEXT_OR_DONE

Fallback: if no ``<alternative>`` tags are found, the entire text is
returned as a single ``Alternative`` with label ``"Rewritten text"``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Alternative:
    """A single parsed alternative from the LLM output."""

    label: str
    text: str


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------


# Matches an opening <alternative label="..."> tag that appears at a
# line boundary: either at the start of the string or immediately
# after a newline character.  The newline (if present) is consumed as
# part of the match so that the tag itself starts at the match group.
_OPENING_RE = re.compile(r'(?:^|\n)<alternative\s+label="([^"]*)">')

# Matches the closing </alternative> tag.
_CLOSING_RE = re.compile(r"</alternative>")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_alternatives(text: str) -> list[Alternative]:
    """Parse structured alternatives from LLM output text.

    Scans for ``<alternative label="...">...</alternative>`` blocks
    where the opening tag appears at a line boundary (start of string
    or after a newline).

    Fallback behaviour:
        If no ``<alternative>`` tags are found, returns the entire
        text as a single ``Alternative(label="Rewritten text", ...)``.

    Args:
        text: Complete LLM output text.

    Returns:
        List of parsed alternatives with their labels and content.
    """
    if not text:
        return []

    alternatives: list[Alternative] = []
    pos = 0

    while pos < len(text):
        # Search for the next opening tag at a line boundary.
        match = _OPENING_RE.search(text, pos)
        if not match:
            break

        label = match.group(1)
        content_start = match.end()

        # Find the closing tag
        close_match = _CLOSING_RE.search(text, content_start)
        if not close_match:
            # Malformed — no closing tag. Treat rest as content.
            content = text[content_start:].strip()
            alternatives.append(Alternative(label=label, text=content))
            break

        content = text[content_start : close_match.start()].strip()
        alternatives.append(Alternative(label=label, text=content))

        # Move past the closing tag to continue scanning
        pos = close_match.end()

    # Fallback: no tags found → entire text as single alternative
    if not alternatives:
        return [Alternative(label="Rewritten text", text=text.strip())]

    return alternatives
