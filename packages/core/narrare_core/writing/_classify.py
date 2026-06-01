"""Entity classification for the writing context assembler.

Extracted from ``context_assembler.py`` for RULE-04 compliance.
Classifies KB entities into pinned, referenced, connected, and suggested tiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.writing.context_models import KBEntity

logger = structlog.get_logger(__name__)


def classify_entities(
    entities: list[KBEntity],
    ref_ids: set[str],
    connections: dict[str, set[str]],
) -> tuple[list[KBEntity], list[KBEntity], list[KBEntity], list[KBEntity]]:
    """Classify entities into pinned, referenced, connected, suggested.

    Deprecated entities (status == ``"deprecated"``) are excluded from all
    categories and logged as a warning.

    Args:
        entities: All KB entities available for context assembly.
        ref_ids: Entity IDs referenced in chapter frontmatter.
        connections: Adjacency map of entity IDs to connected entity IDs.

    Returns:
        Tuple of (pinned, referenced, connected, suggested) entity lists.
    """
    # Filter out deprecated entities
    active: list[KBEntity] = []
    for e in entities:
        if e.status == "deprecated":
            logger.warning(
                "entity_deprecated_excluded",
                entity_id=e.entity_id,
                entity_name=e.name,
                entity_type=e.entity_type,
            )
        else:
            active.append(e)

    draft_count = sum(1 for e in active if e.status == "draft")
    if draft_count:
        logger.info("draft_entities_in_context", count=draft_count)

    pinned = [e for e in active if e.is_pinned]
    referenced = [
        e for e in active if not e.is_pinned and (e.entity_id in ref_ids or e.is_referenced)
    ]
    referenced_ids = {e.entity_id for e in referenced}
    # First-degree connections of referenced entities
    connected_ids: set[str] = set()
    for ref_id in referenced_ids:
        connected_ids.update(connections.get(ref_id, set()))
    connected_ids -= referenced_ids | {e.entity_id for e in pinned}
    connected = [e for e in active if not e.is_pinned and e.entity_id in connected_ids]
    suggested = sorted(
        [
            e
            for e in active
            if not e.is_pinned
            and e.entity_id not in referenced_ids
            and e.entity_id not in connected_ids
        ],
        key=lambda e: e.relevance_score,
        reverse=True,
    )
    return pinned, referenced, connected, suggested
