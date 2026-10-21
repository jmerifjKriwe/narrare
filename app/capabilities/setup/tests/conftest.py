"""Setup suite fixtures, pointing at the shared throwaway database."""

import os
from asyncio import run

import pytest
from sqlalchemy import text

from app.kernel.db.testsupport import ensure_database, url_for

# Set before the session module is imported: it reads its URL once, at import.
DATABASE = "narrare_v2_test"
ensure_database(DATABASE)
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Rebuild the schema from the models: what the tests see is the source."""
    from app.kernel.db.init import reset_schema

    run(reset_schema(url_for(DATABASE)))


@pytest.fixture(autouse=True)
async def empty_tables() -> None:
    # Imported here: the module reads its URL once, at import.
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(text("TRUNCATE novels, chapters, users CASCADE"))
        await session.commit()
