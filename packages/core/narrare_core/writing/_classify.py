"""Entity classification for the writing context assembler.

Extracted from ``context_assembler.py`` for RULE-04 compliance.
Classifies KB entities into pinned, referenced, connected, and suggested tiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.writing.context_models import KBEntity


def classify_entities(
    entities: list[KBEntity],
    ref_ids: set[str],
    connections: dict[str, set[str]],
) -> tuple[list[KBEntity], list[KBEntity], list[KBEntity], list[KBEntity]]:
    """Classify entities into pinned, referenced, connected, suggested.

    Args:
        entities: All KB entities available for context assembly.
        ref_ids: Entity IDs referenced in chapter frontmatter.
        connections: Adjacency map of entity IDs to connected entity IDs.

    Returns:
        Tuple of (pinned, referenced, connected, suggested) entity lists.
    """
    pinned = [e for e in entities if e.is_pinned]
    referenced = [
        e for e in entities if not e.is_pinned and (e.entity_id in ref_ids or e.is_referenced)
    ]
    referenced_ids = {e.entity_id for e in referenced}
    # First-degree connections of referenced entities
    connected_ids: set[str] = set()
    for ref_id in referenced_ids:
        connected_ids.update(connections.get(ref_id, set()))
    connected_ids -= referenced_ids | {e.entity_id for e in pinned}
    connected = [e for e in entities if not e.is_pinned and e.entity_id in connected_ids]
    suggested = sorted(
        [
            e
            for e in entities
            if not e.is_pinned
            and e.entity_id not in referenced_ids
            and e.entity_id not in connected_ids
        ],
        key=lambda e: e.relevance_score,
        reverse=True,
    )
    return pinned, referenced, connected, suggested
