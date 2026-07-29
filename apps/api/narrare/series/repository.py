"""Series repository — DB queries for Series + SeriesSettings (RULE-06).

Implements ``SeriesRepositoryProtocol`` (contracts.py). Query-only: no
business decisions. Returns Core Pydantic types (``narrare_core.series``)
via the ``_to_core_*`` converters so services never touch ORM models.

1:1 invariant: ``create`` always inserts an empty ``SeriesSettings`` row in
the same flush as the Series (the settings FK needs the Series id, which is
generated client-side here so both rows can be added before flushing).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.novels.models import Novel
from narrare.series.models import Series as SeriesModel
from narrare.series.models import SeriesSettings as SeriesSettingsModel
from narrare_core.series.schemas import Series, SeriesSettings


def _to_core_series(model: SeriesModel) -> Series:
    """Map an ORM ``Series`` row to the Core ``Series`` Pydantic type."""
    return Series.model_validate(model, from_attributes=True)


def _to_core_settings(model: SeriesSettingsModel) -> SeriesSettings:
    """Map an ORM ``SeriesSettings`` row to the Core ``SeriesSettings`` type."""
    return SeriesSettings.model_validate(model, from_attributes=True)


class SeriesRepository(BaseRepository):
    """DB-query surface for Series, SeriesSettings and novels-in-series."""

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
        """Insert a new Series (status defaults to draft) + empty settings."""
        new_id = uuid.uuid4()
        series = SeriesModel(
            id=new_id,
            user_id=user_id,
            title=title,
            subtitle=subtitle,
            description=description,
            genre=genre,
            writing_language=writing_language,
            planned_novel_count=planned_novel_count,
        )
        # 1:1 invariant: create the empty settings row in the same flush.
        settings = SeriesSettingsModel(series_id=new_id)
        self._session.add(series)
        self._session.add(settings)
        await self._flush_and_refresh(series)
        return _to_core_series(series)

    async def get(self, series_id: uuid.UUID) -> Series | None:
        """Load a single Series by ID (no ownership check)."""
        model = await self._get_orm(series_id)
        return _to_core_series(model) if model is not None else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[Series]:
        """List all Series owned by ``user_id``, newest update first."""
        result = await self._session.execute(
            select(SeriesModel)
            .where(SeriesModel.user_id == user_id)
            .order_by(SeriesModel.updated_at.desc())
        )
        return [_to_core_series(model) for model in result.scalars()]

    async def update(self, series_id: uuid.UUID, **patch: object) -> Series | None:
        """Patch mutable columns; returns updated Series or None if missing."""
        model = await self._get_orm(series_id)
        if model is None:
            return None
        for field, value in patch.items():
            setattr(model, field, value)
        await self._flush_and_refresh(model)
        return _to_core_series(model)

    async def delete(self, series_id: uuid.UUID) -> bool:
        """Delete a Series; True on success, False if not found."""
        model = await self._get_orm(series_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._flush()
        return True

    async def list_novels(self, series_id: uuid.UUID) -> list[Novel]:
        """Novels in series ordered by ``series_position`` ascending."""
        result = await self._session.execute(
            select(Novel).where(Novel.series_id == series_id).order_by(Novel.series_position.asc())
        )
        return list(result.scalars())

    async def reorder_novels(self, series_id: uuid.UUID, novel_ids: list[uuid.UUID]) -> None:
        """Reassign sequential ``series_position`` (1..N) to given novels.

        Loads the series' novels once, then maps each requested id to its
        1-based position in ``novel_ids``. Ids not in the series are skipped
        (the scope is enforced by the load's ``series_id`` filter).
        """
        result = await self._session.execute(select(Novel).where(Novel.series_id == series_id))
        by_id = {novel.id: novel for novel in result.scalars()}
        for position, novel_id in enumerate(novel_ids, start=1):
            novel = by_id.get(novel_id)
            if novel is not None:
                novel.series_position = position
        await self._flush()

    async def get_settings(self, series_id: uuid.UUID) -> SeriesSettings | None:
        """Load SeriesSettings for a series (None if no row yet)."""
        model = await self._get_settings_orm(series_id)
        return _to_core_settings(model) if model is not None else None

    async def update_settings(
        self, series_id: uuid.UUID, patch: dict[str, object]
    ) -> SeriesSettings:
        """Patch SeriesSettings columns; creates row on demand if missing."""
        model = await self._get_settings_orm(series_id)
        if model is None:
            model = SeriesSettingsModel(series_id=series_id)
            self._session.add(model)
        for field, value in patch.items():
            setattr(model, field, value)
        await self._flush_and_refresh(model)
        return _to_core_settings(model)

    # -- internal ORM loaders (return ORM rows, not Core types) -------------

    async def _get_orm(self, series_id: uuid.UUID) -> SeriesModel | None:
        result = await self._session.execute(select(SeriesModel).where(SeriesModel.id == series_id))
        return result.scalar_one_or_none()

    async def _get_settings_orm(self, series_id: uuid.UUID) -> SeriesSettingsModel | None:
        result = await self._session.execute(
            select(SeriesSettingsModel).where(SeriesSettingsModel.series_id == series_id)
        )
        return result.scalar_one_or_none()
