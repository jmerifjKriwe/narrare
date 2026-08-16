"""Integration tests for SeriesDriftRepository (C2 — design §12 latest-wins gate).

Real PostgreSQL (rolled-back db_session fixture; schema from the real Alembic
chain — RULE-14). Pins the atomic upsert semantics the design's latest-wins
model rests on: per-section merge, sibling survival, fingerprint/generated_at
refresh, and novel-delete cascade.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select, text

from narrare.novels.models import Novel
from narrare.series.series_drift_contracts import SeriesDriftRepositoryProtocol
from narrare.series.series_drift_models import SeriesDriftResult
from narrare.series.series_drift_repository import SeriesDriftRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_user_and_novel(db_session: AsyncSession) -> Novel:
    """Seed one user + one novel (the novel via ORM — Python-side defaults)."""
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
            "VALUES (:id, :email, 'fake_hash', now(), now())"
        ),
        {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
    )
    novel = Novel(id=uuid.uuid4(), user_id=user_id, title="Repo Test Novel")
    db_session.add(novel)
    await db_session.flush()
    return novel


async def _fetch_row(db_session: AsyncSession) -> SeriesDriftResult:
    return (await db_session.execute(select(SeriesDriftResult))).scalar_one()


class TestStoreSection:
    async def test_first_store_creates_row_with_single_section(
        self, db_session: AsyncSession
    ) -> None:
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "first"},
            fingerprint="f" * 64,
        )

        row = await _fetch_row(db_session)
        assert row.novel_id == novel.id
        assert row.result == {"consistency": {"summary": "first"}}
        assert row.input_fingerprint == "f" * 64
        assert row.generated_at is not None

    async def test_sibling_section_merge_survives_parallel_writes(
        self, db_session: AsyncSession
    ) -> None:
        """The composite-document ruling: each run upserts ONLY its key — the
        sibling section from the other parallel check survives."""
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "c1"},
            fingerprint="a" * 64,
        )
        await repo.store_section(
            novel.id,
            section="voice_drift",
            document={"novel_id": str(novel.id)},
            fingerprint="b" * 64,
        )

        row = await _fetch_row(db_session)
        assert set(row.result.keys()) == {"consistency", "voice_drift"}
        assert row.result["consistency"] == {"summary": "c1"}
        assert row.input_fingerprint == "b" * 64  # latest write wins

    async def test_latest_wins_overwrites_own_section_only(self, db_session: AsyncSession) -> None:
        """Design §12 gate: latest-wins overwrite — a new run of the SAME
        check replaces its section; the sibling section survives and the
        fingerprint + generated_at refresh."""
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "old"},
            fingerprint="a" * 64,
        )
        first_generated_at = (await _fetch_row(db_session)).generated_at
        await repo.store_section(
            novel.id,
            section="voice_drift",
            document={"novel_id": "x"},
            fingerprint="b" * 64,
        )
        await repo.store_section(
            novel.id,
            section="consistency",
            document={"summary": "new"},
            fingerprint="c" * 64,
        )

        row = await _fetch_row(db_session)
        assert row.result["consistency"] == {"summary": "new"}
        assert row.result["voice_drift"] == {"novel_id": "x"}
        assert row.input_fingerprint == "c" * 64
        assert row.generated_at >= first_generated_at

    async def test_get_returns_row_or_none(self, db_session: AsyncSession) -> None:
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)

        assert await repo.get(novel.id) is None

        await repo.store_section(novel.id, section="consistency", document={}, fingerprint="a" * 64)
        row = await repo.get(novel.id)
        assert row is not None and row.novel_id == novel.id


class TestCascade:
    async def test_deleting_novel_removes_snapshot(self, db_session: AsyncSession) -> None:
        novel = await _seed_user_and_novel(db_session)
        repo = SeriesDriftRepository(db_session)
        await repo.store_section(novel.id, section="consistency", document={}, fingerprint="a" * 64)

        await db_session.delete(novel)
        await db_session.flush()

        assert await repo.get(novel.id) is None


def test_repository_exposes_protocol_surface() -> None:
    """Structural check: the repository carries the Protocol's methods."""
    assert issubclass(SeriesDriftRepository, SeriesDriftRepositoryProtocol)
    assert hasattr(SeriesDriftRepository, "get")
    assert hasattr(SeriesDriftRepository, "store_section")
    assert callable(SeriesDriftRepository.store_section)
