"""Throwaway databases for tests that run against a real Postgres.

Each run gets its own database: the name carries the worktree and a per-run
token minted once per process, and the database itself carries a marker on
the server — host, boot id, pid — that a sweep requires before it drops
anything. A run that died mid-suite leaves its database behind; the next
run's sweep reclaims it, but only when the marker names this host and either
names another boot or a pid that is no longer alive. A name without a marker,
or from another host, is never ours to drop. One shared name would carry one
suite's rows into the next and let two concurrent runs truncate each other's
tables mid-test (#611).

The server itself is the compose default unless the environment says
otherwise: two checkouts share one machine, and ``NARRE_TEST_DATABASE_URL``
is how the second one aims its suites — and its E2E stacks — at its own
Postgres instead of waiting for the port's first holder. The name a run
mints on that server is still its own; the env var chooses the door, never
the room behind it.
"""

import asyncio
import re
import sys
from contextlib import suppress
from hashlib import blake2s
from os import environ, getpid, kill
from pathlib import Path
from secrets import token_hex
from socket import gethostname
from uuid import UUID  # noqa: TC003

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

_ATTACH_URL = environ.get("NARRE_E2E_ATTACH", "").strip().rstrip("/")

# Attached to a running instance, exactly one database exists — the instance's
# own — and that is what every test-database name resolves to. The name is
# never recorded, so no session finish and no sweep can drop its data.
if _ATTACH_URL and not environ.get("NARRE_DATABASE_URL"):
    raise RuntimeError(
        "NARRE_E2E_ATTACH needs NARRE_DATABASE_URL: the attached instance's"
        " database is where the preconditions are seeded"
    )

_ATTACH = make_url(environ["NARRE_DATABASE_URL"]) if _ATTACH_URL else None

# The one SERVER definition: the compose address unless the environment
# re-aims it (``NARRE_TEST_DATABASE_URL``) — the door a second checkout on
# one machine uses to run against its own Postgres. Attached runs never
# read it: their database is the instance's own, wherever it lives.
SERVER = environ.get(
    "NARRE_TEST_DATABASE_URL", "postgresql+asyncpg://narrare:narrare@localhost:5433"
)


def admin_url(database: str) -> str:
    """A connection to `database` on the server the run may administer.

    Attached to a running instance, that is the instance's server: creating and
    dropping databases is how the default path prepares too, and a hardcoded
    localhost here sent every admin step to the wrong machine.
    """
    if _ATTACH is not None:
        return _ATTACH.set(database=database).render_as_string(hide_password=False)
    return f"{SERVER}/{database}"


REPO_ROOT = Path(__file__).resolve().parents[3]

# The per-run token: eight hex characters minted once per process. The same
# process, the same prefix — the same name, always; two runs differ even when
# their pids would be reused across the runs.
#
# The ``or`` is reload safety: ``importlib.reload`` re-executes the module in
# this same dict (the SERVER tests do), and a token re-minted mid-run hands
# every later ``test_database`` caller a name nobody ensured — or a sweep
# inside a running loop. Carried, not re-minted; the caches below agree.
_RUN_TOKEN: str = globals().get("_RUN_TOKEN") or token_hex(4)
# ``test_database``'s suffix — which the sweep matches on: the worktree token
# plus the run token, 16 lowercase hex characters in total.
_RUN_SUFFIX = re.compile(r"[0-9a-f]{16}")

# The marker ``_ensure`` writes and the sweep reads. A drop needs it to name
# this host — a database owned by a run on another box, even against a shared
# server, is never this run's to drop (which leaves a pid-namespace run safe).
_OWNER = re.compile(r"narrare-run host=(\S*) boot=(\S*) pid=(\d+)")

_HOSTNAME = gethostname()


def _boot_id() -> str:
    """This boot's id, or an empty string outside Linux."""
    with suppress(OSError):
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return ""


_BOOT = _boot_id()

# Carried across a reload (see ``_RUN_TOKEN``): the run's sweeps and names
# are this process's, not this import's.
_SWEPT: set[str] = globals().get("_SWEPT") or set()
_NAMES: dict[str, str] = globals().get("_NAMES") or {}
_RUN_DATABASES: list[str] = globals().get("_RUN_DATABASES") or []


def url_for(database: str) -> str:
    if _ATTACH is not None:
        # Built from the URL, so a query option (`?ssl=require`) survives.
        return _ATTACH.set(database=database).render_as_string(hide_password=False)
    return f"{SERVER}/{database}"


def _alive(pid: int) -> bool:
    """Whether a pid on this host's current boot may still be running.

    ``PermissionError`` is an alive process owned by another user,
    ``ProcessLookupError`` a dead one; a pid this platform cannot signal at
    all does not read as alive.
    """
    try:
        kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OverflowError, ValueError, OSError:
        return False
    return True


def test_database(prefix: str = "narrare_v2_test") -> str:
    """This run's database name: ``prefix_`` + worktree token + run token.

    Same process, same prefix — same name, always; a second pytest run, in a
    second worktree or a second process, names a database of its own (#611).
    The run token is minted once per process, so a name never carries the pid:
    a reused pid can never make a run adopt another run's rows. The first
    call under a prefix per process also runs ``sweep``, so a run crashed
    mid-test does not leave its database behind on the server.

    Names are capped at PostgreSQL's 63-byte identifier limit; a longer one
    raises ``ValueError`` rather than truncating at the server into somebody
    else's name.

    ``ensure_database`` is the caller's next step: nothing is created here.

    Attached to a running instance (``NARRE_E2E_ATTACH``), the answer is that
    instance's database: there is exactly one, it holds the artefact's state,
    and a run that only drives it neither sweeps nor drops it.
    """
    if _ATTACH is not None:
        return _ATTACH.database or ""
    if prefix in _NAMES:
        return _NAMES[prefix]
    if prefix not in _SWEPT:
        sweep(prefix)
        _SWEPT.add(prefix)
    name = f"{prefix}_{blake2s(str(REPO_ROOT).encode(), digest_size=4).hexdigest()}{_RUN_TOKEN}"
    if len(name.encode("utf-8")) > 63:
        raise ValueError(
            f"test database name for prefix {prefix!r} is {len(name.encode('utf-8'))} bytes; "
            f"PostgreSQL limits identifiers to 63 — shorten the prefix"
        )
    _NAMES[prefix] = name
    _RUN_DATABASES.append(name)
    return name


def sweep(prefix: str = "narrare_v2_test") -> None:
    """Drop the prefix's per-run databases whose owner is gone, proven gone.

    A database belongs to this prefix only when its name starts with
    ``prefix_`` followed by 16 lowercase hex characters — the shape and only
    the shape ``test_database`` produces. And a drop needs the owner marker on the
    database itself: it must parse as ``narrare-run host=… boot=… pid=…``, name
    this hostname, and name another boot (crashed machine's leftovers) or a
    pid that is no longer alive — ``PermissionError`` counts as alive. A name
    without a marker (a hand-made database in the namespace), from another
    host, or whose marker does not parse, is skipped: dropping another test's
    server or another box's run would be this run reaching where it has no
    right (finding 1 in the #611 review).
    """
    asyncio.run(_sweep(prefix))


async def _sweep(prefix: str) -> None:
    engine = create_async_engine(admin_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT datname, shobj_description(oid, 'pg_database')"
                    " FROM pg_database WHERE datname LIKE :pattern"
                ),
                {"pattern": f"{prefix}\\_%"},
            )
            for name, marker in rows.fetchall():
                if not str(name).startswith(f"{prefix}_"):
                    continue  # the prefix's own underscores matched as wildcards
                suffix = str(name)[len(prefix) + 1 :]
                if _RUN_SUFFIX.fullmatch(suffix) is None:
                    continue
                owner = _OWNER.fullmatch(str(marker)) if marker is not None else None
                if owner is None:
                    continue  # no marker to own it by: not this run's to drop
                host, boot, pid = owner.group(1), owner.group(2), int(owner.group(3))
                if host != _HOSTNAME:
                    continue  # another machine's run, against a shared server
                if boot == _BOOT and _alive(pid):
                    continue  # live on this boot
                await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


def drop_database(name: str) -> None:
    """Drop one database, terminating connections still using it."""
    asyncio.run(_drop(name))


async def _drop(name: str) -> None:
    engine = create_async_engine(admin_url("postgres"), isolation_level="AUTOCOMMIT")
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
    engine = create_async_engine(admin_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
            )
            if not exists:
                # A parallel pytest worker may create it between the check and here.
                with suppress(Exception):
                    await connection.execute(text(f'CREATE DATABASE "{database}"'))
            # Only a name this process minted is marked. The comment sits
            # outside the CREATE's own suppression: a database created but
            # left unmarked would survive every sweep after its owner is gone.
            if database in _NAMES.values():
                await connection.execute(
                    text(
                        f'COMMENT ON DATABASE "{database}" IS'
                        f" 'narrare-run host={_HOSTNAME} boot={_BOOT} pid={getpid()}'"
                    )
                )
    finally:
        await engine.dispose()


def ensure_database(database: str) -> None:
    asyncio.run(_ensure(database))
