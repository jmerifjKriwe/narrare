"""Novel metadata: author and language round-trip through the database."""

import pytest

from app.capabilities.writing.repository import NovelRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)


async def test_novel_carries_author_and_language() -> None:
    async with Session() as session:
        novel = await NovelRepository(session, LOCAL_USER_ID).create(
            "Im stillen Wald", author="J. Autorin", language="de"
        )
        await session.commit()

    # A second session: the read hits the database, not the identity map.
    async with Session() as session:
        reread = await NovelRepository(session, LOCAL_USER_ID).get(novel.id)
        assert reread is not None
        assert (reread.author, reread.language) == ("J. Autorin", "de")


async def test_novel_metadata_defaults_to_none() -> None:
    async with Session() as session:
        novel = await NovelRepository(session, LOCAL_USER_ID).create("Blank")
        await session.commit()

    async with Session() as session:
        reread = await NovelRepository(session, LOCAL_USER_ID).get(novel.id)
        assert reread is not None
        assert reread.author is None and reread.language is None
