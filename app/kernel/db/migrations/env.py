"""The migration environment.

The URL comes from ``NARRE_DATABASE_URL`` — the only URL source, which is
why alembic.ini carries none — and the table set is the models': every
registering module is imported through ``register_models`` (the four kernel
model modules, then each capability's via the generated registry, because
the kernel may not name a capability) for its registration side effect on
the shared ``Base`` — the same side effect that later populates the
metadata ``diff_against_models`` compares against.
"""

import asyncio
from os import environ
from typing import TYPE_CHECKING, Any, Literal

import pgvector.sqlalchemy
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.kernel.db.base import Base
from app.kernel.db.migrate import register_models

if TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext
    from sqlalchemy.engine import Connection

# The table set is the models': every registering module — kernel machinery
# plus each capability's tables — lands on the shared Base through the one
# seam, not through this file's own import list.
register_models()

config = context.config

# The one URL source: nothing in the ini names a database.
config.set_main_option("sqlalchemy.url", environ["NARRE_DATABASE_URL"])

target_metadata = Base.metadata


def _render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    """Render pgvector's Vector by import path, not by repr.

    The type has no usable repr, so the default rendering would emit
    something no revision could keep; the draft says
    ``pgvector.sqlalchemy.Vector()`` for a human to read and correct.
    ``script.py.mako`` already imports ``pgvector.sqlalchemy``, so nothing is
    added to the draft's imports here — adding it there and here is what
    produced a duplicate import in the first draft. Everything else falls
    through to alembic's own rendering.
    """
    if type_ == "type" and isinstance(obj, pgvector.sqlalchemy.Vector):
        return "pgvector.sqlalchemy.Vector()"
    return False


def _run_migrations(connection: Connection) -> None:
    """Apply the history on a live connection, opened synchronously for us."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_offline() -> None:
    """Emit the history's SQL to stdout instead of touching a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """One engine, no pool: the run is a single process and exits after."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    _run_migrations_offline()
else:
    asyncio.run(_run_async_migrations())
