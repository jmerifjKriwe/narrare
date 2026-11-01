"""The schema's two paths, held equal by one gate.

``init_schema`` is the product's path: the three extensions, then the history
— replayed on a fresh database, bootstrap-stamped onto a models-built one
(design D4), upgraded in place on a versioned one — so an upgrade can reach a
database that already exists, which ``create_all`` never could.
``reset_schema`` is the tests' path: drop everything and build from the
models, so what a test sees is exactly what the models say. The gate in
``app/kernel/db/tests/test_migrations.py`` — an empty database replayed to
head equals the models — is what keeps the two paths identical (design
D12), not discipline.

``just db-init`` brings the development database up idempotently;
``just db-reset`` throws it away and re-runs it.
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.base import Base
from app.kernel.db.migrate import ensure_extensions, prepare_database, register_models
from app.kernel.db.testsupport import drop_every_table


async def init_schema(database_url: str) -> None:
    """Bring a database to the history's head; idempotent on every Narrare state.

    A fresh database is replayed from nothing, a models-built one is
    bootstrap-stamped once its schema equals the models', a versioned one is
    upgraded in place — ``prepare_database`` decides, and refuses by name
    anything else. The dump is the startup/upgrade path's concern (design
    D5), and ``just db-init`` is that path for a development database: one
    behind head takes the same pre-upgrade dump the app's own startup
    would, under the same default — ``NARRE_MIGRATION_BACKUP``, a dump when
    revisions are pending and tables exist. A suite that must not dump sets
    ``NARRE_MIGRATION_BACKUP=skip`` (the API conftest does).
    """
    await prepare_database(database_url)


async def reset_schema(database_url: str) -> None:
    """Drop and recreate every table the models define.

    The test suites run this against their own databases, so what the tests
    see is exactly what the models say — there is no older schema to drift
    from. Tests keep the models path (D12): replaying the history per
    conftest would be slower, and the gate proves the paths equal anyway.
    """
    # The one drop-everything (app/kernel/db/testsupport.py): tables the
    # current models no longer know must go too, and dependent views with
    # them.
    await drop_every_table(database_url)
    await ensure_extensions(database_url)
    # The models, not the history: tests create their schema from the models
    # — registered by the one seam, kernel and capability modules both, not
    # by whichever imports this module's callers happened to make.
    register_models()
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


def init_database(database_url: str) -> None:
    """The sync entry point for recipes, conftests and scripts."""
    asyncio.run(init_schema(database_url))


if __name__ == "__main__":
    # The bootstrap path logs its constraint renames at INFO; a bare
    # ``python -m`` configures no logging, and the default root level would
    # drop them from the recipe's output.
    from logging import INFO, basicConfig

    basicConfig(level=INFO)

    from app.kernel.db.session import DATABASE_URL

    init_database(DATABASE_URL)
    print(f"schema ready: {DATABASE_URL.rsplit('/', 1)[-1]}")
