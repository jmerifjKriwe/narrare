"""Extraction Apply Service — saves endorsed extraction items to the KB.

Handles the apply step of KB-007: after the user reviews extraction results
and endorses individual items, this service creates/updates KB entries and
relationships accordingly.

Separated from ExtractionService to keep both files under the 300-line limit
(RULE-04) and to segregate the apply concern (which needs KBService and
RelationshipRepository) from the extraction concern (which needs the LLM
extraction pipeline). Per-item application logic lives in
:mod:`narrare.kb._extraction_apply_entity` and
:mod:`narrare.kb._extraction_apply_relationship` (same RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._extraction_apply_entity import (
    apply_new_entity_item,
    apply_update_entity_item,
)
from narrare.kb._extraction_apply_relationship import apply_relationship_item
from narrare.kb.schemas_extraction import (
    ApplyExtractionEntryResult,
    ApplyExtractionResponse,
    SkippedItem,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.schemas_extraction import ApplyExtractionItem
    from narrare.kb.service import KBService

logger = structlog.get_logger(__name__)


class ExtractionApplyService:
    """Saves endorsed extraction items to the Knowledge Base.

    Iterates over a list of endorsed items and applies each one:
    - ``new_entity`` → Creates a KB entry via KBService
    - ``update_entity`` → Updates an existing KB entry via KBService
    - ``relationship`` → Creates a relationship via RelationshipRepository
    - ``conflict`` → Logged and skipped (user acknowledged)

    Each item is applied inside a SAVEPOINT (benchmark run 5): a failing
    item rolls back only itself, the outer session stays usable, and the
    remaining items proceed — the request-final commit can no longer be
    poisoned by a single item's IntegrityError, so the response's
    created/updated lists match what is actually committed.

    Errors are handled per-item. Every unapplied item (resolution
    failure or exception) is reported in the response's ``skipped``
    list with a machine-readable reason — nothing vanishes silently.
    """

    def __init__(
        self,
        kb_service: KBService,
        rel_repo: RelationshipRepository,
        kb_repo: KBRepositoryProtocol,
        session: AsyncSession,
    ) -> None:
        self._kb_service = kb_service
        self._rel_repo = rel_repo
        self._kb_repo = kb_repo
        self._session = session

    async def apply(
        self,
        novel_id: UUID,
        user_id: UUID,
        items: list[ApplyExtractionItem],
    ) -> ApplyExtractionResponse:
        """Apply all endorsed items, collecting results and skips.

        Args:
            novel_id: Novel to apply items to.
            user_id: Requesting user.
            items: Endorsed extraction items to apply.

        Returns:
            ApplyExtractionResponse with created_entries, updated_entries,
            and every unapplied item in skipped (with reason).
        """
        created_entries: list[ApplyExtractionEntryResult] = []
        updated_entries: list[ApplyExtractionEntryResult] = []
        skipped: list[SkippedItem] = []

        for item in items:
            try:
                # SAVEPOINT per item: on failure only this item's writes
                # roll back; the outer transaction stays usable.
                async with self._session.begin_nested():
                    reason = await self._apply_single_item(
                        novel_id=novel_id,
                        user_id=user_id,
                        item=item,
                        created_entries=created_entries,
                        updated_entries=updated_entries,
                    )
            except Exception as exc:
                logger.error(
                    "apply_item_failed",
                    item_type=item.item_type,
                    name=item.name,
                    error=str(exc),
                    exc_info=True,
                )
                reason = f"exception: {exc}"
            if reason is not None:
                skipped.append(
                    SkippedItem(
                        name=item.name,
                        item_type=item.item_type,
                        reason=reason,
                    ),
                )

        return ApplyExtractionResponse(
            created_entries=created_entries,
            updated_entries=updated_entries,
            skipped=skipped,
        )

    async def _apply_single_item(
        self,
        novel_id: UUID,
        user_id: UUID,
        item: ApplyExtractionItem,
        created_entries: list[ApplyExtractionEntryResult],
        updated_entries: list[ApplyExtractionEntryResult],
    ) -> str | None:
        """Apply a single endorsed extraction item.

        Args:
            novel_id: Novel scope.
            user_id: Requesting user.
            item: The extraction item to apply.
            created_entries: Accumulator for newly created entries.
            updated_entries: Accumulator for updated entries.

        Returns:
            Machine-readable skip reason, or ``None`` when applied.
            Conflict items return ``None`` (acknowledged by design).
        """
        if item.item_type == "new_entity":
            await apply_new_entity_item(
                novel_id=novel_id,
                user_id=user_id,
                item=item,
                kb_service=self._kb_service,
                created_entries=created_entries,
            )
            return None
        if item.item_type == "update_entity":
            return await apply_update_entity_item(
                novel_id=novel_id,
                user_id=user_id,
                item=item,
                kb_repo=self._kb_repo,
                kb_service=self._kb_service,
                updated_entries=updated_entries,
            )
        if item.item_type == "relationship":
            return await self._apply_relationship(novel_id, item, created_entries)
        if item.item_type == "conflict":
            logger.info(
                "conflict_acknowledged",
                name=item.name,
                source_text=item.source_text,
            )
            return None
        logger.warning(
            "unknown_item_type",
            item_type=item.item_type,
            name=item.name,
        )
        return "unknown_item_type"

    async def _apply_relationship(
        self,
        novel_id: UUID,
        item: ApplyExtractionItem,
        created_entries: list[ApplyExtractionEntryResult],
    ) -> str | None:
        """Create a relationship from a ``relationship`` extraction item.

        Predicate validation, endpoint resolution (in-batch creations
        first, then the DB), duplicate acknowledgment, and edge creation
        live in :mod:`narrare.kb._extraction_apply_relationship`;
        unresolvable items are reported as skips — never silently dropped.

        Args:
            novel_id: Novel scope.
            item: The extraction item.
            created_entries: Entries created earlier in this request;
                forwarded so in-batch entity references resolve (Fix C).

        Returns:
            Skip reason, or ``None`` when the relationship was created
            (or already existed — acknowledged duplicate).
        """
        return await apply_relationship_item(
            novel_id=novel_id,
            item=item,
            kb_repo=self._kb_repo,
            rel_repo=self._rel_repo,
            in_batch_creations=created_entries,
        )
