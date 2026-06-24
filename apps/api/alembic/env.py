"""Alembic migration environment."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import TYPE_CHECKING

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import narrare.auth.models
import narrare.chapters.models
import narrare.embeddings.models
import narrare.evidence.models
import narrare.generation.models
import narrare.kb.models
import narrare.memory.models
import narrare.novels.models
import narrare.planning.models
import narrare.prompts.models
import narrare.settings.models
import narrare.settings.token_limits.models
import narrare.templates.models
import narrare.volumes.models
import narrare.wiki.models
import narrare.writing.models  # noqa: F401
from alembic import context

# Import the declarative base and all ORM models so Alembic can detect tables.
# pyright: reportUnusedImport=false
from narrare._app.database import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev",
    )


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
