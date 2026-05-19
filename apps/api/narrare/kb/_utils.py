"""KB service utilities — slug generation, mention regex, and helpers.

Extracted from service.py to keep file sizes under RULE-04 limits.
"""

from __future__ import annotations

import re

# Regex to match @Name mentions in body text.
# Matches @ followed by a name consisting of letters, apostrophes, and hyphens.
# Multi-word names (space-separated) are supported when subsequent words start
# with an uppercase letter — this aligns with typical entity naming conventions.
# Boundaries: non-letter before @, non-letter after the name.
MENTION_RE = re.compile(
    r"(?<![A-Za-zÀ-ÖØ-öø-ÿ])@"
    r"([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ\'-]*"
    r"(?:\s+[A-Z][a-zÀ-ÖØ-öø-ÿ\'-]*)*)"
    r"(?![A-Za-zÀ-ÖØ-öø-ÿ])"
)


def slugify(name: str) -> str:
    """Convert a name to a URL-friendly slug.

    Lowercases, replaces whitespace with hyphens, strips special chars,
    and collapses consecutive hyphens.
    """
    slug = re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", name.lower()))
    return re.sub(r"-+", "-", slug).strip("-")
