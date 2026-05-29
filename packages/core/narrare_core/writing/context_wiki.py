"""Wiki-aware entity formatting for the context assembler.

Extracted from ``context_assembler.py`` for RULE-04 compliance.
Provides wiki-aware formatting with graceful fallback to raw content.

The formatting logic is a pure data transformation — no I/O, no DB,
no LLM calls.  It simply prefers ``WikiSummaryData.narrative_summary``
over ``KBEntity.content`` when a fresh wiki summary is available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.wiki.types import WikiSummaryStatus

if TYPE_CHECKING:
    from narrare_core.wiki.types import WikiSummaryData
    from narrare_core.writing.context_models import KBEntity


def format_entities_with_wiki(
    entities: list[KBEntity],
    wiki_summaries: dict[str, WikiSummaryData] | None,
) -> tuple[str, int, int]:
    """Format entities, preferring wiki summaries when fresh.

    For entities with a FRESH wiki summary, uses the compressed narrative
    format (~40 tokens).  Falls back to raw ``entity.content`` when the
    wiki summary is missing, stale, or pending.

    Args:
        entities: KB entities to format.
        wiki_summaries:
            Optional mapping of entity_id -> WikiSummaryData.
            When ``None`` or empty, all entities use the raw content format.

    Returns:
        Tuple of ``(formatted_text, fresh_count, stale_count)``.
    """
    if not entities:
        return "", 0, 0

    parts: list[str] = []
    fresh = 0
    stale = 0

    for entity in entities:
        header = f"### {entity.entity_type.title()}: {entity.name}"

        if wiki_summaries:
            wiki = wiki_summaries.get(entity.entity_id)
            if wiki is not None and wiki.status == WikiSummaryStatus.FRESH:
                # Use compressed wiki summary format
                text = f"{header}\n{wiki.narrative_summary}"
                if wiki.role_in_story:
                    text += f"\nRole: {wiki.role_in_story}"
                if wiki.key_attributes:
                    text += f"\nAttributes: {', '.join(wiki.key_attributes)}"
                parts.append(text)
                fresh += 1
                continue
            elif wiki is not None:
                # Wiki exists but stale/pending — count as stale fallback
                stale += 1

        # Fall back to raw entity content
        parts.append(f"{header}\n{entity.content}")

    return "\n\n".join(parts), fresh, stale
