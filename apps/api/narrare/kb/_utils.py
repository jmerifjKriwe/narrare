"""KB service utilities — slug generation, mention regex, and helpers.

Extracted from service.py to keep file sizes under RULE-04 limits.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.schemas import ReferenceResolution

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


def generate_reference_html(
    text: str,
    resolved: list[ReferenceResolution],
    novel_id: UUID,
) -> str:
    """Generate HTML with anchor tags for resolved KB references.

    Replaces @Name mentions in text with clickable anchor tags
    for mentions that resolved to existing KB entries.
    """

    def _replace_link(m: re.Match[str]) -> str:
        name = m.group(1).strip()
        for r in resolved:
            if r.mention == name and r.entry_id is not None:
                return (
                    f'<a href="/studio/{novel_id}/kb/{r.slug}" '
                    f'class="kb-mention" '
                    f'data-entry-id="{r.entry_id}" '
                    f'data-entity-type="{r.entity_type}">'
                    f"@{r.entry_name}"
                    f"</a>"
                )
        return m.group(0)

    return MENTION_RE.sub(_replace_link, text)
