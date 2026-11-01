"""The migration gates (design D3) and the startup path's refusal tests.

All four design gates live here: the history has exactly one head (D3.1), an
empty database replayed to head is indistinguishable from what the models
declare (D3.2 — the gate that keeps the two schema paths identical, D12), the
checked-in 0.2.0 snapshot bootstraps with its prose intact and is then carried
through the history's real post-baseline revision (D3.3 — the bootstrap path
plus the behind-head replay, constraint DDL against a table holding prose),
and the bootstrap branch stamps an equal models-built schema while
refusing a drifted or unknown-revision one by name (D3.4, D4, D6).

``prepare_database`` is the function the gates drive: the same one
``just db-init`` and the API suite's session fixture run.
"""

import asyncio
import shutil
import subprocess
from os import environ, utime
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import Uuid, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.auth import LOCAL_USER_ID
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
    from typing import IO

    from alembic.config import Config
    from sqlalchemy import Table
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
    ``just test`` with copies of the test database. ``skip`` says an operator
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


def test_head_revision_is_found_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``head_revision`` works from a directory that is not the repo root.

    Startup runs wherever the operator launched the app from; a
    ``script_location`` resolved against the process's working directory
    made this very first read of the history die with ``CommandError``
    everywhere but the repo root. The ini names its own location instead
    (``%(here)s``), so the history is found from any directory.
    """
    monkeypatch.chdir(tmp_path)
    head = head_revision()
    # The head is this history's: its id names a file in the versions
    # directory beside this test.
    versions = Path(__file__).parent.parent / "migrations" / "versions"
    assert any(file.name.startswith(f"{head}_") for file in versions.glob("*.py"))


async def test_empty_database_migrated_equals_the_models(url: str) -> None:
    # The gate's claim is about an *empty* database: whichever test ran before
    # this one left its tables behind, so the drop happens here, not only in
    # the module fixture (pytest-randomly shuffles this module).
    await drop_every_table(url)
    # env.py drives alembic through an asyncio.run of its own, which cannot
    # start inside this test's loop; the upgrade gets its own thread.
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
    assert await _models_diff(url) == []


# The snapshot the gate below loads: the release schema, checked in. Produced
# once by replaying the history to head on a scratch database — gate D3.2
# proves migrated == models, so the dump is the models' schema by
# construction — with ``pg_dump --schema-only --no-owner --no-privileges``,
# then stripped of the ``alembic_version`` table, the ``CREATE EXTENSION``
# lines and pg_dump's \restrict/\unrestrict psql guards (which carry a random
# token): the version table is the history's own bookkeeping, the extensions
# are the pre-step ``prepare_database`` runs before anything else, and the
# guards are psql meta-commands asyncpg cannot run. No row is the 0.2.0
# exception — that release predates the history, so its snapshot bootstraps.
# Releases after 0.2.0 ship the row (the design's snapshot rule: hand-appended,
# since a schema-only dump never emits data) and exercise the versioned path.
SNAPSHOT = Path(__file__).parent / "fixtures" / "schema_0.2.0.sql"


async def _load_snapshot(database_url: str, snapshot: Path) -> None:
    """The snapshot's DDL, statement by statement, in one transaction.

    pg_dump writes plain, semicolon-terminated SQL with no function bodies,
    so the statements separate on ``;`` at end of line — a boundary no
    string literal in this fixture contains — and the ``--`` comment lines
    it interleaves (statement headers, the dump banner) drop out per chunk.
    One transaction: the database goes from empty to the release schema, or
    not at all.
    """
    script = snapshot.read_text(encoding="utf-8")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for chunk in script.split(";\n"):
                statement = "\n".join(
                    line for line in chunk.splitlines() if not line.lstrip().startswith("--")
                ).strip()
                if statement:
                    await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def _seed_prose(database_url: str) -> tuple[Any, Any, str, str]:
    """The prose seed the bootstrap gates load: a user, a novel and its chapter.

    Returns ``(novel_id, chapter_id, title, body)`` — the ids the prose is
    read back by, and the title and body the byte-identity assertions name.
    """
    novel_id, chapter_id = uuid4(), uuid4()
    title, body = "Die Prüfung", "Wort für Wort"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO users (id, created_at) VALUES (:id, now())"),
                {"id": LOCAL_USER_ID},
            )
            await connection.execute(
                text(
                    "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                    "VALUES (:id, :user_id, :title, now(), now())"
                ),
                {"id": novel_id, "user_id": LOCAL_USER_ID, "title": title},
            )
            await connection.execute(
                text(
                    "INSERT INTO chapters (id, user_id, novel_id, title, position, body, "
                    "created_at, updated_at) "
                    "VALUES (:id, :user_id, :novel_id, :title, 0, :body, now(), now())"
                ),
                {
                    "id": chapter_id,
                    "user_id": LOCAL_USER_ID,
                    "novel_id": novel_id,
                    "title": title,
                    "body": body,
                },
            )
    finally:
        await engine.dispose()
    return novel_id, chapter_id, title, body


async def test_release_snapshot_upgrades_without_losing_prose(url: str) -> None:
    """This release's 0.2.0 snapshot bootstraps with its prose intact (D3.3).

    The fixture is this release's checked-in schema (0.2.0), and it carries
    no ``alembic_version`` — 0.2.0 predates the history, the one bootstrap-
    exception release (releases after it ship the row per the design's
    snapshot rule and exercise the versioned path) — so this gate exercises
    the bootstrap path: exactly the upgrade the
    go-live release performs on databases created by ``create_all``. The
    bootstrap stamps the baseline, and the history's post-baseline revision
    — the unique chapter positions — then replays for real: constraint DDL
    runs against a table that already holds a chapter, and the prose is
    read back byte-identical on the far side. This is the behind-head
    replay the gate exists for, through real history.
    """
    # The gate's claim is about the snapshot's database alone: whichever test
    # ran before this one left its tables behind, so the drop happens here,
    # not only in the module fixture (pytest-randomly shuffles this module).
    await drop_every_table(url)
    await _load_snapshot(url, SNAPSHOT)

    novel_id, chapter_id, title, body = await _seed_prose(url)

    outcome = await prepare_database(url, backup=False)
    assert outcome.from_revision is None
    assert outcome.bootstrapped is True  # no history in the dump: the stamp, not a replay
    assert outcome.to_revision == head_revision()

    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            chapter_body: str | None = await connection.scalar(
                text("SELECT body FROM chapters WHERE id = :id"), {"id": chapter_id}
            )
            novel_title: str | None = await connection.scalar(
                text("SELECT title FROM novels WHERE id = :id"), {"id": novel_id}
            )
    finally:
        await engine.dispose()
    assert chapter_body is not None and chapter_body.encode("utf-8") == body.encode("utf-8")
    assert novel_title == title
    assert await _models_diff(url) == []  # the stamped schema is still the models'
    assert await _version_row(url) == head_revision()


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


# ---------------------------------------------------------------------------
# Pre-convention databases and the baseline revision (CodeRabbit round 1,
# 2026-11-01): the bootstrap normalizes constraint names and stamps the
# baseline, not head
# ---------------------------------------------------------------------------


async def _constraint_names(database_url: str, table: str) -> set[str]:
    """The constraint names one table carries, straight from the catalog."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT c.conname FROM pg_constraint AS c "
                    "JOIN pg_class AS cl ON cl.oid = c.conrelid "
                    "JOIN pg_namespace AS n ON n.oid = cl.relnamespace "
                    "WHERE cl.relname = :table AND n.nspname = 'public'"
                ),
                {"table": table},
            )
            return {str(row[0]) for row in rows}
    finally:
        await engine.dispose()


async def _revert_to_pre_convention_names(database_url: str) -> None:
    """Rename constraints back to Postgres's pre-convention defaults.

    A database created from the models before the naming convention landed
    (D9) carries Postgres's own default names — ``users_email_key``,
    ``users_pkey``, ``<table>_<column>_fkey`` — exactly what a real
    0.2.0-era database holds.
    """
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE users RENAME CONSTRAINT uq_users_email TO users_email_key")
            )
            await connection.execute(
                text("ALTER TABLE users RENAME CONSTRAINT pk_users TO users_pkey")
            )
            await connection.execute(
                text(
                    "ALTER TABLE chapters RENAME CONSTRAINT fk_chapters_user_id_users "
                    "TO chapters_user_id_fkey"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE novels RENAME CONSTRAINT fk_novels_user_id_users "
                    "TO novels_user_id_fkey"
                )
            )
    finally:
        await engine.dispose()


async def test_pre_convention_database_is_carried_to_the_convention_names(url: str) -> None:
    """A pre-convention database bootstraps — its constraint names end canonical.

    The bootstrap's exact audience: a database built from the pre-convention
    models is refused today, because ``compare_metadata`` renders the
    legacy-named unique constraint as remove+add. The bootstrap normalizes
    instead (CodeRabbit round 1, 2026-11-01): uniques through the diff pair,
    PK and FK through the catalog — and the names ARE the convention's
    afterwards, asserted here by catalog query.
    """
    await reset_schema(url)
    user_id = uuid4()
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO users (id, created_at) VALUES (:id, now())"), {"id": user_id}
            )
    finally:
        await engine.dispose()
    await _revert_to_pre_convention_names(url)

    outcome = await prepare_database(url, backup=False)

    assert outcome.from_revision is None
    assert outcome.bootstrapped is True
    assert outcome.to_revision == head_revision()
    # The renames carried no data: the seeded user survives.
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            users: int | None = await connection.scalar(text("SELECT count(*) FROM users"))
            assert users == 1
    finally:
        await engine.dispose()
    users_names = await _constraint_names(url, "users")
    assert {"uq_users_email", "pk_users"} <= users_names
    assert not {"users_email_key", "users_pkey"} & users_names
    chapters_names = await _constraint_names(url, "chapters")
    assert "fk_chapters_user_id_users" in chapters_names
    assert "chapters_user_id_fkey" not in chapters_names
    novels_names = await _constraint_names(url, "novels")
    assert "fk_novels_user_id_users" in novels_names
    assert "novels_user_id_fkey" not in novels_names
    assert await _models_diff(url) == []  # nothing but the names was touched
    assert await _version_row(url) == head_revision()


async def test_drifted_pre_convention_database_is_still_refused(url: str) -> None:
    """The normalization is not an amnesty: real drift still refuses, by name.

    Legacy constraint names on top of a dropped column must not end in a
    stamp — the bootstrap normalizes the names, then refuses the drift it
    still sees.
    """
    await reset_schema(url)
    await _revert_to_pre_convention_names(url)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("ALTER TABLE chapters DROP COLUMN title"))
    finally:
        await engine.dispose()

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup=False)

    message = str(refused.value)
    assert "add_column" in message
    assert "chapters" in message
    assert "title" in message


def _probe_history(tmp_path: Path, revision_id: str, upgrade: str) -> Config:
    """A copied history with one probe revision on top of its head.

    The probe stands in for the next revision a real history grows: the
    repo's own ``versions/`` directory stays untouched, and the returned
    ``Config`` aims at the copy so a test can put head beyond the database
    it drives.
    """
    probe_migrations = tmp_path / "migrations"
    shutil.copytree(Path(__file__).parent.parent / "migrations", probe_migrations)
    head = head_revision()
    (probe_migrations / "versions" / f"{revision_id}_probe.py").write_text(
        f'"""probe\n'
        f"\n"
        f"Revision ID: {revision_id}\n"
        f"Revises: {head}\n"
        f"Create Date: 2026-11-01\n"
        f"\n"
        f'"""\n'
        f"\n"
        f"import sqlalchemy as sa\n"
        f"from alembic import op\n"
        f"\n"
        f'revision: str = "{revision_id}"\n'
        f'down_revision: str | None = "{head}"\n'
        f"branch_labels: str | None = None\n"
        f"depends_on: str | None = None\n"
        f"\n"
        f"\n"
        f"def upgrade() -> None:\n"
        f"{upgrade}\n"
        f"\n"
        f"\n"
        f"def downgrade() -> None:\n"
        f"    pass\n",
        encoding="utf-8",
    )
    probe_config = default_config()
    probe_config.set_main_option("script_location", str(probe_migrations))
    return probe_config


async def test_unversioned_database_is_stamped_at_the_baseline_revision(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An old unversioned database is stamped at the BASELINE revision, not head (D4).

    The bootstrap's first comparison target is the baseline revision's
    replayed schema — a database that never had a history matches the
    release schema it shipped with, not head's models. One probe revision
    on top of the history makes the difference observable: the database is
    stamped at the baseline and upgraded through everything above it (the
    real post-baseline revision, then the probe — its column exists
    afterwards); stamping at head would have skipped the replay entirely.
    This is also the dump-on-versioned-behind coverage (D5): a
    pending upgrade on a table-bearing database takes the restorable copy
    first.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    probe_id = "5ea50f00d000"
    probe_config = _probe_history(
        tmp_path,
        probe_id,
        '    op.add_column("chapters", sa.Column("probe", sa.Text(), nullable=True))',
    )

    await drop_every_table(url)
    await _load_snapshot(url, SNAPSHOT)
    novel_id, chapter_id, title, body = await _seed_prose(url)

    outcome = await prepare_database(url, backup=True, backup_dir=tmp_path, config=probe_config)

    assert outcome.from_revision is None
    assert outcome.bootstrapped is True
    assert outcome.to_revision == probe_id  # this history's head, not the repo's
    assert await _version_row(url) == probe_id
    # Stamped at the baseline: the probe revision was really applied on top
    # of it — a stamp at head would have skipped it and left no column.
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            probe_values: int | None = await connection.scalar(
                text("SELECT count(*) FROM chapters WHERE probe IS NOT NULL")
            )
            chapter_body: str | None = await connection.scalar(
                text("SELECT body FROM chapters WHERE id = :id"), {"id": chapter_id}
            )
            novel_title: str | None = await connection.scalar(
                text("SELECT title FROM novels WHERE id = :id"), {"id": novel_id}
            )
    finally:
        await engine.dispose()
    assert probe_values == 0  # the column exists, every value null — the add ran
    assert chapter_body is not None and chapter_body.encode("utf-8") == body.encode("utf-8")
    assert novel_title == title
    # The restorable copy (D5): pending revisions and tables — the dump ran.
    assert outcome.backup is not None
    assert outcome.backup.parent == tmp_path
    assert outcome.backup.read_bytes()[:5] == b"PGDMP"
    # The scratch database the comparison replayed the baseline on is gone —
    # the name is derived from the target database, so this is its own.
    scratch = migrate_module._scratch_database_name(url)  # pyright: ignore[reportPrivateUsage]
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            leftovers: int | None = await connection.scalar(
                text("SELECT count(*) FROM pg_database WHERE datname = :name"), {"name": scratch}
            )
            assert leftovers == 0
    finally:
        await engine.dispose()


async def test_models_built_database_is_stamped_at_head(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A models-built database stamps at HEAD when the history has moved on (D4).

    The second real population of an unversioned database: built from the
    models at head (``reset_schema``, the API suite's client fixture, any
    ``create_all``). Against a history whose head is beyond the baseline it
    equals head's models, not the baseline replay — the stamp goes to head,
    and the upgrade afterwards has nothing to apply. Branch 1 — the
    0.2.0-era database, stamped at the baseline and upgraded — is the test
    above; the order of the two comparisons is what separates the eras.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "skip")
    probe_id = "5ea50f00d001"
    probe_config = _probe_history(
        tmp_path,
        probe_id,
        "    op.create_table(\n"
        '        "probe_table",\n'
        '        sa.Column("id", sa.Uuid(), nullable=False),\n'
        '        sa.PrimaryKeyConstraint("id", name=op.f("pk_probe_table")),\n'
        "    )",
    )
    await reset_schema(url)

    # The probe revision ships together with its model change: the
    # probe-head models' ``create_all`` produces exactly the real models
    # plus this table. The model registers on the shared Base for this test
    # only — removed again below, so no other test's comparison sees it.
    from app.kernel.db.base import Base

    try:
        from sqlalchemy.orm import Mapped, mapped_column

        class Probe(Base):
            """The probe revision's table, as the probe-head models declare it."""

            __tablename__ = "probe_table"

            id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)

        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    lambda sync_connection: cast("Table", Probe.__table__).create(sync_connection)
                )
        finally:
            await engine.dispose()

        outcome = await prepare_database(url, backup=False, config=probe_config)

        assert outcome.from_revision is None
        assert outcome.bootstrapped is True
        # Stamped at head: the version row is the probe revision and the
        # upgrade afterwards had nothing to apply — a stamp at the baseline
        # would have replayed the probe onto an existing table and failed.
        assert await _version_row(url) == probe_id
        assert await _models_diff(url) == []  # no DDL happened: still the models'
    finally:
        Base.metadata.remove(Base.metadata.tables["probe_table"])
        await drop_every_table(url)


def test_scratch_database_name_is_derived_per_target() -> None:
    """The bootstrap's scratch name derives from the target database.

    Advisory locks are per-database, not cluster-wide: two bootstraps
    against different databases of one server do not serialise against
    each other, so a shared fixed scratch name would race its own
    drop/create. Same target → same name (a crashed run's leftover is
    found and pre-dropped again); different targets → different names;
    bounded under Postgres's 63-byte identifier limit.
    """
    one = "postgresql+asyncpg://narrare:narrare@localhost:5433/one"
    two = "postgresql+asyncpg://narrare:narrare@localhost:5433/two"
    name_for = migrate_module._scratch_database_name  # pyright: ignore[reportPrivateUsage]
    assert name_for(one) == name_for(one)
    assert name_for(one) != name_for(two)
    for target in (one, two):
        name = name_for(target)
        assert len(name.encode()) <= 63
        assert name.startswith("narrare_baseline_")


def test_sidecar_urls_keep_query_options_and_encoded_credentials() -> None:
    """The bootstrap's admin and scratch URLs survive rebuilds with ``make_url``.

    The old ``rsplit("/", 1)[0]`` string surgery worked only for the plain
    ``scheme://user:pass@host/db`` shape: a query option such as
    ``sslmode=require`` was dropped, and a server reachable only with it
    became unreachable for the scratch replay and its cleanup. The rebuild
    keeps the credentials (encoded form included) and the query, changing
    only the database name.
    """
    target = "postgresql+asyncpg://u:p%40x@h:5432/db?sslmode=require"
    sidecar = migrate_module._sidecar_url  # pyright: ignore[reportPrivateUsage]
    scratch_name = migrate_module._scratch_database_name(target)  # pyright: ignore[reportPrivateUsage]
    admin = make_url(sidecar(target, "postgres"))
    scratch = make_url(sidecar(target, scratch_name))
    assert admin.render_as_string(hide_password=False) == (
        "postgresql+asyncpg://u:p%40x@h:5432/postgres?sslmode=require"
    )
    assert scratch.render_as_string(hide_password=False) == (
        f"postgresql+asyncpg://u:p%40x@h:5432/{scratch_name}?sslmode=require"
    )


def test_percent_encoded_url_survives_the_config_parser_round_trip() -> None:
    """A percent in the URL (an encoded password) survives the ConfigParser.

    ``set_main_option`` is ConfigParser's: its interpolation reads ``%`` as
    the escape character, so the URL must be escaped on write — alembic
    unescapes on read. Unescaped, ``n%40rrare`` dies with a plain
    ``ValueError: invalid interpolation syntax`` the moment the option is
    set. The offline upgrade runs ``env.py`` without a database.
    """
    encoded = "postgresql+asyncpg://narrare:n%40rrare@localhost:5433/narrare_v2_migrations"
    config = alembic_config(encoded)
    command.upgrade(config, "head", sql=True)
    assert config.get_main_option("sqlalchemy.url") == encoded


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


async def test_first_boot_takes_no_dump_of_the_empty_schema(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh first boot — extensions, no tables — migrates with no dump.

    The dump protects prose (D5) and an empty schema has none: the product
    owner's 2026-10-31 decision takes no copy of nothing, which also keeps
    pg_dump out of the first boot's requirements.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_DIR", str(tmp_path))
    await drop_every_table(url)

    outcome = await prepare_database(url, backup=True)

    assert outcome.from_revision is None  # every revision was pending
    assert outcome.to_revision == head_revision()
    assert outcome.backup is None
    assert list(tmp_path.iterdir()) == []
    assert await _version_row(url) == head_revision()  # the replay ran regardless


async def test_pending_revision_writes_a_dump(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run with pending revisions takes the restorable copy first (D5)."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    # Premise shift (product owner, 2026-10-31): a dump requires pending
    # revisions AND tables — a replay onto an empty database takes none
    # (the test below). The pending-with-tables shape is the first upgrade:
    # the 0.2.0 snapshot loaded onto an empty database, models-built and
    # unversioned.
    await drop_every_table(url)
    await _load_snapshot(url, SNAPSHOT)

    outcome = await prepare_database(url, backup_dir=tmp_path)

    assert outcome.from_revision is None  # no history yet: the stamp was pending
    assert outcome.backup is not None
    assert outcome.backup.parent == tmp_path
    assert outcome.backup.read_bytes()[:5] == b"PGDMP"


async def test_up_to_date_database_writes_no_dump(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second run has nothing pending: no dump, no DDL, head to head (D5)."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    # The first run needs a dump to have something to not repeat: a
    # table-bearing pending database (the first-upgrade shape) — an empty
    # one takes no dump at all since the 2026-10-31 first-boot skip.
    await drop_every_table(url)
    await _load_snapshot(url, SNAPSHOT)
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
    await reset_schema(url)  # tables: since 2026-10-31 an empty database attempts no dump

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


async def test_empty_backup_command_is_a_named_refusal(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A NARRE_BACKUP_COMMAND that resolves to nothing is BackupFailed, not IndexError."""
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_COMMAND", "   ")
    await reset_schema(url)  # tables: since 2026-10-31 an empty database attempts no dump

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)

    assert isinstance(refused.value.__cause__, BackupFailed)
    assert "empty command" in str(refused.value.__cause__)
    assert list(tmp_path.iterdir()) == []  # nothing that looks like a dump was kept
    # Nothing migrated: the version table never came into existence.
    with pytest.raises(ProgrammingError) as missing:
        await _version_row(url)
    assert getattr(missing.value.__cause__, "sqlstate", None) == UNDEFINED_TABLE


async def test_failed_file_form_leaves_no_dump(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed pg_dump --file run leaves its zero-byte target behind — we do not.

    pg_dump opens the output file before it connects, so a failing run (here:
    an unresolvable host) exits leaving a zero-byte ``*.dump``. That file must
    not survive as a dump, and must not evict a restorable one from retention.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv(
        "NARRE_BACKUP_COMMAND",
        "pg_dump --format=custom --no-owner --file {file} "
        "--host nosuchhost.invalid --dbname narrare",
    )
    await reset_schema(url)  # tables: since 2026-10-31 an empty database attempts no dump

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)

    assert isinstance(refused.value.__cause__, BackupFailed)
    assert list(tmp_path.iterdir()) == []


async def test_fake_dump_file_is_refused_and_removed(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that exits 0 with an empty ``{file}`` is refused — and leaves nothing.

    ``touch {file}`` succeeds, creates a zero-byte dump, and writes nothing to
    stdout: the acceptance probe must refuse it, and the artifact must not
    survive as a dump (the same class of leftover a failed --file run leaves).
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_COMMAND", "touch {file}")
    await reset_schema(url)  # tables: since 2026-10-31 an empty database attempts no dump

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)

    assert isinstance(refused.value.__cause__, BackupFailed)
    assert list(tmp_path.iterdir()) == []


async def test_garbage_dump_file_is_refused_and_removed(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that exits 0 writing non-dump bytes into ``{file}`` is refused.

    ``pg_dump {url} --file {file}`` without ``--format=custom`` is the
    operator's plausible mistake: the run succeeds, the file is non-empty —
    and ``pg_restore`` cannot read a word of it. A non-empty ``{file}`` was
    the one artifact shape acceptance let through; the ``PGDMP`` magic is
    required on whichever file the run left, and nothing survives.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_COMMAND", "sh -c 'printf not-a-dump > {file}'")
    await reset_schema(url)  # tables: since 2026-10-31 an empty database attempts no dump

    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)

    assert isinstance(refused.value.__cause__, BackupFailed)
    assert list(tmp_path.iterdir()) == []  # the fake-good dump did not survive
    # Nothing migrated: the version table never came into existence.
    with pytest.raises(ProgrammingError) as missing:
        await _version_row(url)
    assert getattr(missing.value.__cause__, "sqlstate", None) == UNDEFINED_TABLE


async def test_stalled_dump_command_times_out(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dump that never finishes cannot block startup forever (NARRE_BACKUP_TIMEOUT).

    A pg_dump that stalls — or sits at a password prompt — must not hold the
    startup hostage: the subprocess is bounded by ``NARRE_BACKUP_TIMEOUT``
    (seconds, default 300), the expired run is ``BackupFailed``, and the
    refusal migrates nothing and leaves no artifact behind.
    """
    monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
    monkeypatch.setenv("NARRE_BACKUP_COMMAND", "sh -c 'sleep 30; exit 0'")
    monkeypatch.setenv("NARRE_BACKUP_TIMEOUT", "1")
    await reset_schema(url)  # tables: an empty database attempts no dump

    started = monotonic()
    with pytest.raises(MigrationRefused) as refused:
        await prepare_database(url, backup_dir=tmp_path)
    elapsed = monotonic() - started

    assert elapsed < 15  # the timeout, ~1s — not the command's 30
    assert isinstance(refused.value.__cause__, BackupFailed)
    assert "NARRE_BACKUP_TIMEOUT" in str(refused.value.__cause__)
    assert list(tmp_path.iterdir()) == []  # nothing that looks like a dump was kept
    # Nothing migrated: the version table never came into existence.
    with pytest.raises(ProgrammingError) as missing:
        await _version_row(url)
    assert getattr(missing.value.__cause__, "sqlstate", None) == UNDEFINED_TABLE


async def test_bad_backup_timeout_is_a_named_refusal(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A NARRE_BACKUP_TIMEOUT that is not a positive number is BackupFailed.

    The value is resolved before any work starts — no sink is opened, no
    artifact survives, nothing is migrated. The no-open pin is what bites
    on the order: with the timeout resolved after ``partial.open``, the
    sink descriptor leaked until garbage collection surfaced it as an
    unraisable warning — timing-dependent. Here it is an assertion.
    """
    opened: list[str] = []
    real_open = Path.open

    def _recording_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        opened.append(self.name)
        return cast("IO[bytes]", real_open(self, *args, **kwargs))

    monkeypatch.setattr(Path, "open", _recording_open)
    for value in ("not-a-number", "0", "-5"):
        monkeypatch.setenv("NARRE_MIGRATION_BACKUP", "pg_dump")
        monkeypatch.setenv("NARRE_BACKUP_TIMEOUT", value)
        await reset_schema(url)  # tables: an empty database attempts no dump

        with pytest.raises(MigrationRefused) as refused:
            await prepare_database(url, backup_dir=tmp_path)

        assert isinstance(refused.value.__cause__, BackupFailed)
        assert "NARRE_BACKUP_TIMEOUT" in str(refused.value.__cause__)
        assert opened == []  # the refusal happened before any sink was opened
        assert list(tmp_path.iterdir()) == []
        # Nothing migrated: the version table never came into existence.
        with pytest.raises(ProgrammingError) as missing:
            await _version_row(url)
        assert getattr(missing.value.__cause__, "sqlstate", None) == UNDEFINED_TABLE


async def test_sink_close_failure_is_a_named_refusal(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sink that fails at close time (ENOSPC, EIO) is BackupFailed, not raw OSError.

    The close flushes what ``subprocess.run`` streamed; a failure there has
    nothing to do with running the command, and must be named as the write
    that did not land.
    """
    real_open = Path.open

    class _CloseFails:
        """Delegates everything to the real handle; close() fails, as a full disk would."""

        def __init__(self, handle: IO[bytes]) -> None:
            self._handle = handle

        def __getattr__(self, name: str) -> Any:
            return getattr(self._handle, name)

        def close(self) -> None:
            self._handle.close()
            raise OSError(28, "No space left on device")

        def __enter__(self) -> _CloseFails:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

    def _open_with_broken_close(self: Path, *args: Any, **kwargs: Any) -> Any:
        handle = cast("IO[bytes]", real_open(self, *args, **kwargs))
        if self.name.endswith(".dump.partial"):
            return _CloseFails(handle)
        return handle

    monkeypatch.setattr(Path, "open", _open_with_broken_close)

    with pytest.raises(BackupFailed) as failed:
        await dump_database(url, tmp_path)

    assert "could not write" in str(failed.value)  # the write, not the command, is named
    assert list(tmp_path.iterdir()) == []  # the half-written sink did not survive


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
    await reset_schema(url)  # tables: since 2026-10-31 an empty database attempts no dump

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


async def test_retention_counts_only_this_database(url: str, tmp_path: Path) -> None:
    """Retention evicts only the current database's dumps, never another stack's.

    ``keep`` used to count every ``*.dump`` in the directory by mtime: two
    stacks sharing a backup directory evicted each other's copies. The dump
    filename's prefix carries the database — retention filters to it before
    applying ``keep`` (CodeRabbit round 1, 2026-11-01).
    """
    database = url.rsplit("/", 1)[-1]
    ours = [tmp_path / f"{database}-20260101T0000000{i}.dump" for i in range(3)]
    theirs = [tmp_path / f"other_stack-20260101T0000000{i}.dump" for i in range(2)]
    for path in [*ours, *theirs]:
        path.write_bytes(b"an older dump")
    for position, path in enumerate([*ours, *theirs]):
        utime(path, (1_000_000_000 + position, 1_000_000_000 + position))

    fresh = await dump_database(url, tmp_path, keep=3)

    kept = {path.name for path in tmp_path.iterdir()}
    assert kept == {fresh.name, ours[1].name, ours[2].name, theirs[0].name, theirs[1].name}
    assert ours[0].name not in kept  # our oldest was the one eviction
    for path in [*theirs, ours[1], ours[2]]:
        assert path.stat().st_mtime < fresh.stat().st_mtime  # untouched by this run


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
