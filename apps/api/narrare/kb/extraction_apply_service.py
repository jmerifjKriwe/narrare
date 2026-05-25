"""Extraction Apply Service — saves endorsed extraction items to the KB.

Handles the apply step of KB-007: after the user reviews extraction results
and endorses individual items, this service creates/updates KB entries and
relationships accordingly.

Separated from ExtractionService to keep both files under the 300-line limit
(RULE-04) and to segregate the apply concern (which needs KBService and
RelationshipRepository) from the extraction concern (which needs the LLM
extraction pipeline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.kb.schemas import (
    KBEntryCreate,
    KBEntryUpdate,
)
from narrare.kb.schemas_extraction import (
    ApplyExtractionEntryResult,
    ApplyExtractionResponse,
)

if TYPE_CHECKING:
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

    Errors are handled per-item — a single failing item does not
    block the remaining items.
    """

    def __init__(
        self,
        kb_service: KBService,
        rel_repo: RelationshipRepository,
        kb_repo: KBRepositoryProtocol,
    ) -> None:
        self._kb_service = kb_service
        self._rel_repo = rel_repo
        self._kb_repo = kb_repo

    async def apply(
        self,
        novel_id: UUID,
        user_id: UUID,
        items: list[ApplyExtractionItem],
    ) -> ApplyExtractionResponse:
        """Apply all endorsed items, collecting results.

        Args:
            novel_id: Novel to apply items to.
            user_id: Requesting user.
            items: Endorsed extraction items to apply.

        Returns:
            ApplyExtractionResponse with created_entries and updated_entries.
        """
        created_entries: list[ApplyExtractionEntryResult] = []
        updated_entries: list[ApplyExtractionEntryResult] = []

        for item in items:
            try:
                await self._apply_single_item(
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
                continue

        return ApplyExtractionResponse(
            created_entries=created_entries,
            updated_entries=updated_entries,
        )

    async def _apply_single_item(
        self,
        novel_id: UUID,
        user_id: UUID,
        item: ApplyExtractionItem,
        created_entries: list[ApplyExtractionEntryResult],
        updated_entries: list[ApplyExtractionEntryResult],
    ) -> None:
        """Apply a single endorsed extraction item.

        Args:
            novel_id: Novel scope.
            user_id: Requesting user.
            item: The extraction item to apply.
            created_entries: Accumulator for newly created entries.
            updated_entries: Accumulator for updated entries.
        """
        if item.item_type == "new_entity":
            await self._apply_new_entity(
                novel_id,
                user_id,
                item,
                created_entries,
            )
        elif item.item_type == "update_entity":
            await self._apply_update_entity(
                novel_id,
                user_id,
                item,
                updated_entries,
            )
        elif item.item_type == "relationship":
            await self._apply_relationship(novel_id, item)
        elif item.item_type == "conflict":
            logger.info(
                "conflict_acknowledged",
                name=item.name,
                source_text=item.source_text,
            )
        else:
            logger.warning(
                "unknown_item_type",
                item_type=item.item_type,
                name=item.name,
            )

    async def _apply_new_entity(
        self,
        novel_id: UUID,
        user_id: UUID,
        item: ApplyExtractionItem,
        created_entries: list[ApplyExtractionEntryResult],
    ) -> None:
        """Create a new KB entry from a ``new_entity`` extraction item.

        Args:
            novel_id: Novel scope.
            user_id: Requesting user.
            item: The extraction item.
            created_entries: Accumulator for results.
        """
        data = KBEntryCreate(
            entity_type=item.entity_type or "unknown",
            name=item.name,
            metadata=item.proposed_content,
            body=item.source_text,
            status="draft",
        )
        entry = await self._kb_service.create(
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

    async def _apply_update_entity(
        self,
        novel_id: UUID,
        user_id: UUID,
        item: ApplyExtractionItem,
        updated_entries: list[ApplyExtractionEntryResult],
    ) -> None:
        """Update an existing KB entry from an ``update_entity`` item.

        Args:
            novel_id: Novel scope.
            user_id: Requesting user.
            item: The extraction item.
            updated_entries: Accumulator for results.
        """
        if not item.target_entity_id:
            logger.warning(
                "update_entity_missing_target_id",
                name=item.name,
            )
            return

        target_id = UUID(item.target_entity_id)

        data = KBEntryUpdate(
            metadata=item.proposed_content,
        )
        entry = await self._kb_service.update(
            novel_id=novel_id,
            entry_id=target_id,
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
        )

    async def _apply_relationship(
        self,
        novel_id: UUID,
        item: ApplyExtractionItem,
    ) -> None:
        """Create a relationship from a ``relationship`` extraction item.

        Looks up source and target entities by name within the novel.

        Args:
            novel_id: Novel scope.
            item: The extraction item.
        """
        if not item.related_entity_name or not item.relationship_type:
            logger.warning(
                "relationship_missing_fields",
                name=item.name,
                related_entity_name=item.related_entity_name,
                relationship_type=item.relationship_type,
            )
            return

        # Look up source and target entities by name in the novel
        source_entry = await self._kb_repo.get_by_name(novel_id, item.name)
        if source_entry is None:
            logger.warning(
                "relationship_source_not_found",
                name=item.name,
                novel_id=str(novel_id),
            )
            return

        target_entry = await self._kb_repo.get_by_name(
            novel_id,
            item.related_entity_name,
        )
        if target_entry is None:
            logger.warning(
                "relationship_target_not_found",
                name=item.related_entity_name,
                novel_id=str(novel_id),
            )
            return

        from narrare.kb.models import KBRelationship

        rel = KBRelationship(
            source_id=source_entry.id,
            target_id=target_entry.id,
            rel_type=item.relationship_type,
        )
        await self._rel_repo.create(rel)
        logger.info(
            "apply_relationship_created",
            source=item.name,
            target=item.related_entity_name,
            rel_type=item.relationship_type,
        )
