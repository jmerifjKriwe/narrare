"""The migration history's read side, and the one function that writes it.

The read side: which revision is head, and whether a database's schema still
equals the models'. The write side: ``prepare_database`` takes a database from
wherever it is to the history's head — replaying a fresh one, bootstrap-
stamping a models-built one, upgrading a versioned one — and refuses, by
name, every state it does not understand (design D4 to D7 of the schema-migrations
design). The gates in ``app/kernel/db/tests/test_migrations.py`` pin all of it.
The metadata compared against is the models': ``env.py`` imports every model
module for its registration side effect, and a caller that compares outside
alembic must have imported those modules the same way — ``init.py`` and the
gates' upgrade step do.
"""

import asyncio
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"

# Postgres SQLSTATE for undefined_table — the version table of a database
# that has never been migrated.
UNDEFINED_TABLE = "42P01"


class MigrationRefused(RuntimeError):  # noqa: N818  the name is the task interface
    """The migration history cannot be read or applied as asked."""


@dataclass
class MigrationOutcome:
    """What one ``prepare_database`` run did, for the caller's log line."""

    from_revision: str | None
    to_revision: str
    bootstrapped: bool
    backup: Path | None


def default_config() -> Config:
    """The repo's alembic.ini; the URL arrives via NARRE_DATABASE_URL in env.py."""
    return Config(str(ALEMBIC_INI))


def head_revision() -> str:
    """The one head of the migration history.

    Two heads mean someone committed a branch instead of extending the
    history; zero mean no revisions exist. Both refuse: an upgrade that
    guesses which line to follow is how a database ends up half-migrated.
    """
    heads = ScriptDirectory.from_config(default_config()).get_heads()
    if len(heads) != 1:
        raise MigrationRefused(
            f"expected exactly one head revision, found {len(heads)}: {', '.join(heads)}"
        )
    return heads[0]


def diff_against_models(config: Config, connection: Connection) -> list[Any]:
    """What alembic would still have to do for the database to match the models.

    An empty list means the migrated schema equals the models' — the gate
    that keeps the two schema paths (the replayed history, the models-built
    tests) saying the same thing. The comparison runs with the same switches
    an autogenerate draft runs with, so the gate proves what a draft would
    see.
    """
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    return list(compare_metadata(context, Base.metadata))


async def current_revision(connection: AsyncConnection) -> str | None:
    """The revision the database's ``alembic_version`` row names; None if none.

    A database with no history yet has no version table at all, so the read
    tolerates exactly that error. It runs inside a savepoint: the failed
    statement rolls back to it and the connection stays usable — without the
    repair, every statement after the first read would die on an aborted
    transaction. Any other failure is a real problem and surfaces.
    """
    try:
        async with connection.begin_nested():
            revision: str | None = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    except ProgrammingError as exc:
        # The dialect's wrapped error carries the Postgres SQLSTATE.
        if getattr(exc.__cause__, "sqlstate", None) != UNDEFINED_TABLE:
            raise
        return None
    return revision


async def _has_tables(connection: AsyncConnection) -> bool:
    """Whether the public schema holds any table — the bootstrap branch's trigger."""
    present: bool | None = await connection.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public')")
    )
    return bool(present)


def _describe(diff: list[Any]) -> str:
    """A diff as one line a refusal can name: op, schema, table, column."""
    return "; ".join(" ".join(str(part) for part in op if part is not None) for op in diff)


async def prepare_database(
    database_url: str, *, backup: bool = True, backup_dir: Path | None = None
) -> MigrationOutcome:
    """Bring one database to the history's head, refusing to guess.

    The state the database starts in decides the path: a fresh one is
    replayed from nothing; a models-built one — tables but no
    ``alembic_version`` — is stamped only when its schema equals the models',
    else refused with the differences named; a versioned one is upgraded in
    place, but a revision outside this app's history is refused with both
    versions named, and so is an upgrade that ends anywhere but head.

    The pre-migration dump ``backup``/``backup_dir`` ask for is deliberately
    unused here — it is wired together with the advisory lock that serialises
    two concurrent runs; the parameters exist now so the signature is already
    final.

    env.py reads the URL from NARRE_DATABASE_URL — the only URL source — and
    drives alembic through an ``asyncio.run`` of its own, which cannot start
    while this coroutine's loop is running; the alembic commands therefore
    get a worker thread.
    """
    # Process-global by design: env.py takes the URL from the environment
    # only, and this is the CLI/startup process, which owns the variable for
    # its short life — nothing else in the process re-reads it after import.
    environ["NARRE_DATABASE_URL"] = database_url

    # Imported here, not at the top: init.py imports this module, and the
    # extensions step (D7) lives there — a top-level import would be a cycle.
    from app.kernel.db.init import ensure_extensions

    try:
        await ensure_extensions(database_url)
    except Exception as exc:
        raise MigrationRefused(
            "could not create the extensions the schema's DDL needs "
            f"(vector, pg_trgm, unaccent): {exc}; on a hosted database the "
            "platform owns this step — have the extensions created, or grant "
            "this user the right to"
        ) from exc

    head = head_revision()
    config = default_config()

    current: str | None = None
    bootstrapped = False
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            current = await current_revision(connection)
            if current is None and await _has_tables(connection):
                diff = await connection.run_sync(
                    lambda sync_connection: diff_against_models(config, sync_connection)
                )
                if diff:
                    raise MigrationRefused(
                        "the database has tables but no migration history, and its "
                        f"schema does not match the models ({_describe(diff)}); "
                        "refusing to guess — align the schema with the models by "
                        "hand or reset the database"
                    )
                # An equal schema earns the history's version row and no DDL:
                # this is the stamp (D4), not a replay of the history.
                await asyncio.to_thread(command.stamp, config, head)
                bootstrapped = True

            if current is not None and current not in {
                script.revision for script in ScriptDirectory.from_config(config).walk_revisions()
            }:
                raise MigrationRefused(f"database is at {current}, this app knows {head}")

            await asyncio.to_thread(command.upgrade, config, "head")

            final = await current_revision(connection)
    finally:
        await engine.dispose()
    if final != head:
        raise MigrationRefused(f"the upgrade ended at {final}, expected {head}")

    return MigrationOutcome(
        from_revision=current, to_revision=head, bootstrapped=bootstrapped, backup=None
    )
