"""The migration environment.

The URL comes from ``NARRE_DATABASE_URL`` — the only URL source, which is
why alembic.ini carries none — and the table set is the models': the kernel
model modules are imported here, the capability model modules are reached
through the generated registry, because the kernel may not name a
capability. The imports exist for their registration side effect on the
shared ``Base`` — the same side effect that later populates the metadata
``diff_against_models`` compares against.
"""

import asyncio
from contextlib import suppress
from importlib import import_module
from os import environ
from typing import TYPE_CHECKING, Any, Literal

import pgvector.sqlalchemy
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.generated.capabilities import CAPABILITIES
from app.kernel.contracts import models as contracts_models
from app.kernel.db.base import Base
from app.kernel.jobs import models as jobs_models
from app.kernel.llm import models as llm_models
from app.kernel.prompts import models as prompts_models

if TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext
    from sqlalchemy.engine import Connection

# Kernel machinery, not domain: contracts holds the shared vocabulary, jobs,
# llm and prompts their own tables.
del contracts_models, jobs_models, llm_models, prompts_models

# A capability's tables join the migration's table set without a named
# import — the kernel may not name a capability, so the generated registry
# says whose models module exists. A capability without tables has no
# models module; the suppression is that contract, not a blind catch.
for _capability in CAPABILITIES:
    with suppress(ModuleNotFoundError):
        import_module(f"app.capabilities.{_capability.id}.models")

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
