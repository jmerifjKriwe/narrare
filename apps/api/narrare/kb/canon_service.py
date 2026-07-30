"""KBCanonService — Series-Canon KB CRUD (Series Foundation Spec 1, Task 3.8).

Business logic for the Canon half of the ``kb_entries`` scope split: create /
read / update / delete of entries where ``novel_id IS NULL`` (shared across all
novels of a series). Reuses the generic :class:`KBRepository` CRUD surface —
the only Canon-specific aspects are the scope invariant (``novel_id IS NULL``)
and series-ownership verification.

The service never touches HTTP or raw SQL (RULE-06): DB operations are
delegated to ``KBRepositoryProtocol`` (Task 2.2) and series ownership to
``SeriesRepositoryProtocol``. Domain errors (:class:`NotFoundError`,
:class:`ForbiddenError`, :class:`ConflictError`) are raised here and mapped to
HTTP by the global ``NarrareError`` handler in ``_app/main.py`` (404 / 403 /
409), so the router stays free of error-translation logic.

Field-mapping on update is shared with the novel CRUD via
:func:`narrare.kb._entry_updates.build_entry_updates` (DRY, RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._entry_updates import build_entry_updates
from narrare.kb._validators import resolve_entry_slug, validate_entry_metadata
from narrare_core.kb.schemas.entry import SeriesKBEntry
from narrare_core.shared.errors import ConflictError, ForbiddenError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
    from narrare.series.contracts import SeriesRepositoryProtocol

logger = structlog.get_logger(__name__)


class KBCanonService:
    """Business logic for Series-Canon KB entries (``novel_id IS NULL``).

    Depends on the KB repository (CRUD + canon scope lookups) and the series
    repository (ownership). All dependencies are injected via ``__init__``.
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol,
        series_repo: SeriesRepositoryProtocol,
    ) -> None:
        self._kb_repo = kb_repo
        self._series_repo = series_repo

    # -- ownership -------------------------------------------------------

    async def _verify_series_ownership(self, series_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ``ForbiddenError`` if the series is missing or not owned.

        Mirrors the novel CRUD's anti-enumeration stance
        (:meth:`KBService._verify_novel_ownership`): a missing series and a
        not-owned series both surface as 403 so series ids are not enumerable.
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")

    async def _load_canon(
        self, series_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> KBEntry:
        """Load a canon entry, verifying ownership + the canon scope invariant.

        Raises:
            ForbiddenError: Series missing or not owned by ``user_id`` (403).
            NotFoundError: Entry missing, not canon (``novel_id IS NOT NULL``),
                or canon of a *different* series (404).
        """
        await self._verify_series_ownership(series_id, user_id)
        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None or entry.novel_id is not None or entry.series_id != series_id:
            raise NotFoundError("KBEntry", identifier=str(entry_id))
        return entry

    # -- read ------------------------------------------------------------

    async def list_canon(self, series_id: uuid.UUID, user_id: uuid.UUID) -> list[SeriesKBEntry]:
        """List all Series-Canon entries for a series."""
        await self._verify_series_ownership(series_id, user_id)
        return await self._kb_repo.find_canon_for_series(series_id)

    async def get_canon(
        self, series_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesKBEntry:
        """Get a single Series-Canon entry."""
        entry = await self._load_canon(series_id, entry_id, user_id)
        return self._to_series(entry)

    # -- create ----------------------------------------------------------

    async def create_canon(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryCreate,
    ) -> SeriesKBEntry:
        """Create a new Series-Canon entry (``novel_id=None``)."""
        await self._verify_series_ownership(series_id, user_id)

        if data.metadata is not None:
            validate_entry_metadata(data.entity_type, data.metadata)

        slug = resolve_entry_slug(data.slug, data.name)

        if await self._kb_repo.find_canon_by_slug(series_id, slug) is not None:
            raise ConflictError(f"An entry with slug '{slug}' already exists in this series")

        from narrare.kb.models import KBEntry

        entry = KBEntry(
            novel_id=None,
            series_id=series_id,
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

        created = await self._kb_repo.create(entry)
        logger.info(
            "kb_canon_created",
            entry_id=str(created.id),
            series_id=str(series_id),
            entity_type=data.entity_type,
        )
        return self._to_series(created)

    # -- update ----------------------------------------------------------

    async def update_canon(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryUpdate,
    ) -> SeriesKBEntry:
        """Update a Series-Canon entry."""
        entry = await self._load_canon(series_id, entry_id, user_id)
        updates = build_entry_updates(entry, data)

        # Canon-scoped slug uniqueness check.
        new_slug = updates.get("slug")
        if (
            new_slug is not None
            and str(new_slug) != entry.slug
            and await self._kb_repo.find_canon_by_slug(series_id, str(new_slug)) is not None
        ):
            raise ConflictError(f"An entry with slug '{new_slug}' already exists")

        updated = await self._kb_repo.update(entry, updates)
        logger.info("kb_canon_updated", entry_id=str(entry_id))
        return self._to_series(updated)

    # -- delete ----------------------------------------------------------

    async def delete_canon(
        self, series_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a Series-Canon entry."""
        entry = await self._load_canon(series_id, entry_id, user_id)
        await self._kb_repo.delete(entry)
        logger.info("kb_canon_deleted", entry_id=str(entry_id))

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _to_series(entry: KBEntry) -> SeriesKBEntry:
        """Map an ORM canon row to the Core ``SeriesKBEntry`` value object.

        Validates the canon invariant at the type boundary (``novel_id IS
        NULL``), so an overlay row reaching here is a programmer error, not a
        404 (the scope check happens earlier in :meth:`_load_canon`).
        """
        return SeriesKBEntry.model_validate(entry, from_attributes=True)
