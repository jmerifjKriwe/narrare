"""Throwaway databases for tests that run against a real Postgres.

Each run gets its own database: the name carries the worktree and the process,
it is created and dropped per run, and a database left behind by a run that
died mid-suite the next run's sweep reclaims. One shared name would carry one
suite's rows into the next and let two concurrent runs truncate each other's
tables mid-test (#611).
"""

import asyncio
import re
import sys
from contextlib import suppress
from hashlib import blake2s
from os import getpid, kill
from pathlib import Path
from uuid import UUID  # noqa: TC003

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

SERVER = "postgresql+asyncpg://narrare:narrare@localhost:5433"

REPO_ROOT = Path(__file__).resolve().parents[3]

# ``test_database``'s suffix — which the sweep matches on: the worktree token
# plus the owning pid, 16 lowercase hex characters in total.
_RUN_TOKEN = re.compile(r"[0-9a-f]{16}")

_SWEPT: set[str] = set()
_RUN_DATABASES: list[str] = []


def url_for(database: str) -> str:
    return f"{SERVER}/{database}"


def test_database(prefix: str = "narrare_v2_test", *, pid: int | None = None) -> str:
    """This run's database name: ``prefix_`` + worktree token + process pid.

    Same process, same prefix — same name, always; a second pytest run, in a
    second worktree or a second process, names a database of its own (#611).
    The first call under a prefix per process also runs ``sweep``, so a run
    crashed mid-test does not leave its database behind on the server.

    ``ensure_database`` is the caller's next step: nothing is created here.
    """
    if prefix not in _SWEPT:
        sweep(prefix)
        _SWEPT.add(prefix)
    owner = getpid() if pid is None else pid
    name = f"{prefix}_{blake2s(str(REPO_ROOT).encode(), digest_size=4).hexdigest()}{owner:08x}"
    if name not in _RUN_DATABASES:
        _RUN_DATABASES.append(name)
    return name


def sweep(prefix: str = "narrare_v2_test") -> None:
    """Drop the prefix's per-run databases whose owner process is gone.

    A database belongs to this prefix only when its name is exactly
    ``prefix_`` plus 16 lowercase hex characters — the shape and only the
    shape ``test_database`` produces. Everything else stays untouched: the
    legacy ``narrare_v2_test``, the ``narrare_v2_*_e2e`` names, the developer
    databases. The last 8 hex characters read as a pid; a dead pid's database
    is dropped, a live one's kept — ``PermissionError`` counts as alive
    (another user's process), ``ProcessLookupError`` as dead.
    """
    asyncio.run(_sweep(prefix))


async def _sweep(prefix: str) -> None:
    engine = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            names = [
                str(row[0])
                for row in (await connection.execute(text("SELECT datname FROM pg_database")))
            ]
            for name in names:
                if not name.startswith(f"{prefix}_"):
                    continue
                suffix = name[len(prefix) + 1 :]
                if _RUN_TOKEN.fullmatch(suffix) is None:
                    continue
                try:
                    owner = int(suffix[8:], 16)
                    kill(owner, 0)
                except ProcessLookupError:
                    pass  # dead: its database is litter this run reclaims
                except PermissionError:
                    continue  # alive, owned by another user
                except OverflowError, ValueError:
                    continue  # not a pid this platform can signal: not ours to drop
                else:
                    continue  # alive
                await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


def drop_database(name: str) -> None:
    """Drop one database, terminating connections still using it."""
    asyncio.run(_drop(name))


async def _drop(name: str) -> None:
    engine = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


def drop_run_databases() -> None:
    """Drop every name ``test_database`` handed out this run.

    ``app/conftest.py``'s ``pytest_sessionfinish`` calls it once the last test
    is done; a drop failing here must not bury pytest's real result under an
    INTERNALERROR, so each name is tried on its own and a failure is reported
    to stderr instead of raised. Each run drops only the names it recorded, so
    a concurrent run's database is not ours to touch.
    """
    for name in _RUN_DATABASES:
        try:
            drop_database(name)
        except (OSError, SQLAlchemyError) as error:
            print(f"{name}: {error}", file=sys.stderr)


async def drop_every_table(database_url: str) -> None:
    """Drop every table and view in the public schema — a throwaway database again.

    The one drop-everything, shared by ``reset_schema``, the migration
    gates' conftest and the gates themselves. Thoroughness matters: leftover
    tables from an older schema version would turn "empty database" tests
    into "previously migrated" ones, and ``metadata.drop_all`` alone leaves
    those behind and then fails on the next run. Dropping tables (not the
    whole schema) keeps the vector extension's types registered, so pooled
    connections do not hit stale type OIDs. Views can depend on tables;
    they are dropped too.
    """
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        for (table_name,) in result.fetchall():
            await connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        result = await connection.execute(
            text("SELECT viewname FROM pg_views WHERE schemaname = 'public'")
        )
        for (view_name,) in result.fetchall():
            await connection.execute(text(f'DROP VIEW IF EXISTS "{view_name}" CASCADE'))
    await engine.dispose()


async def seed_user(user_id: UUID) -> None:
    """The users row a user-owned test row needs: the key reaches users."""
    from app.kernel.contracts.models import User
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
        await session.commit()


async def _ensure(database: str) -> None:
    engine = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
        )
        if not exists:
            # A parallel pytest worker may create it between the check and here.
            with suppress(Exception):
                await connection.execute(text(f'CREATE DATABASE "{database}"'))
    await engine.dispose()


def ensure_database(database: str) -> None:
    asyncio.run(_ensure(database))
