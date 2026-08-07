"""In-memory fake for the KB scope surface ``SeriesJoinService`` consumes.

The shared :class:`~tests.fakes.fake_kb_repo.FakeKBRepository` stores ORM
``KBEntry`` rows and does not implement the scope methods. The join service,
however, consumes the **Core** Pydantic types (``NovelKBEntry`` /
``SeriesKBEntry``) that the real ``KBRepository`` scope methods return. This
focused fake mirrors that surface so the join-service unit tests see
realistic data (ADR-030: a real fake, not ``MagicMock``).

Only the three methods ``SeriesJoinService`` calls are implemented:
``find_canon_for_series``, ``find_overlay_for_novel``, ``promote_to_canon``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare_core.kb.schemas.entry import SeriesKBEntry
from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare_core.kb.schemas.entry import NovelKBEntry


class FakeJoinKBRepo:
    """In-memory fake for the KB scope surface used by ``SeriesJoinService``."""

    def __init__(self) -> None:
        self._canon: dict[uuid.UUID, list[SeriesKBEntry]] = {}
        self._overlay: dict[uuid.UUID, list[NovelKBEntry]] = {}
        self.calls: list[CallRecord] = []
        self.promoted: list[tuple[uuid.UUID, uuid.UUID]] = []
        self._fail_promote_on: int | None = None
        self._promote_count = 0

    # -- seeders --
    def seed_canon(self, series_id: uuid.UUID, entries: list[SeriesKBEntry]) -> None:
        """Pre-populate the Series-Canon entries for a series."""
        self._canon[series_id] = list(entries)

    def seed_overlay(self, novel_id: uuid.UUID, entries: list[NovelKBEntry]) -> None:
        """Pre-populate the Novel-Overlay entries for a novel."""
        self._overlay[novel_id] = list(entries)

    def fail_on_promote(self, n: int) -> None:
        """Make the Nth ``promote_to_canon`` call raise (1-based)."""
        self._fail_promote_on = n

    # -- protocol surface --
    async def find_canon_for_series(self, series_id: uuid.UUID) -> list[SeriesKBEntry]:
        self.calls.append(CallRecord("find_canon_for_series", kwargs={"series_id": series_id}))
        return list(self._canon.get(series_id, []))

    async def find_overlay_for_novel(self, novel_id: uuid.UUID) -> list[NovelKBEntry]:
        self.calls.append(CallRecord("find_overlay_for_novel", kwargs={"novel_id": novel_id}))
        return list(self._overlay.get(novel_id, []))

    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry:
        self.calls.append(
            CallRecord("promote_to_canon", kwargs={"novel_id": novel_id, "entry_id": entry_id})
        )
        self._promote_count += 1
        if self._fail_promote_on is not None and self._promote_count >= self._fail_promote_on:
            raise RuntimeError("promote_to_canon failed (simulated)")
        self.promoted.append((novel_id, entry_id))
        entry = next(e for e in self._overlay.get(novel_id, []) if e.id == entry_id)
        return SeriesKBEntry(
            id=entry.id,
            entity_type=entry.entity_type,
            name=entry.name,
            slug=entry.slug,
            series_id=uuid4(),  # the series it now belongs to
        )
