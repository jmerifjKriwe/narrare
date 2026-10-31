"""The migration gates (design D3) and the startup path's refusal tests.

Three of the four design gates live here: the history has exactly one head
(D3.1), an empty database replayed to head is indistinguishable from what the
models declare (D3.2 — the gate that keeps the two schema paths identical,
D12), and the bootstrap branch stamps an equal models-built schema while
refusing a drifted or unknown-revision one by name (D3.4, D4, D6). The fourth
gate (D3.3, the previous release's snapshot) is still to come.

``prepare_database`` is the function the gates drive: the same one
``just db-init`` and the API suite's session fixture run.
"""

import asyncio
from os import environ
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.init import reset_schema
from app.kernel.db.migrate import (
    MigrationRefused,
    default_config,
    diff_against_models,
    head_revision,
    prepare_database,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from alembic.config import Config
    from sqlalchemy.engine import Connection


@pytest.fixture(autouse=True)
def _restore_database_url() -> Iterator[None]:
    """Put ``NARRE_DATABASE_URL`` back after a test exported its own URL."""
    previous = environ.get("NARRE_DATABASE_URL")
    yield
    if previous is None:
        environ.pop("NARRE_DATABASE_URL", None)
    else:
        environ["NARRE_DATABASE_URL"] = previous


def alembic_config(url: str) -> Config:
    """The repo's alembic.ini, aimed at the gate's database.

    env.py reads the URL from ``NARRE_DATABASE_URL`` — the only URL source —
    so aiming a run at a database means exporting it, the way
    ``app/conftest.py`` does for the whole suite. The autouse fixture above
    restores the previous value when the test ends.
    """
    environ["NARRE_DATABASE_URL"] = url
    return default_config()


def _diff_from_models(connection: Connection, url: str) -> list[Any]:
    """The comparison, on the sync facade ``run_sync`` hands over."""
    return diff_against_models(alembic_config(url), connection)


async def _models_diff(url: str) -> list[Any]:
    """The comparison, from a test's own engine."""
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: _diff_from_models(sync_connection, url)
            )
    finally:
        await engine.dispose()


async def _drop_every_table(url: str) -> None:
    """Empty the gates' database again — the module fixture only did it once.

    pytest-randomly shuffles this module, so every test builds its own state:
    a leftover ``alembic_version`` from the previous test would turn a fresh
    database into a versioned one and quietly exercise the wrong branch.
    """
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        for (table_name,) in result.fetchall():
            await connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
    await engine.dispose()


async def _version_row(url: str) -> str | None:
    """The database's ``alembic_version`` value, read directly."""
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            version: str | None = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            return version
    finally:
        await engine.dispose()


def test_migrations_have_one_head() -> None:
    assert head_revision().count(",") == 0 and head_revision()


async def test_empty_database_migrated_equals_the_models(url: str) -> None:
    # The gate's claim is about an *empty* database: whichever test ran before
    # this one left its tables behind, so the drop happens here, not only in
    # the module fixture (pytest-randomly shuffles this module).
    await _drop_every_table(url)
    # env.py drives alembic through an asyncio.run of its own, which cannot
    # start inside this test's loop; the upgrade gets its own thread.
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
    assert await _models_diff(url) == []


# ---------------------------------------------------------------------------
# prepare_database — the unattended startup path (D3.4, D4, D6)
# ---------------------------------------------------------------------------


async def test_fresh_database_is_upgraded(url: str) -> None:
    """An empty database is replayed from nothing — no bootstrap, no stamp."""
    await _drop_every_table(url)

    outcome = await prepare_database(url)

    assert outcome.from_revision is None
    assert outcome.bootstrapped is False
    assert outcome.to_revision == head_revision()
    assert await _version_row(url) == head_revision()


async def test_models_created_database_is_stamped(url: str) -> None:
    """A models-built schema earns the history's version row and no DDL (D4)."""
    await reset_schema(url)
    user_id = uuid4()
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO users (id, created_at) VALUES (:id, now())"),
                {"id": user_id},
            )
    finally:
        await engine.dispose()

    outcome = await prepare_database(url)

    assert outcome.from_revision is None
    assert outcome.bootstrapped is True
    assert outcome.to_revision == head_revision()
    # No DDL happened: the stamp writes the version row only — the seeded row
    # survives, the schema still equals the models', and the version is head.
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            users: int | None = await connection.scalar(text("SELECT count(*) FROM users"))
            assert users == 1
    finally:
        await engine.dispose()
    assert await _version_row(url) == head_revision()
    assert await _models_diff(url) == []


async def test_drifted_database_is_refused(url: str) -> None:
    """A schema no revision built and not equal to the models is named (D4)."""
    await reset_schema(url)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("ALTER TABLE chapters DROP COLUMN title"))
    finally:
        await engine.dispose()

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url)

    message = str(refused.value)
    assert "add_column" in message  # the op that would reconcile the drift
    assert "chapters" in message  # the table the diff is about
    assert "title" in message  # the missing piece itself


async def test_database_ahead_of_the_app_is_refused(url: str) -> None:
    """A revision outside this app's history names both versions (D6)."""
    await _drop_every_table(url)
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE alembic_version SET version_num = 'zzzz'"))
    finally:
        await engine.dispose()

    head = head_revision()
    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url)

    message = str(refused.value)
    assert "zzzz" in message  # what the database says
    assert head in message  # what this app knows
