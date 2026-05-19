"""KB relationship service — business logic.

Orchestrates relationship creation with validation (no self-reference,
uniqueness, entry ownership).  Delegates to repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.kb.relationships import INVERSE_SUGGESTIONS
from narrare_core.shared.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import (
        KBRepositoryProtocol,
        RelationshipRepositoryProtocol,
    )
    from narrare.kb.models import KBRelationship
    from narrare.kb.schemas import KBRelationshipCreate

logger = structlog.get_logger(__name__)


class RelationshipService:
    """Business logic for KB relationships."""

    def __init__(
        self,
        rel_repo: RelationshipRepositoryProtocol,
        entry_repo: KBRepositoryProtocol,
    ) -> None:
        self._rel_repo = rel_repo
        self._entry_repo = entry_repo

    async def create(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBRelationshipCreate,
    ) -> KBRelationship:
        """Create a new relationship.

        Validates both entries exist, belong to the novel, no self-ref,
        and no duplicate.

        Raises:
            NotFoundError: Source or target entry not found.
            ValidationError: Self-referencing relationship.
            ConflictError: Relationship already exists.
        """
        # Validate source entry
        source = await self._entry_repo.get_by_id(data.source_id)
        if source is None or source.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(data.source_id))

        # Validate target entry
        target = await self._entry_repo.get_by_id(data.target_id)
        if target is None or target.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(data.target_id))

        # No self-reference
        if data.source_id == data.target_id:
            raise ValidationError("Self-referencing relationships are not allowed")

        # Check uniqueness
        if await self._rel_repo.exists(data.source_id, data.target_id, data.rel_type):
            raise ConflictError(
                f"Relationship '{data.rel_type}' from {data.source_id} "
                f"to {data.target_id} already exists"
            )

        from narrare.kb.models import KBRelationship

        rel = KBRelationship(
            source_id=data.source_id,
            target_id=data.target_id,
            rel_type=data.rel_type,
            label=data.label,
            direction=data.direction,
            metadata_=data.metadata,
        )

        rel = await self._rel_repo.create(rel)
        logger.info(
            "kb_relationship_created",
            rel_id=str(rel.id),
            source_id=str(data.source_id),
            target_id=str(data.target_id),
            rel_type=data.rel_type,
        )
        return rel

    async def list_for_entry(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[KBRelationship]:
        """List relationships for an entry.

        Validates the entry belongs to the novel.

        Raises:
            NotFoundError: Entry not found.
        """
        entry = await self._entry_repo.get_by_id(entry_id)
        if entry is None or entry.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(entry_id))

        return await self._rel_repo.list_for_entry(entry_id, direction)

    async def delete(self, novel_id: uuid.UUID, rel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a relationship.

        Validates the relationship belongs to an entry in the novel.

        Raises:
            NotFoundError: Relationship not found or not in novel.
        """
        rel = await self._rel_repo.get_by_id(rel_id)
        if rel is None:
            raise NotFoundError("KBRelationship", identifier=str(rel_id))

        # Verify the source entry belongs to the novel
        source = await self._entry_repo.get_by_id(rel.source_id)
        if source is None or source.novel_id != novel_id:
            raise NotFoundError("KBRelationship", identifier=str(rel_id))

        await self._rel_repo.delete(rel)
        logger.info("kb_relationship_deleted", rel_id=str(rel_id))

    def get_inverse_suggestion(self, rel_type: str) -> str | None:
        """Return the suggested inverse relationship type.

        Delegates to core ``INVERSE_SUGGESTIONS`` mapping.
        """
        return INVERSE_SUGGESTIONS.get(rel_type)
