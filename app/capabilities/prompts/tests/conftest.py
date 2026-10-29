"""Prompts suite fixtures: the shared test database, rebuilt from the models."""

from asyncio import run

import pytest
from sqlalchemy import text

from app.kernel.db.testsupport import url_for

# app/conftest.py names the database and the app binds it; this file says what
# to rebuild and what a test starts from.
DATABASE = "narrare_v2_test"


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
        await session.execute(text("TRUNCATE prompt_templates, novels, chapters, users CASCADE"))
        # An installed instance: the API answers as the local user.
        session.add(User(id=LOCAL_USER_ID))
        await session.commit()
