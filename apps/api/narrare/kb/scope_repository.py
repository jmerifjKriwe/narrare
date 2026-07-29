"""KB scope-aware repository methods — Series Foundation Spec 1 (Task 2.2).

Scope-aware queries and promote/demote mutations for KB entries, plus the
ORM→Core type converters. Extracted from ``repository.py`` to respect the
RULE-04 250-line file-size limit for ``repository.py`` (the five methods plus
two converters would push it past the limit).

``KBRepository`` inherits this class, so the methods remain part of the single
``KBRepositoryProtocol`` surface (RULE-03 contract first). The class extends
``BaseRepository`` for the shared ``_session`` / ``_flush`` utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.kb.models import KBEntry
from narrare.novels.models import Novel
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry

if TYPE_CHECKING:
    import uuid


class KBScopeRepository(BaseRepository):
    """Scope-aware KB queries, inherited by :class:`KBRepository` (RULE-04 split)."""

    async def find_canon_for_series(self, series_id: uuid.UUID) -> list[SeriesKBEntry]:
        """All Series-Canon entries for a series (``novel_id IS NULL``)."""
        result = await self._session.execute(
            select(KBEntry).where(
                KBEntry.series_id == series_id,
                KBEntry.novel_id.is_(None),
            )
        )
        return [self._to_series_kb_entry(e) for e in result.scalars()]

    async def find_overlay_for_novel(self, novel_id: uuid.UUID) -> list[NovelKBEntry]:
        """All Novel-Overlay entries for a novel (``novel_id = X``)."""
        result = await self._session.execute(select(KBEntry).where(KBEntry.novel_id == novel_id))
        return [self._to_novel_kb_entry(e) for e in result.scalars()]

    async def find_merged_for_novel(
        self, novel_id: uuid.UUID
    ) -> list[NovelKBEntry | SeriesKBEntry]:
        """Canon of parent series + Overlay of novel, merged (Overlay wins on slug).

        For a standalone novel (no series) only its overlays are returned; the
        canon query is skipped so no extra DB round-trip occurs.
        """
        novel_result = await self._session.execute(
            select(Novel.series_id).where(Novel.id == novel_id)
        )
        series_id = novel_result.scalar_one_or_none()

        # Skip the canon query entirely when the novel is not in a series.
        canon = await self.find_canon_for_series(series_id) if series_id else []
        overlay = await self.find_overlay_for_novel(novel_id)

        merged: dict[str, NovelKBEntry | SeriesKBEntry] = {e.slug: e for e in canon}
        for e in overlay:
            merged[e.slug] = e  # overlay wins on slug collision
        return list(merged.values())

    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry:
        """Promote a Novel-Overlay to Series-Canon."""
        entry = await self._get_kb_entry(entry_id)
        if entry is None or entry.novel_id != novel_id:
            raise ValueError(f"Entry {entry_id} not found or not overlay of novel {novel_id}")

        novel_result = await self._session.execute(select(Novel).where(Novel.id == novel_id))
        novel_obj = novel_result.scalar_one_or_none()
        if novel_obj is None or novel_obj.series_id is None:
            raise ValueError(f"Novel {novel_id} not in a series")

        entry.novel_id = None
        entry.series_id = novel_obj.series_id
        entry.base_entry_id = None
        await self._flush()
        return self._to_series_kb_entry(entry)

    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
    ) -> NovelKBEntry:
        """Demote a Series-Canon to Novel-Overlay for ``target_novel_id``."""
        entry = await self._get_kb_entry(entry_id)
        if entry is None or entry.series_id != series_id or entry.novel_id is not None:
            raise ValueError(f"Entry {entry_id} not found or not canon of series {series_id}")

        entry.novel_id = target_novel_id
        entry.base_entry_id = None
        await self._flush()
        return self._to_novel_kb_entry(entry)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _get_kb_entry(self, entry_id: uuid.UUID) -> KBEntry | None:
        """Fetch a single KB entry by id (scope-repo-local lookup)."""
        result = await self._session.execute(select(KBEntry).where(KBEntry.id == entry_id))
        return result.scalar_one_or_none()

    def _to_series_kb_entry(self, model: KBEntry) -> SeriesKBEntry:
        """Convert an ORM row to a Core ``SeriesKBEntry`` (canon scope)."""
        # Canon invariant (ck_kb_entries_scope_invariant): series_id IS NOT NULL.
        assert model.series_id is not None
        return SeriesKBEntry(
            id=model.id,
            entity_type=model.entity_type,
            name=model.name,
            slug=model.slug,
            status=model.status,
            body=model.body,
            metadata_=model.metadata_,
            tags=model.tags,
            template_version=model.template_version,
            source=model.source,
            review_status=model.review_status,
            embeddings_dirty=model.embeddings_dirty,
            last_referenced_at=model.last_referenced_at,
            usage_count=model.usage_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            series_id=model.series_id,
        )

    def _to_novel_kb_entry(self, model: KBEntry) -> NovelKBEntry:
        """Convert an ORM row to a Core ``NovelKBEntry`` (overlay scope)."""
        # Overlay invariant (ck_kb_entries_scope_invariant): novel_id IS NOT NULL.
        assert model.novel_id is not None
        return NovelKBEntry(
            id=model.id,
            entity_type=model.entity_type,
            name=model.name,
            slug=model.slug,
            status=model.status,
            body=model.body,
            metadata_=model.metadata_,
            tags=model.tags,
            template_version=model.template_version,
            source=model.source,
            review_status=model.review_status,
            embeddings_dirty=model.embeddings_dirty,
            last_referenced_at=model.last_referenced_at,
            usage_count=model.usage_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            novel_id=model.novel_id,
            series_id=model.series_id,
            base_entry_id=model.base_entry_id,
        )
