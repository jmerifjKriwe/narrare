"""The update check suite's fixtures: the shared database and a release source.

The release source is the shared test harness
(``app/kernel/testing/release_vendor.py``), a real local HTTP server the E2E
suite uses too. The URL and the cache TTL are environment configuration, so the
fixtures point them at that server and the cache at zero — except the one test
that proves the cache.
"""

from asyncio import run
from collections.abc import AsyncIterator, Iterator  # noqa: TC003
from uuid import UUID  # noqa: TC003

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.user import User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import test_database, url_for
from app.kernel.testing.release_vendor import ReleaseVendor

DATABASE = test_database()

RELEASE = {
    "tag": "v999.0.0",
    "notes": "## Notes\n\n- new",
    "url": "https://example.test/release",
}


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Rebuild the schema from the models: what the tests see is the source."""
    from app.kernel.db.init import reset_schema

    run(reset_schema(url_for(DATABASE)))


@pytest.fixture(autouse=True)
async def installed(schema: None) -> None:
    """An installed instance: one local user row, and no state it left behind."""
    async with Session() as session:
        await session.execute(text("TRUNCATE users CASCADE"))
        session.add(User(id=LOCAL_USER_ID))
        await session.commit()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session


@pytest.fixture
def user() -> UUID:
    return LOCAL_USER_ID


@pytest.fixture(autouse=True)
def _empty_release_cache() -> Iterator[None]:
    """The module cache outlives a test; no test starts inside another's answer."""
    from app.kernel.updates.service import reset_cache

    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def vendor(monkeypatch: pytest.MonkeyPatch) -> Iterator[ReleaseVendor]:
    """A newer release on the shared local source, with the cache disabled."""
    with ReleaseVendor(**RELEASE) as vendor:
        monkeypatch.setenv("NARRA_UPDATE_CHECK_URL", vendor.base_url)
        monkeypatch.setenv("NARRA_UPDATE_CHECK_CACHE_SECONDS", "0")
        yield vendor
