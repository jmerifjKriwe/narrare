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
import shutil
import subprocess
from os import environ
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db import migrate as migrate_module
from app.kernel.db.backup import BackupFailed, dump_database
from app.kernel.db.init import reset_schema
from app.kernel.db.migrate import (
    UNDEFINED_TABLE,
    MigrationRefused,
    current_revision,
    default_config,
    diff_against_models,
    head_revision,
    prepare_database,
)
from app.kernel.db.testsupport import drop_every_table

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy.engine import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection


@pytest.fixture(autouse=True)
def _restore_database_url() -> Iterator[None]:
    """Put ``NARRE_DATABASE_URL`` back after a test exported its own URL."""
    previous = environ.get("NARRE_DATABASE_URL")
    yield
    if previous is None:
        environ.pop("NARRE_DATABASE_URL", None)
    else:
        environ["NARRE_DATABASE_URL"] = previous


@pytest.fixture(autouse=True)
def _skip_migration_backups(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the gates from dumping on every run — the dump tests opt back in.

    Every ``prepare_database`` call here faces pending revisions, and the
    production answer — dump first — would fill ``./backups`` on every
    ``just test`` with copies of an empty database. ``skip`` says an operator
    has taken their own copy; the tests that exercise the dump itself set
    ``NARRE_MIGRATION_BACKUP`` back to ``pg_dump``.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "skip")


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
    await drop_every_table(url)
    # env.py drives alembic through an asyncio.run of its own, which cannot
    # start inside this test's loop; the upgrade gets its own thread.
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
    assert await _models_diff(url) == []


# ---------------------------------------------------------------------------
# prepare_database — the unattended startup path (D3.4, D4, D6)
# ---------------------------------------------------------------------------


async def test_fresh_database_is_upgraded(url: str) -> None:
    """An empty database is replayed from nothing — no bootstrap, no stamp."""
    await drop_every_table(url)

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
    await drop_every_table(url)
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


# ---------------------------------------------------------------------------
# The failure paths (D5, review focus 3 and 5): the lock, the pre-migration
# dump, and a run that must migrate nothing
# ---------------------------------------------------------------------------


class _WithSQLState(Exception):  # noqa: N818  a stand-in for the dialect's wrapped error
    """A stand-in for the dialect's wrapped error, carrying its SQLSTATE."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


class _ExplodingConnection:
    """The one method ``current_revision`` uses — and it fails, as asked."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def begin_nested(self) -> _ExplodingConnection:
        return self

    async def __aenter__(self) -> _ExplodingConnection:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, _statement: object) -> None:
        raise self._error


async def test_extension_privilege_failure_is_refused(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A role without CREATE EXTENSION is refused with the platform's way out (D7)."""

    async def _no_rights(_database_url: str) -> None:
        raise RuntimeError("permission denied to create extension") from _WithSQLState("42501")

    monkeypatch.setattr(migrate_module, "ensure_extensions", _no_rights)

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup=False)

    assert "create extensions" in str(refused.value)  # the sentence, complete


async def test_unreachable_database_surfaces_unchanged(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure that is not a privilege problem surfaces as itself, not a refusal."""

    async def _down(_database_url: str) -> None:
        raise ConnectionError("could not connect")

    monkeypatch.setattr(migrate_module, "ensure_extensions", _down)

    with pytest.raises(ConnectionError):
        await prepare_database(url, backup=False)


async def test_current_revision_reraises_other_programming_errors() -> None:
    """A ProgrammingError that is not undefined-table raises — it is not None."""
    cause = _WithSQLState("42601")  # syntax error: a failure, not an empty history
    error = ProgrammingError("SELECT version_num FROM alembic_version", {}, cause)
    error.__cause__ = cause

    with pytest.raises(ProgrammingError):
        await current_revision(cast("AsyncConnection", _ExplodingConnection(error)))


async def test_two_version_rows_are_refused(url: str) -> None:
    """Two heads in the version table are refused — either alone would hide the other."""
    await drop_every_table(url)
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("INSERT INTO alembic_version VALUES ('ffff')"))
    finally:
        await engine.dispose()

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup=False)

    message = str(refused.value)
    assert "exactly one" in message  # the count, not the unknown-revision wording
    assert head_revision() in message and "ffff" in message  # both rows, named


async def test_dump_and_restore_round_trip(url: str, tmp_path: Path) -> None:
    """The toolchain itself: a seeded novel survives dump and restore (D5).

    The repository's own snapshot and support restores need pg_dump and
    pg_restore; a missing binary is an install with a named package, never
    a skip.
    """
    if shutil.which("pg_dump") is None or shutil.which("pg_restore") is None:
        pytest.fail("pg_dump/pg_restore are not on PATH — install postgresql-client-17")

    await reset_schema(url)
    user_id, novel_id = uuid4(), uuid4()
    title = "Die Prüfung"
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO users (id, created_at) VALUES (:id, now())"), {"id": user_id}
            )
            await connection.execute(
                text(
                    "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                    "VALUES (:id, :user_id, :title, now(), now())"
                ),
                {"id": novel_id, "user_id": user_id, "title": title},
            )
    finally:
        await engine.dispose()

    dump = await dump_database(url, tmp_path)
    assert dump.read_bytes()[:5] == b"PGDMP"

    # The round trip: a fresh scratch database on the same server, restored
    # from the dump, holds the seeded novel — title byte-identical, umlauts
    # and all. pg_restore speaks plain postgresql://; the engines keep the
    # +asyncpg URL they were given.
    server_sync = url.replace("+asyncpg", "").rsplit("/", 1)[0]
    server = url.rsplit("/", 1)[0]
    scratch = "narrare_v2_migrations_roundtrip"
    admin = create_async_engine(f"{server}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)"))
            await connection.execute(text(f"CREATE DATABASE {scratch}"))
        try:
            # The toolchain under test, fixed argv.
            restore = await asyncio.to_thread(
                subprocess.run,
                ["pg_restore", "--no-owner", "--dbname", f"{server_sync}/{scratch}", str(dump)],
                capture_output=True,
                check=False,
            )
            assert restore.returncode == 0, restore.stderr.decode(errors="replace")

            engine = create_async_engine(f"{server}/{scratch}")
            try:
                async with engine.connect() as connection:
                    restored: str | None = await connection.scalar(
                        text("SELECT title FROM novels WHERE id = :id"), {"id": novel_id}
                    )
                    assert restored == title
            finally:
                await engine.dispose()
        finally:
            # Whatever went wrong above, the scratch database does not outlive
            # the test.
            async with admin.connect() as connection:
                await connection.execute(text(f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)"))
    finally:
        await admin.dispose()


async def test_pending_revision_writes_a_dump(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run with pending revisions takes the restorable copy first (D5)."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    await drop_every_table(url)

    outcome = await prepare_database(url, backup_dir=tmp_path)

    assert outcome.from_revision is None  # the full replay was pending
    assert outcome.backup is not None
    assert outcome.backup.parent == tmp_path
    assert outcome.backup.read_bytes()[:5] == b"PGDMP"


async def test_up_to_date_database_writes_no_dump(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second run has nothing pending: no dump, no DDL, head to head (D5)."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    await drop_every_table(url)
    first = await prepare_database(url, backup_dir=tmp_path)
    assert first.backup is not None  # sanity: the pending run did take its dump
    files_before = sorted(path.name for path in tmp_path.iterdir())

    # The versioned-at-head path: two consecutive runs, the second does nothing.
    second = await prepare_database(url, backup_dir=tmp_path)

    assert (second.from_revision, second.to_revision) == (head_revision(), head_revision())
    assert second.bootstrapped is False
    assert second.backup is None
    assert sorted(path.name for path in tmp_path.iterdir()) == files_before
    assert await _models_diff(url) == []  # and no DDL happened either


async def test_failing_backup_command_migrates_nothing(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No dump, no migration: the refusal names both ways out (review focus 5)."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_COMMAND", "false {url} {file}")
    await drop_every_table(url)

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)

    message = str(refused.value)
    assert isinstance(refused.value.__cause__, BackupFailed)
    assert "postgresql-client" in message  # way out one: install the client
    assert "NARRE_MIGRATION_BACKUP=skip" in message  # way out two: own copy taken
    # Nothing migrated: the version table never came into existence.
    with pytest.raises(ProgrammingError) as missing:
        await _version_row(url)
    assert getattr(missing.value.__cause__, "sqlstate", None) == UNDEFINED_TABLE
    # The failed run released the lock in its finally: the next start works.
    recovered = await prepare_database(url, backup=False)
    assert recovered.to_revision == head_revision()


async def test_unwritable_backup_directory_is_a_named_refusal(url: str, tmp_path: Path) -> None:
    """A dump directory that cannot be created or written is BackupFailed, not a crash."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)  # read and enter, no write — enough to fail both ways

    try:
        # The directory cannot be created under the locked parent.
        with pytest.raises(BackupFailed):
            await dump_database(url, locked / "backups")
        # The stdout sink cannot be opened inside the locked directory.
        with pytest.raises(BackupFailed):
            await dump_database(url, locked)
    finally:
        locked.chmod(0o700)  # let tmp_path's own cleanup remove it


async def test_malformed_backup_command_template_is_a_named_refusal(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A template that cannot be resolved is BackupFailed, not KeyError/ValueError."""
    for template in (
        "pg_dump {url",  # ValueError: single '{' in the format string
        "pg_dump {oops} {file}",  # KeyError: a placeholder the template does not get
        'pg_dump "{url} {file}',  # ValueError: shlex finds no closing quotation
    ):
        monkeypatch.setenv("NARRE_BACKUP_COMMAND", template)
        with pytest.raises(BackupFailed):
            await dump_database(url, tmp_path)


async def test_stdout_that_is_not_a_dump_is_refused(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Output that no pg_restore could read is refused — no valid-looking dump left."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_COMMAND", "printf 'not a dump'")
    await drop_every_table(url)

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)

    assert isinstance(refused.value.__cause__, BackupFailed)
    assert list(tmp_path.iterdir()) == []  # nothing that looks like a dump was kept
    # Nothing migrated: the version table never came into existence.
    with pytest.raises(ProgrammingError) as missing:
        await _version_row(url)
    assert getattr(missing.value.__cause__, "sqlstate", None) == UNDEFINED_TABLE


async def test_dump_retention_keeps_the_newest(url: str, tmp_path: Path) -> None:
    """The newest ``keep`` dumps remain; the dump just written is never its own victim."""
    dumps = [await dump_database(url, tmp_path) for _ in range(4)]
    # keep=3: the oldest is gone, the newest three remain.
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        dump.name for dump in dumps[1:]
    )

    fresh = await dump_database(url, tmp_path, keep=1)
    assert [path.name for path in tmp_path.iterdir()] == [fresh.name]

    # keep=0 does not delete the dump it just wrote.
    kept_anyway = await dump_database(url, tmp_path, keep=0)
    assert kept_anyway.exists()
    assert [path.name for path in tmp_path.iterdir()] == [kept_anyway.name]


async def test_concurrent_starts_migrate_once(url: str) -> None:
    """Two starts at once: the lock serialises them, both serve (review focus 3).

    The second caller waits on ``pg_advisory_lock`` and then finds head
    already reached — both return, and the version table holds exactly one
    row.
    """
    await drop_every_table(url)

    outcomes = await asyncio.gather(prepare_database(url), prepare_database(url))

    assert [outcome.to_revision for outcome in outcomes] == [head_revision(), head_revision()]
    assert {outcome.from_revision for outcome in outcomes} == {None, head_revision()}
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            rows: int | None = await connection.scalar(text("SELECT count(*) FROM alembic_version"))
            assert rows == 1
    finally:
        await engine.dispose()
