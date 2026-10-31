"""The migration history's read side, and the one function that writes it.

The read side: which revision is head, and whether a database's schema still
equals the models'. The write side: ``prepare_database`` takes a database from
wherever it is to the history's head — replaying a fresh one, bootstrap-
stamping a models-built one, upgrading a versioned one — under the advisory
lock that serialises two concurrent starts, with a restorable dump taken
first while revisions are pending (design D5) — and refuses, by name, every
state it does not understand (design D4 to D7 of the schema-migrations
design). ``ensure_extensions`` is the write side's pre-step (D7) and lives
here because ``prepare_database`` is its caller. The gates in
``app/kernel/db/tests/test_migrations.py`` pin all of it.
The metadata compared against is the models': ``env.py`` imports every model
module for its registration side effect, and a caller that compares outside
alembic must have imported those modules the same way — ``init.py`` and the
gates' upgrade step do.
"""

import asyncio
from contextlib import suppress
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

from app.kernel.db.backup import BackupFailed, dump_database
from app.kernel.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"

# Postgres SQLSTATE for undefined_table — the version table of a database
# that has never been migrated.
UNDEFINED_TABLE = "42P01"

# Postgres SQLSTATE for insufficient_privilege — the extension pre-step's
# one tolerable failure, because there the platform owns the step (D7).
INSUFFICIENT_PRIVILEGE = "42501"


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


async def ensure_extensions(database_url: str) -> None:
    """Create the three extensions every table's DDL assumes; idempotent.

    A separate pre-step, not DDL inside a revision: on a hosted database the
    app user may not be allowed to create extensions, and there the platform
    owns that step (design D7). It lives in this module, not in ``init.py``:
    ``prepare_database`` runs it before anything else, and ``init.py``
    imports this module — the other direction would be the cycle.
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

    Every row is read, not ``scalar``'s arbitrary one: two rows would mean
    two writers appointed two heads, and collapsing that to one revision
    hides the other — the database is refused instead.
    """
    try:
        async with connection.begin_nested():
            rows = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).fetchall()
    except ProgrammingError as exc:
        # The dialect's wrapped error carries the Postgres SQLSTATE.
        if getattr(exc.__cause__, "sqlstate", None) != UNDEFINED_TABLE:
            raise
        return None
    if len(rows) != 1:
        named = ", ".join(str(row[0]) for row in rows) or "none"
        raise MigrationRefused(
            f"alembic_version holds {len(rows)} revisions ({named}), expected exactly one"
        )
    return str(rows[0][0])


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

    The whole decision runs under a session-level ``pg_advisory_lock`` held
    on its own connection: two concurrent starts serialise, the second finds
    head already reached and does nothing. The lock is released in a
    ``finally``, so a failed run cannot hold the next one hostage.

    While revisions are pending, the upgrade is preceded by a ``pg_dump``
    copy (design D5): a run with pending revisions either produces a
    restorable dump or migrates nothing. ``backup=False`` — a caller that
    owes no dump, like ``init_schema`` — and ``NARRE_MIGRATION_BACKUP=skip``
    — an operator who took their own copy — leave it out; the copy goes to
    ``backup_dir``, else ``NARRE_BACKUP_DIR`` (default ``./backups``).

    env.py reads the URL from NARRE_DATABASE_URL — the only URL source — and
    drives alembic through an ``asyncio.run`` of its own, which cannot start
    while this coroutine's loop is running; the alembic commands therefore
    get a worker thread, and the lock keeps two such runs from overlapping
    (alembic's migration environment is not reentrant).
    """
    # Process-global by design: env.py takes the URL from the environment
    # only, and this is the CLI/startup process, which owns the variable for
    # its short life — nothing else in the process re-reads it after import.
    environ["NARRE_DATABASE_URL"] = database_url

    try:
        await ensure_extensions(database_url)
    except Exception as exc:
        # Only a privilege problem is the refusal the platform can act on
        # (D7): an unreachable host or a bad password is not a permissions
        # story, and surfaces unchanged.
        if getattr(exc.__cause__, "sqlstate", None) != INSUFFICIENT_PRIVILEGE:
            raise
        raise MigrationRefused(
            "could not create the extensions the schema's DDL needs "
            f"(vector, pg_trgm, unaccent): {exc}; on a hosted database the "
            "platform owns this step — have the extensions created, or grant "
            "this user the right to create extensions"
        ) from exc

    head = head_revision()
    config = default_config()

    current: str | None = None
    bootstrapped = False
    backup_path: Path | None = None
    final: str | None = None
    engine = create_async_engine(database_url)
    # The lock's own connection, in autocommit: the session-level lock must
    # not ride on a transaction of the other engine's, and must survive the
    # whole run regardless of what those transactions do.
    lock_engine = create_async_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        async with lock_engine.connect() as lock_connection:
            await lock_connection.execute(
                text("SELECT pg_advisory_lock(hashtext('narrare_migrations'))")
            )
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
                        # this is the stamp (D4), not a replay of the history. The
                        # stamp itself runs once this transaction has ended — no
                        # connection of ours sits idle-in-transaction across it.
                        bootstrapped = True

                    if current is not None and current not in {
                        script.revision
                        for script in ScriptDirectory.from_config(config).walk_revisions()
                    }:
                        raise MigrationRefused(f"database is at {current}, this app knows {head}")

                    # The reads are done — end this transaction before any
                    # alembic command opens its own connections (D5's upgrade
                    # runs next): nothing of ours stays idle-in-transaction
                    # under it.
                    await connection.rollback()

                if bootstrapped:
                    await asyncio.to_thread(command.stamp, config, head)
                # Revisions are pending if the upgrade will really run — a
                # fresh replay or a versioned one behind head — and only then
                # does the restorable copy happen (D5), unless this caller
                # owes none, or the operator already took their own backup.
                elif (
                    (current is None or current != head)
                    and backup
                    and environ.get("NARRE_MIGRATION_BACKUP", "pg_dump") != "skip"
                ):
                    directory = backup_dir or Path(environ.get("NARRE_BACKUP_DIR") or "./backups")
                    try:
                        backup_path = await dump_database(database_url, directory)
                    except BackupFailed as exc:
                        raise MigrationRefused(
                            "the pre-migration dump failed and nothing was migrated: "
                            f"{exc}; install postgresql-client so the dump can run, "
                            "or set NARRE_MIGRATION_BACKUP=skip after taking your "
                            "own copy of the database"
                        ) from exc

                await asyncio.to_thread(command.upgrade, config, "head")

                # The re-read gets a fresh connection: the one above ended its
                # transaction before the upgrade, and its snapshot would be
                # stale anyway.
                async with engine.connect() as connection:
                    final = await current_revision(connection)
            finally:
                # The session ends below either way, but say the release out
                # loud. If this fails, the session is already gone — and with
                # it the lock — so it must not mask the run's own error.
                with suppress(Exception):
                    await lock_connection.execute(
                        text("SELECT pg_advisory_unlock(hashtext('narrare_migrations'))")
                    )
    finally:
        await engine.dispose()
        await lock_engine.dispose()
    if final != head:
        raise MigrationRefused(f"the upgrade ended at {final}, expected {head}")

    return MigrationOutcome(
        from_revision=current, to_revision=head, bootstrapped=bootstrapped, backup=backup_path
    )
