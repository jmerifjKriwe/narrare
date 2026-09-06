"""Relationship application for the extraction apply flow (KB-007).

Applies a ``relationship`` extraction item: validates the predicate,
resolves both endpoints via :mod:`narrare.kb._extraction_resolution`,
and creates the KB edge. Split from ``extraction_apply_service.py`` for
RULE-04 compliance (the apply service sits at the 300-line limit).

Unresolvable items return a stable machine-readable skip reason that the
service reports in ``ApplyExtractionResponse.skipped`` — unapplied items
are never silently dropped.

See:
    :class:`narrare.kb.extraction_apply_service.ExtractionApplyService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._extraction_resolution import (
    UnresolvedRelationship,
    resolve_relationship_endpoints,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.schemas_extraction import ApplyExtractionItem

logger = structlog.get_logger(__name__)


async def apply_relationship_item(
    novel_id: UUID,
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    rel_repo: RelationshipRepository,
) -> str | None:
    """Create a KB relationship edge from a ``relationship`` item.

    The predicate must be present (``relationship_type``). Endpoint
    resolution uses ``source_entity_name``/``target_entity_name`` with
    legacy ``name``/``related_entity_name`` fallbacks (see
    :func:`narrare.kb._extraction_resolution.resolve_relationship_endpoints`).

    Args:
        novel_id: Novel scope.
        item: The endorsed extraction item.
        kb_repo: KB repository (novel-scoped endpoint lookups).
        rel_repo: Relationship repository (edge creation).

    Returns:
        Machine-readable skip reason, or ``None`` when the edge was created.
    """
    if not item.relationship_type or not item.relationship_type.strip():
        logger.warning(
            "relationship_missing_type",
            name=item.name,
        )
        return "missing_relationship_type"

    resolved = await resolve_relationship_endpoints(item, kb_repo, novel_id)
    if isinstance(resolved, UnresolvedRelationship):
        return resolved.reason

    from narrare.kb.models import KBRelationship

    rel = KBRelationship(
        source_id=resolved.source.id,
        target_id=resolved.target.id,
        rel_type=item.relationship_type,
    )
    await rel_repo.create(rel)
    logger.info(
        "apply_relationship_created",
        source=resolved.source.name,
        target=resolved.target.name,
        rel_type=item.relationship_type,
    )
    return None
