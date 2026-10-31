"""The schema's two paths, held equal by one gate.

``init_schema`` is the product's path: the three extensions, then the
migration history replayed to head — so an upgrade can reach a database
that already exists, which ``create_all`` never could. ``reset_schema`` is
the tests' path: drop everything and build from the models, so what a test
sees is exactly what the models say. The gate in
``app/kernel/db/tests/test_migrations.py`` — an empty database replayed to
head equals the models — is what keeps the two paths identical (design
D12), not discipline.

``just db-init`` brings the development database up idempotently;
``just db-reset`` throws it away and re-runs it.
"""

import asyncio
from os import environ

from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# The schema is registered by import on the shared Base: contracts holds the
# domain vocabulary, jobs, llm and prompts their own tables — kernel
# machinery, not domain — and both the replayed history above and the
# models-built create_all below see every table only because all four
# modules are imported here.
from app.kernel.contracts import models
from app.kernel.db.migrate import default_config
from app.kernel.jobs import models as jobs_models
from app.kernel.llm import models as llm_models
from app.kernel.prompts import models as prompts_models

del jobs_models, llm_models, prompts_models  # the imports are for their registration side effect


async def ensure_extensions(database_url: str) -> None:
    """Create the three extensions every table's DDL assumes; idempotent.

    A separate pre-step, not DDL inside a revision: on a hosted database the
    app user may not be allowed to create extensions, and there the platform
    owns that step (design D7).
    """
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        # vector: the embedding columns; pg_trgm: the trigram search over
        # search_text; unaccent: the diacritics-folding the query side
        # applies (the index itself is a plain gin_trgm_ops on the column).
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    await engine.dispose()


async def init_schema(database_url: str) -> None:
    """Bring a database to the history's head; a migrated database is a no-op.

    env.py reads the URL from NARRE_DATABASE_URL — the only URL source — so
    the upgrade aims at the caller's database by exporting it, the way
    app/conftest.py does for the whole suite. env.py drives alembic through
    an ``asyncio.run`` of its own, which cannot start while this coroutine's
    loop is running; the upgrade therefore gets a worker thread. The same
    shape is what an unattended startup path needs.
    """
    await ensure_extensions(database_url)
    environ["NARRE_DATABASE_URL"] = database_url
    await asyncio.to_thread(command.upgrade, default_config(), "head")


async def reset_schema(database_url: str) -> None:
    """Drop and recreate every table the models define.

    The test suites run this against their own databases, so what the tests
    see is exactly what the models say — there is no older schema to drift
    from. Tests keep the models path (D12): replaying the history per
    conftest would be slower, and the gate proves the paths equal anyway.
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
    # The models, not the history: tests create their schema from the models.
    await ensure_extensions(database_url)
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(models.Base.metadata.create_all)
    await engine.dispose()


def init_database(database_url: str) -> None:
    """The sync entry point for recipes, conftests and scripts."""
    asyncio.run(init_schema(database_url))


if __name__ == "__main__":
    from app.kernel.db.session import DATABASE_URL

    init_database(DATABASE_URL)
    print(f"schema ready: {DATABASE_URL.rsplit('/', 1)[-1]}")
