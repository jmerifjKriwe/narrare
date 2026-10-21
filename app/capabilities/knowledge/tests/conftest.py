"""Knowledge suite fixtures: the suite's own database, schema from the models."""

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
    from app.kernel.auth import LOCAL_USER_ID
    from app.kernel.contracts.models import User
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(text("TRUNCATE chunks, documents, novels, chapters, users CASCADE"))
        # The local user exists: these tests exercise a set-up instance. The
        # guard test deletes it again to see the refusal.
        session.add(User(id=LOCAL_USER_ID))
        await session.commit()
