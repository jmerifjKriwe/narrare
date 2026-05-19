"""KB entry service — business logic.

Orchestrates entry creation, validation, slug generation, and
ownership checks.  Delegates DB operations to the repository.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from narrare_core.templates.schema_bridge import validate_metadata

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
    from narrare.novels.contracts import NovelRepositoryProtocol

logger = structlog.get_logger(__name__)


def _slugify(name: str) -> str:
    """Convert a name to a URL-friendly slug.

    Lowercases, replaces whitespace with hyphens, strips special chars,
    and collapses consecutive hyphens.
    """
    slug = re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", name.lower()))
    return re.sub(r"-+", "-", slug).strip("-")


class KBService:
    """Business logic for KB entries."""

    def __init__(
        self,
        repo: KBRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._novel_repo = novel_repo

    async def _verify_novel_ownership(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Verify the novel belongs to the user.

        Raises ForbiddenError if ownership check fails.
        """
        if self._novel_repo is None:
            return

        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise ForbiddenError("You do not have access to this novel")

    async def create(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryCreate,
    ) -> KBEntry:
        """Create a new KB entry.

        Validates metadata, generates slug, checks uniqueness.

        Raises:
            ValidationError: Invalid metadata for entity type.
            ConflictError: Slug already exists in this novel.
            ForbiddenError: Novel not owned by user.
        """
        await self._verify_novel_ownership(novel_id, user_id)

        # Validate metadata against core schema registry
        if data.metadata is not None:
            try:
                validate_metadata(data.entity_type, data.metadata)
            except Exception as exc:
                raise ValidationError(
                    f"Invalid metadata for entity type '{data.entity_type}': {exc}"
                ) from exc

        # Generate slug if not provided
        slug = data.slug or _slugify(data.name)
        if not slug:
            raise ValidationError("Could not generate a valid slug from the name")

        # Check slug uniqueness
        existing = await self._repo.get_by_slug(novel_id, slug)
        if existing is not None:
            raise ConflictError(f"An entry with slug '{slug}' already exists in this novel")

        from narrare.kb.models import KBEntry

        entry = KBEntry(
            novel_id=novel_id,
            entity_type=data.entity_type,
            name=data.name,
            slug=slug,
            status=data.status,
            tags=data.tags,
            metadata_=data.metadata,
            body=data.body or "",
            template_version=data.template_version,
            embeddings_dirty=True,
        )

        entry = await self._repo.create(entry)
        logger.info(
            "kb_entry_created",
            entry_id=str(entry.id),
            novel_id=str(novel_id),
            entity_type=data.entity_type,
        )
        return entry

    async def get(self, novel_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID) -> KBEntry:
        """Get an entry, verifying novel ownership.

        Raises:
            NotFoundError: Entry not found.
            ForbiddenError: Novel not owned by user.
        """
        await self._verify_novel_ownership(novel_id, user_id)
        entry = await self._repo.get_by_id(entry_id)
        if entry is None or entry.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(entry_id))
        return entry

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]:
        """List entries for a novel with optional filters."""
        await self._verify_novel_ownership(novel_id, user_id)
        return await self._repo.list_entries(
            novel_id,
            entity_type=entity_type,
            tags=tags,
            page=page,
            page_size=page_size,
        )

    async def update(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryUpdate,
    ) -> KBEntry:
        """Update an existing entry.

        Re-validates metadata if changed.  Updates slug if name changes.

        Raises:
            NotFoundError: Entry not found.
            ValidationError: Invalid metadata.
            ConflictError: New slug already taken.
        """
        entry = await self.get(novel_id, entry_id, user_id)
        updates: dict[str, object] = {}

        if data.name is not None:
            updates["name"] = data.name
            # Regenerate slug when name changes (unless slug also provided)
            if data.slug is None:
                new_slug = _slugify(data.name)
                if new_slug and new_slug != entry.slug:
                    updates["slug"] = new_slug

        if data.slug is not None:
            updates["slug"] = data.slug

        if data.entity_type is not None:
            updates["entity_type"] = data.entity_type

        if data.status is not None:
            updates["status"] = data.status

        if data.tags is not None:
            updates["tags"] = data.tags

        if data.body is not None:
            updates["body"] = data.body

        if data.template_version is not None:
            updates["template_version"] = data.template_version

        # Re-validate metadata if changed
        effective_type = updates.get("entity_type", entry.entity_type)
        if data.metadata is not None:
            try:
                validate_metadata(str(effective_type), data.metadata)
            except Exception as exc:
                raise ValidationError(
                    f"Invalid metadata for entity type '{effective_type}': {exc}"
                ) from exc
            updates["metadata_"] = data.metadata
            updates["embeddings_dirty"] = True

        # Check slug uniqueness if slug changed
        new_slug = updates.get("slug")
        if new_slug is not None and str(new_slug) != entry.slug:
            existing = await self._repo.get_by_slug(novel_id, str(new_slug))
            if existing is not None:
                raise ConflictError(f"An entry with slug '{new_slug}' already exists")

        updated = await self._repo.update(entry, updates)
        logger.info("kb_entry_updated", entry_id=str(entry_id))
        return updated

    async def delete(self, novel_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete an entry.

        Raises:
            NotFoundError: Entry not found.
        """
        entry = await self.get(novel_id, entry_id, user_id)
        await self._repo.delete(entry)
        logger.info("kb_entry_deleted", entry_id=str(entry_id))

    async def search(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]:
        """Search entries by text query."""
        await self._verify_novel_ownership(novel_id, user_id)
        return await self._repo.search(
            novel_id,
            query,
            entity_type=entity_type,
            tags=tags,
            page=page,
            page_size=page_size,
        )
