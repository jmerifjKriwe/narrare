"""The migration gates (design D3.1 and D3.2 of the schema-migrations design).

Two of the four design gates live here for now: the history has exactly one
head, and an empty database replayed to head is indistinguishable from what
the models declare. The second is the gate that keeps the two schema paths
identical (D12): tests build from the models, `just db-init` replays the
history, and this test is the only thing that proves both say the same thing.
"""

from os import environ
from typing import TYPE_CHECKING

import pytest
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.kernel.db.migrate import default_config, diff_against_models, head_revision

if TYPE_CHECKING:
    from collections.abc import Iterator

    from alembic.config import Config
    from sqlalchemy.engine import Connection

_OPEN_CONNECTIONS: list[Connection] = []


@pytest.fixture(autouse=True)
def _close_opened_connections() -> Iterator[None]:
    """Close what ``connect`` opened: this suite turns warnings into errors."""
    yield
    for connection in _OPEN_CONNECTIONS:
        connection.close()
    _OPEN_CONNECTIONS.clear()


def alembic_config(url: str) -> Config:
    """The repo's alembic.ini, aimed at the gate's database.

    env.py reads the URL from ``NARRE_DATABASE_URL`` — the only URL source —
    so aiming a run at a database means exporting it, the way
    ``app/conftest.py`` does for the whole suite. Nothing re-reads the
    variable after the app modules have bound their engines at import, so
    the export cannot redirect another suite's connection.
    """
    environ["NARRE_DATABASE_URL"] = url
    return default_config()


def connect(url: str) -> Connection:
    """A synchronous connection for the autogenerate comparison.

    Alembic's comparison machinery runs on a sync Connection; the URL speaks
    asyncpg, so the driver is swapped for psycopg. Reflection only — no
    application data path ever goes through this engine. NullPool makes
    ``close`` a real close, and the autouse fixture above closes it.
    """
    connection = create_engine(url.replace("+asyncpg", "+psycopg"), poolclass=NullPool).connect()
    _OPEN_CONNECTIONS.append(connection)
    return connection


def test_migrations_have_one_head() -> None:
    assert head_revision().count(",") == 0 and head_revision()


def test_empty_database_migrated_equals_the_models(url: str) -> None:
    command.upgrade(alembic_config(url), "head")
    assert diff_against_models(alembic_config(url), connect(url)) == []
