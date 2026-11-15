"""Series persistence: the shelf's grouping, user-owned like every row."""

from uuid import UUID

import pytest

from app.capabilities.writing.repository import NovelRepository, SeriesRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


async def test_series_round_trips_through_the_database() -> None:
    async with Session() as session:
        series = await SeriesRepository(session, LOCAL_USER_ID).create("Die Nebel-Chroniken")
        await session.commit()

    # A second session: the read hits the database, not the identity map.
    async with Session() as session:
        reread = await SeriesRepository(session, LOCAL_USER_ID).get(series.id)
        assert reread is not None
        assert reread.title == "Die Nebel-Chroniken"
        assert reread.user_id == LOCAL_USER_ID
        assert reread.created_at.tzinfo is not None


async def test_another_users_series_is_not_found() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = await SeriesRepository(session, OTHER_USER).create("Fremde Reihe")
        await session.commit()

    async with Session() as session:
        assert await SeriesRepository(session, LOCAL_USER_ID).get(foreign.id) is None


async def test_a_new_novel_carries_no_shelf_answers() -> None:
    async with Session() as session:
        novel = await NovelRepository(session, LOCAL_USER_ID).create("Blank")
        await session.commit()

    async with Session() as session:
        reread = await NovelRepository(session, LOCAL_USER_ID).get(novel.id)
        assert reread is not None
        assert reread.status is None
        assert reread.series_id is None
        assert reread.series_volume is None
        assert reread.archived_at is None


async def test_deleting_a_series_unlinks_its_books() -> None:
    """The foreign key is SET NULL: a series going away ungroups its
    books, it does not take them with it."""
    async with Session() as session:
        series = await SeriesRepository(session, LOCAL_USER_ID).create("Die Nebel-Chroniken")
        novel = await NovelRepository(session, LOCAL_USER_ID).create("Band Eins")
        novel.series_id = series.id
        await session.commit()

    async with Session() as session:
        stored = await SeriesRepository(session, LOCAL_USER_ID).get(series.id)
        assert stored is not None
        await session.delete(stored)
        await session.commit()

    async with Session() as session:
        reread = await NovelRepository(session, LOCAL_USER_ID).get(novel.id)
        assert reread is not None
        assert reread.series_id is None
