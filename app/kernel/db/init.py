"""The schema's single source: it is created directly from the models.

There are no migrations and no reason for any — the product is not live, so the
schema never drifts: a change lands in the models and here, and the database is
recreated. ``just db-init`` creates a missing schema idempotently;
``just db-reset`` throws a development database away and re-runs it. When the
product goes live, this module is where a migration story would begin — not
before.
"""

from asyncio import run

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# The contracts module is the schema: importing it registers every table.
from app.kernel.contracts import models


async def init_schema(database_url: str) -> None:
    """Create the extension and every table; existing tables stay untouched."""
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        # The vector column type needs its extension before the tables exist.
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(models.Base.metadata.create_all)
    await engine.dispose()


async def reset_schema(database_url: str) -> None:
    """Drop and recreate every table the models define.

    The test suites run this against their own databases, so what the tests see
    is exactly what the models say — there is no older schema to drift from.
    """
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        # Drop every table (and dependent views/foreign keys) in the public
        # schema, including ones the current models do not know about (leftover
        # tables from an older schema version). metadata.drop_all alone leaves
        # those behind and then fails on the next run. Dropping tables (not the
        # whole schema) keeps the vector extension's types registered, so pooled
        # connections do not hit stale type OIDs.
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        for (table_name,) in result.fetchall():
            await connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        # Views can also depend on tables; drop them too.
        result = await connection.execute(
            text("SELECT viewname FROM pg_views WHERE schemaname = 'public'")
        )
        for (view_name,) in result.fetchall():
            await connection.execute(text(f'DROP VIEW IF EXISTS "{view_name}" CASCADE'))
    await engine.dispose()
    await init_schema(database_url)


def init_database(database_url: str) -> None:
    """The sync entry point for recipes, conftests and scripts."""
    run(init_schema(database_url))


if __name__ == "__main__":
    from app.kernel.db.session import DATABASE_URL

    init_database(DATABASE_URL)
    print(f"schema ready: {DATABASE_URL.rsplit('/', 1)[-1]}")
