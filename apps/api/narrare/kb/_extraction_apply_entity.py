"""Entity application for the extraction apply flow (KB-007).

Applies ``new_entity`` and ``update_entity`` extraction items: creates a
KB entry via ``KBService``, or resolves an update target via
:mod:`narrare.kb._extraction_resolution` and updates the entry
(downgrade-guarded rename, merge-not-clobber metadata). Split from
``extraction_apply_service.py`` for RULE-04 compliance when per-item
SAVEPOINT wiring (benchmark run 5 batch-robustness fix) pushed the apply
service over the 300-line limit — mirroring the existing
``_extraction_apply_relationship`` split.

Unapplied items return a stable machine-readable skip reason that the
service reports in ``ApplyExtractionResponse.skipped`` — unapplied items
are never silently dropped.

See:
    :class:`narrare.kb.extraction_apply_service.ExtractionApplyService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._extraction_resolution import resolve_update_target
from narrare.kb.schemas import (
    KBEntryCreate,
    KBEntryUpdate,
)
from narrare.kb.schemas_extraction import ApplyExtractionEntryResult

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.schemas_extraction import ApplyExtractionItem
    from narrare.kb.service import KBService

logger = structlog.get_logger(__name__)


async def apply_new_entity_item(
    novel_id: UUID,
    user_id: UUID,
    item: ApplyExtractionItem,
    kb_service: KBService,
    created_entries: list[ApplyExtractionEntryResult],
) -> None:
    """Create a new KB entry from a ``new_entity`` extraction item.

    Args:
        novel_id: Novel scope.
        user_id: Requesting user.
        item: The extraction item.
        kb_service: KB service (entry creation).
        created_entries: Accumulator for results.
    """
    data = KBEntryCreate(
        entity_type=item.entity_type or "unknown",
        name=item.name,
        metadata=item.proposed_content,
        body=item.source_text,
        status="draft",
        source="auto_extraction",
        review_status="pending",
    )
    entry = await kb_service.create(
        novel_id=novel_id,
        user_id=user_id,
        data=data,
    )
    created_entries.append(
        ApplyExtractionEntryResult(
            id=str(entry.id),
            name=entry.name,
            entity_type=entry.entity_type,
        ),
    )
    logger.info(
        "apply_new_entity_created",
        entry_id=str(entry.id),
        name=item.name,
        entity_type=item.entity_type,
    )


async def apply_update_entity_item(
    novel_id: UUID,
    user_id: UUID,
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    kb_service: KBService,
    updated_entries: list[ApplyExtractionEntryResult],
) -> str | None:
    """Update an existing KB entry from an ``update_entity`` item.

    Target resolution, the downgrade-guarded rename decision, and the
    merge-not-clobber metadata composition live in
    :mod:`narrare.kb._extraction_resolution`; unresolvable items are a
    reported skip (RULE-11).

    Args:
        novel_id: Novel scope.
        user_id: Requesting user.
        item: The extraction item.
        kb_repo: KB repository (update-target resolution).
        kb_service: KB service (entry update).
        updated_entries: Accumulator for results.

    Returns:
        Skip reason, or ``None`` when the entry was updated. The precise
        failure cause is in the logs; the response carries the stable
        ``target_not_resolved`` identifier.
    """
    decision = await resolve_update_target(item, kb_repo, novel_id)
    if decision is None:
        return "target_not_resolved"

    data = KBEntryUpdate(
        metadata=decision.merged_metadata,
        name=decision.rename_to,
    )
    entry = await kb_service.update(
        novel_id=novel_id,
        entry_id=decision.target_id,
        user_id=user_id,
        data=data,
    )
    updated_entries.append(
        ApplyExtractionEntryResult(
            id=str(entry.id),
            name=entry.name,
            entity_type=entry.entity_type,
        ),
    )
    logger.info(
        "apply_update_entity_updated",
        entry_id=str(entry.id),
        name=item.name,
        renamed_to=decision.rename_to,
    )
    return None
