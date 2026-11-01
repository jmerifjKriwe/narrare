"""The migration history's read side, and the one function that writes it.

The read side: which revision is head, and whether a database's schema still
equals the models'. The write side: ``prepare_database`` takes a database from
wherever it is to the history's head — replaying a fresh one, bootstrap-
stamping a models-built one, upgrading a versioned one — under the advisory
lock that serialises two concurrent starts, with a restorable dump taken
first while revisions are pending and the database holds tables — a fresh
first boot takes none, which keeps pg_dump out of its requirements
(design D5) — and refuses, by name, every
state it does not understand (design D4 to D7 of the schema-migrations
design). ``ensure_extensions`` is the write side's pre-step (D7) and lives
here because ``prepare_database`` is its caller. The gates in
``app/kernel/db/tests/test_migrations.py`` pin all of it.
The comparison's table set: ``register_models`` imports every model module
for its registration side effect — ``env.py``, ``reset_schema`` and the
comparisons call it, so no caller's import graph is a hidden precondition.
The bootstrap compares an unversioned database against the *baseline*
revision's replayed schema, reflected from a scratch database on the same
server, and stamps the baseline (CodeRabbit round 1, 2026-11-01); the
equality gate compares against the models' metadata.
"""

import asyncio
import logging
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
from sqlalchemy import ForeignKeyConstraint, MetaData, UniqueConstraint, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.backup import BackupFailed, dump_database
from app.kernel.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"

# Postgres SQLSTATE for undefined_table — the version table of a database
# that has never been migrated.
UNDEFINED_TABLE = "42P01"

# Postgres SQLSTATE for insufficient_privilege — the extension pre-step's
# one tolerable failure, because there the platform owns the step (D7).
INSUFFICIENT_PRIVILEGE = "42501"

# The scratch database the bootstrap replays the baseline revision on, to
# hold the schema an unversioned database is compared against. The advisory
# lock below serialises ``prepare_database`` runs cluster-wide, so the fixed
# name cannot collide with a concurrent run; a leftover from a crashed run
# is dropped with ``FORCE`` before the replay creates it.
BOOTSTRAP_SCRATCH_DATABASE = "narrare_migrations_baseline"


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


def head_revision(config: Config | None = None) -> str:
    """The one head of the migration history.

    Two heads mean someone committed a branch instead of extending the
    history; zero mean no revisions exist. Both refuse: an upgrade that
    guesses which line to follow is how a database ends up half-migrated.
    """
    heads = ScriptDirectory.from_config(config or default_config()).get_heads()
    if len(heads) != 1:
        raise MigrationRefused(
            f"expected exactly one head revision, found {len(heads)}: {', '.join(heads)}"
        )
    return heads[0]


def baseline_revision(config: Config | None = None) -> str:
    """The history's root: the one revision with no down_revision.

    The bootstrap's comparison target (design D4): a database that never had
    a history matches the schema the *baseline* replayed — not head's
    models, which later revisions may already have moved past.
    """
    roots = [
        revision.revision
        for revision in ScriptDirectory.from_config(config or default_config()).walk_revisions()
        if revision.down_revision is None
    ]
    if len(roots) != 1:
        raise MigrationRefused(f"expected exactly one baseline revision, found {len(roots)}")
    return roots[0]


def register_models() -> None:
    """Import every module that registers tables on the shared ``Base``.

    The four kernel model modules first, then each capability's models
    module via the generated registry (the kernel may not name a
    capability). The imports exist for their registration side effect: the
    metadata ``diff_against_models`` compares against is the full table set
    only once every registering module has been imported, and which modules
    a process imported for other reasons is not a fact a schema comparison
    may lean on. A capability without tables has no models module, and only
    that absence is swallowed — a ModuleNotFoundError raised *inside* an
    existing models module is a real defect and surfaces.
    """
    from importlib import import_module

    from app.generated.capabilities import CAPABILITIES
    from app.kernel.contracts import models as contracts_models
    from app.kernel.jobs import models as jobs_models
    from app.kernel.llm import models as llm_models
    from app.kernel.prompts import models as prompts_models

    del contracts_models, jobs_models, llm_models, prompts_models

    for capability in CAPABILITIES:
        models_module = f"app.capabilities.{capability.id}.models"
        try:
            import_module(models_module)
        except ModuleNotFoundError as exc:
            if exc.name != models_module:
                raise


def diff_against_models(
    config: Config, connection: Connection, metadata: MetaData | None = None
) -> list[Any]:
    """What alembic would still have to do for the database to match the schema.

    An empty list means the database equals ``metadata`` — the models' by
    default, which is the gate that keeps the two schema paths (the replayed
    history, the models-built tests) saying the same thing; the bootstrap
    passes the baseline revision's reflected replay instead (design D4,
    CodeRabbit round 1, 2026-11-01). The comparison runs with the same
    switches an autogenerate draft runs with, so the gate proves what a
    draft would see. The models register here first: the default target
    brings its own table set instead of trusting the caller's import graph.
    """
    register_models()
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    return list(compare_metadata(context, metadata if metadata is not None else Base.metadata))


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
    """Whether the public schema holds any table.

    The bootstrap branch's trigger — tables without a history row are a
    candidate for the stamp — and the dump branch's gate (D5): the dump
    protects prose, and a database without tables has none.
    """
    present: bool | None = await connection.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public')")
    )
    return bool(present)


def _describe(diff: list[Any]) -> str:
    """A diff as one line a refusal can name: op, schema, table, column."""
    return "; ".join(" ".join(str(part) for part in op if part is not None) for op in diff)


async def _extensions_or_refuse(database_url: str) -> None:
    """``ensure_extensions``, with the one privilege failure as a refusal (D7)."""
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


# The catalog behind the PK/FK normalization: every primary key ('p') and
# foreign key ('f') in the public schema, with its table, its column list
# and — for a foreign key — the referenced table.
_CONSTRAINT_CATALOG = text(
    """
    SELECT cl.relname AS table_name,
           c.conname AS constraint_name,
           c.contype::text AS kind,
           (SELECT array_agg(a.attname ORDER BY k.ord)
              FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
              JOIN pg_attribute AS a
                ON a.attrelid = c.conrelid AND a.attnum = k.attnum) AS columns,
           ref.relname AS referred_table
      FROM pg_constraint AS c
      JOIN pg_class AS cl ON cl.oid = c.conrelid
      JOIN pg_namespace AS n ON n.oid = cl.relnamespace
      LEFT JOIN pg_class AS ref ON ref.oid = c.confrelid
     WHERE n.nspname = 'public' AND c.contype IN ('p', 'f')
    """
)


async def _normalize_legacy_pk_fk_names(database_url: str) -> list[tuple[str, str, str]]:
    """Rename pre-convention PK and FK constraints to the convention's names.

    Postgres names what the pre-convention models left unnamed itself:
    ``<table>_pkey`` and ``<table>_<column>_fkey``. Alembic does not compare
    those two kinds, so they never refuse a bootstrap — but they stay
    non-canonical and bite the first revision that names them. Before the
    bootstrap's comparison, each such constraint whose convention name the
    models' metadata knows is renamed in place — both the old and the new
    name are derived, never hardcoded: the catalog yields the constraint's
    identity (table, columns, referenced table) and the legacy default it
    carries, the metadata yields the convention name for that same identity
    (CodeRabbit round 1, 2026-11-01).

    Idempotent by construction: a name already at its convention form, or
    anything that is not Postgres's legacy default, is left alone. The
    renames run in one transaction on their own connection — the caller has
    already taken the pre-migration dump (D5), so this write is covered.

    Returns the applied renames as ``(table, old, new)``; each is logged at
    INFO, one line naming the bootstrap normalization.
    """
    register_models()
    expected_pk: dict[str, str] = {}
    expected_fk: dict[tuple[str, tuple[str, ...], str], str] = {}
    for table in Base.metadata.tables.values():
        primary_key = table.primary_key
        # `name` is `str | _NoneName` — SQLAlchemy's unnamed sentinel mimics
        # None; only a rendered convention name counts here.
        if primary_key.columns and isinstance(primary_key.name, str):
            expected_pk[table.name] = primary_key.name
        for constraint in table.constraints:
            if isinstance(constraint, ForeignKeyConstraint) and isinstance(constraint.name, str):
                identity = (
                    table.name,
                    tuple(column.name for column in constraint.columns),
                    constraint.referred_table.name,
                )
                expected_fk[identity] = constraint.name
    renames: list[tuple[str, str, str]] = []
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for table_name, constraint_name, kind, columns, referred_table in (
                await connection.execute(_CONSTRAINT_CATALOG)
            ).fetchall():
                if table_name not in Base.metadata.tables:
                    continue
                if kind == "p":
                    expected = expected_pk.get(table_name)
                    legacy = f"{table_name}_pkey"
                else:
                    identity = (table_name, tuple(columns or ()), referred_table)
                    expected = expected_fk.get(identity)
                    legacy = f"{table_name}_{'_'.join(columns or ())}_fkey"
                if expected is None or constraint_name != legacy:
                    continue
                await connection.execute(
                    # Identifiers from the catalog; DDL takes no bind params.
                    text(
                        f'ALTER TABLE "{table_name}" RENAME CONSTRAINT '
                        f'"{constraint_name}" TO "{expected}"'
                    )
                )
                renames.append((table_name, constraint_name, expected))
    finally:
        await engine.dispose()
    for table_name, old, new in renames:
        logger.info(
            "bootstrap normalization: renamed constraint %s on %s to %s", old, table_name, new
        )
    return renames


def _rename_unique_constraint_pairs(
    connection: Connection, diff: list[Any]
) -> list[tuple[str, str, str]]:
    """Apply a diff's remove+add unique pairs as ``RENAME CONSTRAINT`` statements.

    Alembic does not know renames: a unique constraint whose only difference
    is its name comes back as a remove of the old and an add of the new. For
    a pre-convention database that pair is exactly the convention rename
    (``users_email_key`` → ``uq_users_email``): same table, same columns.
    Such a pair is applied as the rename it is instead of refusing the
    database (CodeRabbit round 1, 2026-11-01); anything else in the diff
    stays a refusal. Idempotent: after the rename, the re-comparison has no
    pair to find. Every applied rename is logged at INFO.
    """
    removes = [
        op[1]
        for op in diff
        if len(op) == 2 and op[0] == "remove_constraint" and isinstance(op[1], UniqueConstraint)
    ]
    adds = [
        op[1]
        for op in diff
        if len(op) == 2 and op[0] == "add_constraint" and isinstance(op[1], UniqueConstraint)
    ]
    renames: list[tuple[str, str, str]] = []
    for removed in removes:
        old = removed.name
        if not old:
            continue
        columns = [column.name for column in removed.columns]
        match = next(
            (
                added
                for added in adds
                if added.name
                and added.table.name == removed.table.name
                and [column.name for column in added.columns] == columns
            ),
            None,
        )
        if match is None or match.name is None:
            continue
        renames.append((removed.table.name, old, match.name))
    for table_name, old, new in renames:
        connection.execute(
            # Identifiers from the catalog/metadata; DDL takes no bind params.
            text(f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old}" TO "{new}"')
        )
        logger.info(
            "bootstrap normalization: renamed unique constraint %s on %s to %s",
            old,
            table_name,
            new,
        )
    return renames


async def _drop_scratch_database(server: str) -> None:
    """Drop the bootstrap's scratch database, if it exists; leftovers included."""
    engine = create_async_engine(f"{server}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(
                # A fixed module constant, no interpolation.
                text(f"DROP DATABASE IF EXISTS {BOOTSTRAP_SCRATCH_DATABASE} WITH (FORCE)")
            )
    finally:
        await engine.dispose()


async def _baseline_metadata_or_refuse(config: Config, database_url: str) -> tuple[str, MetaData]:
    """Replay the baseline revision on a scratch database; reflect its schema.

    The schema an unversioned database is compared against is the *baseline*
    revision's replay, not head's models (design D4, CodeRabbit round 1,
    2026-11-01): a database that never had a history matches the release
    schema it shipped with, and the bootstrap stamps that baseline so the
    normal flow upgrades it to head afterwards. The scratch lives on the
    same server — the admin URL is the database URL's own, with ``postgres``
    as the database; testsupport's SERVER is the test server and wrong at
    runtime. It is dropped once the metadata is reflected, and any leftover
    from a crashed run is dropped with ``FORCE`` before the replay.

    A server this user may not sidecar a database on (no ``CREATE DATABASE``
    right) is a refusal naming the operator's way out — stamp the baseline
    by hand with alembic; every other failure surfaces unchanged.
    """
    baseline = baseline_revision(config)
    server = database_url.rsplit("/", 1)[0]
    scratch_url = f"{server}/{BOOTSTRAP_SCRATCH_DATABASE}"
    admin_engine = create_async_engine(f"{server}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as connection:
            try:
                await connection.execute(
                    # A fixed module constant, no interpolation.
                    text(f"DROP DATABASE IF EXISTS {BOOTSTRAP_SCRATCH_DATABASE} WITH (FORCE)")
                )
                await connection.execute(text(f"CREATE DATABASE {BOOTSTRAP_SCRATCH_DATABASE}"))
            except Exception as exc:
                if getattr(exc.__cause__, "sqlstate", None) != INSUFFICIENT_PRIVILEGE:
                    raise
                raise MigrationRefused(
                    "the bootstrap compares an unversioned database against the baseline "
                    f"revision's replay on a scratch database ({BOOTSTRAP_SCRATCH_DATABASE}), "
                    f"and it could not be created: {exc}; grant this user the right to "
                    "CREATE DATABASE, or stamp the baseline by hand: "
                    "alembic stamp <baseline revision>"
                ) from exc
    finally:
        await admin_engine.dispose()

    metadata = MetaData()
    previous = environ["NARRE_DATABASE_URL"]
    try:
        # env.py reads the URL from the environment only: the replay aims at
        # the scratch database, not at the caller's.
        environ["NARRE_DATABASE_URL"] = scratch_url
        await ensure_extensions(scratch_url)
        await asyncio.to_thread(command.upgrade, config, baseline)
        engine = create_async_engine(scratch_url)
        try:
            async with engine.connect() as connection:
                await connection.run_sync(metadata.reflect)
        finally:
            await engine.dispose()
    finally:
        environ["NARRE_DATABASE_URL"] = previous
        await _drop_scratch_database(server)
    version_table = metadata.tables.get("alembic_version")
    if version_table is not None:
        metadata.remove(version_table)
    return baseline, metadata


async def prepare_database(
    database_url: str,
    *,
    backup: bool = True,
    backup_dir: Path | None = None,
    config: Config | None = None,
) -> MigrationOutcome:
    """Bring one database to the history's head, refusing to guess.

    The state the database starts in decides the path: a fresh one is
    replayed from nothing; one with tables but no ``alembic_version`` is
    bootstrapped — its constraint names are normalized to the naming
    convention's, and when the schema then equals the *baseline* revision's
    replayed schema it is stamped at that baseline (the upgrade below
    carries it to head), else refused with the differences named (design
    D4, CodeRabbit round 1, 2026-11-01); a versioned one is upgraded in
    place, but a revision outside this app's history is refused with both
    versions named, and so is an upgrade that ends anywhere but head. The
    config defaults to the repo's own history; a caller may pass another
    ``Config`` — a test pointing ``script_location`` at a copied history —
    and head, baseline, stamp and upgrade all follow it.

    The whole run — the extensions pre-step, the version reads, the
    pre-migration dump, the upgrade — executes under a session-level
    ``pg_advisory_lock`` held on its own connection: two concurrent starts
    serialise, and cannot race each other's extension catalog or replay;
    the second finds head already reached and does nothing. The lock is
    released in a ``finally``, so a failed run cannot hold the next one
    hostage.

    While revisions are pending, the run is preceded by a ``pg_dump`` copy
    (design D5): a run that is about to write — a first upgrade's stamp, an
    upgrade behind head — either produces a restorable dump or migrates
    nothing. The copy runs only when the database holds tables: the
    dump protects prose, and an empty schema has none, so a fresh first boot
    takes none — which also keeps pg_dump out of the first boot's
    requirements (product owner, 2026-10-31). ``backup=False`` — a caller
    that owes no dump, like ``init_schema`` — and
    ``NARRE_MIGRATION_BACKUP=skip`` — an operator who took their own copy —
    leave it out; the copy goes to ``backup_dir``, else ``NARRE_BACKUP_DIR``
    (default ``./backups``).

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

    head = head_revision(config)
    config = config if config is not None else default_config()

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
                # Inside the lock: two cold starts must not race the CREATE
                # EXTENSION statements — the loser would die on the catalog.
                await _extensions_or_refuse(database_url)

                async with engine.connect() as connection:
                    current = await current_revision(connection)
                    has_tables = await _has_tables(connection)
                    if current is None and has_tables:
                        # A bootstrap candidate: tables but no history. The
                        # decision — normalize the constraint names, compare
                        # against the baseline revision, stamp or refuse —
                        # runs after the dump below, so no write of this run
                        # precedes the restorable copy (D5).
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

                # Revisions are pending when the run will really write — a
                # fresh replay, a first upgrade's stamp, a versioned one
                # behind head — and the restorable copy happens then (D5),
                # but only when the database holds tables: the dump protects
                # prose, and an empty schema has none — a fresh first boot
                # skips it, which also keeps pg_dump out of the first boot's
                # requirements (product owner, 2026-10-31). This caller owes
                # none when ``backup=False``, like ``init_schema``, and
                # ``NARRE_MIGRATION_BACKUP=skip`` says the operator already
                # took their own copy. The copy precedes the stamp below: a
                # run with pending revisions either produces it or migrates
                # nothing.
                if (
                    (current is None or current != head)
                    and has_tables
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

                stamp_target = head
                if bootstrapped:
                    # The bootstrap (design D4, CodeRabbit round 1,
                    # 2026-11-01). First the constraint names: a database
                    # created before the naming convention (D9) carries
                    # Postgres's own PK and FK defaults, and alembic renders
                    # its legacy-named uniques as remove+add pairs — both are
                    # renamed to the convention's, not held against the
                    # database.
                    await _normalize_legacy_pk_fk_names(database_url)

                    # The schema to match is the *baseline* revision's
                    # replayed schema: an unversioned database matches the
                    # release it shipped with, not head's models. Matching
                    # earns the stamp at the baseline — the upgrade below
                    # then carries it to head through every revision it
                    # missed; anything else after the normalization is
                    # refused, with the differences named.
                    baseline, baseline_metadata = await _baseline_metadata_or_refuse(
                        config, database_url
                    )
                    stamp_target = baseline
                    async with engine.connect() as connection:
                        diff = await connection.run_sync(
                            lambda sync_connection: diff_against_models(
                                config, sync_connection, baseline_metadata
                            )
                        )
                    if diff:
                        # A remove+add pair of the same unique constraint is
                        # the convention rename; applied as such, then the
                        # comparison runs again — whatever still differs is
                        # the refusal's subject.
                        async with engine.begin() as connection:
                            renamed = await connection.run_sync(
                                lambda sync_connection: _rename_unique_constraint_pairs(
                                    sync_connection, diff
                                )
                            )
                        if renamed:
                            async with engine.connect() as connection:
                                diff = await connection.run_sync(
                                    lambda sync_connection: diff_against_models(
                                        config, sync_connection, baseline_metadata
                                    )
                                )
                    if diff:
                        raise MigrationRefused(
                            "the database has tables but no migration history, and its "
                            "schema does not match the baseline revision "
                            f"{baseline} ({_describe(diff)}); refusing to guess — align "
                            "the schema with the models by hand or reset the database"
                        )

                if bootstrapped:
                    await asyncio.to_thread(command.stamp, config, stamp_target)

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
