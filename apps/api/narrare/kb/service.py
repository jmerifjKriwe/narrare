"""KB entry service — business logic.

Orchestrates entry creation, validation, slug generation, reference
resolution, and ownership checks.  Delegates DB operations to the repository.
After create/update, queues embedding generation tasks (non-blocking).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._entry_updates import build_entry_updates
from narrare.kb._reference_resolution import (
    resolve_references as resolve_references_impl,
)
from narrare.kb._validators import resolve_entry_slug, validate_entry_metadata
from narrare_core.shared.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.embedding_hooks import EmbeddingHookManager
    from narrare.kb.lifecycle_dispatcher import KBLifecycleDispatcher
    from narrare.kb.models import KBEntry
    from narrare.kb.schemas import (
        KBEntryCreate,
        KBEntryUpdate,
        ResolveReferencesResponse,
    )
    from narrare.novels.contracts import NovelRepositoryProtocol

logger = structlog.get_logger(__name__)


class KBService:
    """Business logic for KB entries."""

    def __init__(
        self,
        repo: KBRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol | None = None,
        embedding_hooks: EmbeddingHookManager | None = None,
        lifecycle: KBLifecycleDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._novel_repo = novel_repo
        self._embedding_hooks = embedding_hooks
        self._lifecycle = lifecycle

    async def _verify_novel_ownership(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ForbiddenError if the novel does not belong to the user."""
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
        """Create entry — validate metadata, generate slug, check uniqueness."""
        await self._verify_novel_ownership(novel_id, user_id)

        # Validate metadata against core schema registry
        if data.metadata is not None:
            validate_entry_metadata(data.entity_type, data.metadata)

        # Generate slug if not provided
        slug = resolve_entry_slug(data.slug, data.name)

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
            source=data.source,
            review_status=data.review_status,
        )

        entry = await self._repo.create(entry)
        logger.info(
            "kb_entry_created",
            entry_id=str(entry.id),
            novel_id=str(novel_id),
            entity_type=data.entity_type,
        )

        # Queue embedding generation (non-blocking)
        if self._embedding_hooks is not None:
            await self._embedding_hooks.on_entry_created(entry)

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
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]:
        """List entries for a novel with optional filters."""
        await self._verify_novel_ownership(novel_id, user_id)
        return await self._repo.list_entries(
            novel_id,
            entity_type=entity_type,
            tags=tags,
            review_status=review_status,
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
        """Update entry — re-validate metadata, regenerate slug on name change."""
        entry = await self.get(novel_id, entry_id, user_id)
        # Snapshot pre-update identity for ADR-050 P1-B lifecycle dispatch.
        old_name = entry.name
        was_deprecated = entry.status == "deprecated"

        # Field mapping is shared with the canon CRUD path (RULE-04 extraction).
        updates = build_entry_updates(entry, data)

        # Check slug uniqueness if slug changed
        new_slug = updates.get("slug")
        if new_slug is not None and str(new_slug) != entry.slug:
            existing = await self._repo.get_by_slug(novel_id, str(new_slug))
            if existing is not None:
                raise ConflictError(f"An entry with slug '{new_slug}' already exists")

        updated = await self._repo.update(entry, updates)
        logger.info("kb_entry_updated", entry_id=str(entry_id))

        # Queue embedding generation if content changed (non-blocking)
        if self._embedding_hooks is not None:
            content_changed = "body" in updates or "metadata_" in updates
            await self._embedding_hooks.on_entry_updated(
                updated,
                content_changed=content_changed,
            )

        # ADR-050 P1-B: notify cross-feature observers of rename/deprecate.
        if self._lifecycle is not None:
            await self._lifecycle.dispatch_kb_update(
                novel_id=novel_id,
                entity_id=entry_id,
                old_name=old_name,
                was_deprecated=was_deprecated,
                new_name=data.name,
                new_status=data.status,
            )

        return updated

    async def delete(self, novel_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete an entry (raises NotFoundError if not found)."""
        entry = await self.get(novel_id, entry_id, user_id)
        await self._repo.delete(entry)
        logger.info("kb_entry_deleted", entry_id=str(entry_id))

        # ADR-050 P1-B: hard delete stays hard delete — observers surface
        # dangling refs as RefIntegrityIssue (no tombstone column on KBEntry).
        if self._lifecycle is not None:
            await self._lifecycle.notify_deleted(novel_id=novel_id, entity_id=entry_id)

    async def resolve_references(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        text: str,
    ) -> ResolveReferencesResponse:
        """Find all @Name mentions in text and resolve them to KB entries.

        Delegates to :func:`narrare.kb._reference_resolution.resolve_references`
        (RULE-04 extraction). Mentions matching an entry name are linked;
        unmatched mentions are returned without an entry_id.
        """
        await self._verify_novel_ownership(novel_id, user_id)
        return await resolve_references_impl(self._repo, novel_id, text)

    async def autocomplete(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        q: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Auto-complete KB entry names by prefix.

        Returns lightweight dicts with id, name, entity_type, slug.
        """
        await self._verify_novel_ownership(novel_id, user_id)
        entries = await self._repo.search_by_name_prefix(novel_id, q, limit)
        return [
            {"id": str(e.id), "name": e.name, "entity_type": e.entity_type, "slug": e.slug}
            for e in entries
        ]

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
