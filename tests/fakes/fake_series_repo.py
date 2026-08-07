"""Fake series repository for unit tests.

In-memory implementation of ``SeriesRepositoryProtocol`` — used by
``SeriesService`` unit tests (no DB). Mirrors ``FakeNovelRepository``.

Stores Core ``Series`` Pydantic instances (the same type the real
``SeriesRepository`` returns) so the service sees realistic data.
"""

from __future__ import annotations

import uuid
from typing import Any

from narrare_core.series.schemas import NovelRow, Series, SeriesSettings
from tests.fakes._shared import CallRecord


class FakeSeriesRepository:
    """In-memory fake for ``SeriesRepositoryProtocol``.

    Series are keyed by id. Novels (arbitrary objects) are stored per series
    so ``list_novels`` can return a count the service computes.
    """

    def __init__(self) -> None:
        self._series: dict[uuid.UUID, Series] = {}
        self._novels: dict[uuid.UUID, list[Any]] = {}
        self._settings: dict[uuid.UUID, SeriesSettings] = {}
        self.calls: list[CallRecord] = []

    def seed(
        self,
        *series: Series,
        novels: list[Any] | None = None,
    ) -> None:
        """Pre-populate the fake with Series (and optional novels)."""
        for s in series:
            self._series[s.id] = s
            self._novels[s.id] = list(novels) if novels is not None else []
            self._settings.setdefault(s.id, SeriesSettings(series_id=s.id, author_voice=None))

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        subtitle: str | None,
        description: str | None,
        genre: str | None,
        writing_language: str | None,
        planned_novel_count: int | None,
    ) -> Series:
        self.calls.append(
            CallRecord(
                "create",
                kwargs={
                    "user_id": user_id,
                    "title": title,
                    "subtitle": subtitle,
                    "planned_novel_count": planned_novel_count,
                },
            )
        )
        new_id = uuid.uuid4()
        series = Series(
            id=new_id,
            user_id=user_id,
            title=title,
            subtitle=subtitle,
            description=description,
            genre=genre,
            writing_language=writing_language,
            status="draft",
            planned_novel_count=planned_novel_count,
        )
        self._series[new_id] = series
        self._novels[new_id] = []
        self._settings[new_id] = SeriesSettings(series_id=new_id, author_voice=None)
        return series

    async def get(self, series_id: uuid.UUID) -> Series | None:
        self.calls.append(CallRecord("get", kwargs={"series_id": series_id}))
        return self._series.get(series_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Series]:
        self.calls.append(CallRecord("list_for_user", kwargs={"user_id": user_id}))
        return [s for s in self._series.values() if s.user_id == user_id]

    async def update(self, series_id: uuid.UUID, **patch: object) -> Series | None:
        self.calls.append(CallRecord("update", kwargs={"series_id": series_id, **patch}))
        existing = self._series.get(series_id)
        if existing is None:
            return None
        updated = existing.model_copy(update=patch)
        self._series[series_id] = updated
        return updated

    async def delete(self, series_id: uuid.UUID) -> bool:
        self.calls.append(CallRecord("delete", kwargs={"series_id": series_id}))
        removed = self._series.pop(series_id, None)
        self._novels.pop(series_id, None)
        self._settings.pop(series_id, None)
        return removed is not None

    async def list_novels(self, series_id: uuid.UUID) -> list[NovelRow]:
        """Novels in series as Core ``NovelRow`` value objects (I-A2)."""
        self.calls.append(CallRecord("list_novels", kwargs={"series_id": series_id}))
        return [NovelRow.model_validate(n) for n in self._novels.get(series_id, [])]

    async def count_novels(self, series_id: uuid.UUID) -> int:
        """Count novels in a series (I-B3 N+1 fix — no row materialisation)."""
        self.calls.append(CallRecord("count_novels", kwargs={"series_id": series_id}))
        return len(self._novels.get(series_id, []))

    async def count_novels_per_series(self, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """``GROUP BY series_id`` novel counts for every series of ``user_id``."""
        self.calls.append(CallRecord("count_novels_per_series", kwargs={"user_id": user_id}))
        return {
            sid: len(novels)
            for sid, novels in self._novels.items()
            if sid in self._series and self._series[sid].user_id == user_id
        }

    async def delete_canon_for_series(self, series_id: uuid.UUID) -> int:
        """Fake has no KB rows — records the call, returns 0 rows deleted."""
        self.calls.append(CallRecord("delete_canon_for_series", kwargs={"series_id": series_id}))
        return 0

    async def detach_overlay_series_id(self, novel_id: uuid.UUID, series_id: uuid.UUID) -> int:
        """Fake has no KB rows — records the call, returns 0 rows updated (T7)."""
        self.calls.append(
            CallRecord(
                "detach_overlay_series_id",
                kwargs={"novel_id": novel_id, "series_id": series_id},
            )
        )
        return 0

    async def reorder_novels(self, series_id: uuid.UUID, novel_ids: list[uuid.UUID]) -> None:
        self.calls.append(CallRecord("reorder_novels", kwargs={"series_id": series_id}))

    async def get_settings(self, series_id: uuid.UUID) -> SeriesSettings | None:
        self.calls.append(CallRecord("get_settings", kwargs={"series_id": series_id}))
        return self._settings.get(series_id)

    async def update_settings(
        self, series_id: uuid.UUID, patch: dict[str, object]
    ) -> SeriesSettings:
        self.calls.append(CallRecord("update_settings", kwargs={"series_id": series_id}))
        existing = self._settings.get(series_id)
        if existing is None:
            existing = SeriesSettings(series_id=series_id, author_voice=None)
        updated = existing.model_copy(update=patch)
        self._settings[series_id] = updated
        return updated

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)
