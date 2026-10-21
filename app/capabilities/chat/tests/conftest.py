"""Chat suite fixtures: the suite's own database, schema from the migration."""

import os

import pytest
from alembic.config import Config
from app.kernel.db.testsupport import ensure_database, url_for
from sqlalchemy import text

from alembic import command

# Set before the session module is imported: it reads its URL once, at import.
DATABASE = "narrare_v2_test"
ensure_database(DATABASE)
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Build the schema from the migration, so a drift from the models fails here."""
    config = Config("app/kernel/db/alembic.ini")
    config.set_main_option("script_location", "app/kernel/db/migrations")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def empty_tables() -> None:
    # Imported here: the module reads its URL once, at import.
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(text("TRUNCATE chunks, documents, novels, chapters, users CASCADE"))
        await session.commit()
