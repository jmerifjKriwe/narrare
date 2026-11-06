"""The per-run test database: one name per worktree and per run token.

Real Postgres, no mocks. The name is formed, the databases are created,
marked and swept, and the ``pg_database`` truth — including the owner marker —
is queried on the server the suites run against — #611's whole substance is
two pytest runs touching one database, so the proof has to be a live server,
not a stub. The tests are sync: the helpers own their own loop and a test
simply drives them.
"""

import re
import socket
import subprocess
from asyncio import run
from hashlib import blake2s
from os import getpid
from pathlib import Path
from secrets import token_hex
from shutil import which

import pytest

from app.kernel.db import testsupport
from app.kernel.db.testsupport import SERVER

LEGACY = "narrare_v2_test"

# The tests restate the helper from this file's own position: this file sits
# four levels under the repository root. ``_tree()`` hashes it, and the worktree
# test pins ``testsupport.REPO_ROOT`` to it — a wrong ``parents[...]`` fails
# there instead of quietly hashing a different root.
ROOT = Path(__file__).resolve().parents[4]

# The sweep's drop precondition, stated here independently of the helper: the
# marker an owner writes onto its database.
_OWNER = re.compile(r"narrare-run host=(\S*) boot=(\S*) pid=(\d+)")


def _tree() -> str:
    """The worktree token, restated here independently of the helper."""
    return blake2s(str(ROOT).encode(), digest_size=4).hexdigest()


def _boot_id() -> str:
    """This boot's id, read where the helper reads it."""
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


async def _exists(name: str) -> bool:
    """Whether the server currently knows the database by that name."""
    engine = testsupport.create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            found = await connection.execute(
                testsupport.text("SELECT datname FROM pg_database WHERE datname = :name"),
                {"name": name},
            )
            return found.fetchone() is not None
    finally:
        await engine.dispose()


def _gone(name: str) -> bool:
    return run(_exists(name)) is False


async def _marker(name: str) -> str | None:
    """The database's owner comment, read the way the sweep reads it."""
    engine = testsupport.create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            row = await connection.execute(
                testsupport.text(
                    "SELECT shobj_description(oid, 'pg_database')"
                    " FROM pg_database WHERE datname = :name"
                ),
                {"name": name},
            )
            return row.scalar()
    finally:
        await engine.dispose()


async def _mark(name: str, *, host: str, boot: str, pid: int) -> None:
    """Write the owner marker a run writes onto its own database."""
    engine = testsupport.create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(
                testsupport.text(
                    f'COMMENT ON DATABASE "{name}" IS'
                    f" 'narrare-run host={host} boot={boot} pid={pid}'"
                )
            )
    finally:
        await engine.dispose()


def test_one_name_per_worktree_and_run() -> None:
    """The name carries the worktree token and a 16-hex run token, and repeats."""
    name = testsupport.test_database()

    assert testsupport.REPO_ROOT == ROOT
    assert name != LEGACY
    suffix = name[len(LEGACY) + 1 :]
    assert re.fullmatch(r"[0-9a-f]{16}", suffix) is not None  # the shape the sweep matches
    assert suffix[:8] == _tree()  # the worktree token first
    assert testsupport.test_database() == name


def test_two_prefixes_name_two_databases() -> None:
    """A second prefix is a second database, not this run's again."""
    first = testsupport.test_database(prefix="narrare_v2_alpha")
    second = testsupport.test_database(prefix="narrare_v2_beta")

    assert first != second
    assert first.startswith("narrare_v2_alpha_")
    assert second.startswith("narrare_v2_beta_")


def test_ensure_database_marks_this_run_exactly_and_a_sweep_keeps_it() -> None:
    """A run's own database carries the marker exactly — host, boot, pid.

    No test reading the marker would leave the ``COMMENT ON DATABASE`` block
    free to rot: deleting it passes every other test while no dead run is
    ever reclaimed, so the comment is read from the server and compared to
    what this process would have written. The sweep keeps the same database:
    it is this run's and its owner is alive.
    """
    name = testsupport.test_database(prefix="narrare_v2_alpha")
    testsupport.ensure_database(name)
    try:
        assert (
            run(_marker(name))
            == f"narrare-run host={socket.gethostname()} boot={_boot_id()} pid={getpid()}"
        )

        testsupport.sweep("narrare_v2_alpha")

        assert run(_exists(name)) is True
    finally:
        testsupport.drop_database(name)


def test_the_sweep_keeps_a_live_owner_on_this_host_and_boot() -> None:
    """A concurrent run's database — this host, this boot, a live pid — survives.

    Without this case ``_alive`` could return False unconditionally and still
    pass every other test while dropping another run's database mid-suite:
    the dead-owner case cannot tell a live pid from a dead one.
    """
    child = subprocess.Popen(["/bin/sleep", "60"])
    live = f"{LEGACY}_{_tree()}aaaa0003"
    testsupport.ensure_database(live)
    try:
        run(_mark(live, host=socket.gethostname(), boot=_boot_id(), pid=child.pid))
        assert run(_exists(live)) is True

        testsupport.sweep()

        assert run(_exists(live)) is True
    finally:
        child.kill()
        child.wait()
        testsupport.drop_database(live)


def test_a_second_process_names_a_database_of_its_own() -> None:
    """The run token is minted per process: another process, another name.

    The name never carries a pid, so a fresh process is the only way to show
    two runs — two names — from one worktree.
    """
    mine = testsupport.test_database()
    uv = which("uv")
    assert uv is not None  # the test needs this worktree's uv
    theirs = subprocess.run(  # noqa: S603  fixed argv, this worktree's uv, no shell
        [
            uv,
            "run",
            "python",
            "-c",
            "from app.kernel.db.testsupport import test_database; print(test_database())",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )

    printed = theirs.stdout.strip().splitlines()[-1]
    assert printed != mine
    assert re.fullmatch(r"[0-9a-f]{16}", printed[len(LEGACY) + 1 :]) is not None


def test_a_name_past_the_63_byte_limit_is_refused() -> None:
    """PostgreSQL limits identifiers to 63 bytes; a longer name can never exist."""
    with pytest.raises(ValueError):
        testsupport.test_database("x" * 50)


def test_the_sweep_drops_a_dead_owners_database_and_keeps_another_hosts() -> None:
    """A marked database whose owner died on this boot is litter; another host's stays.

    Both databases are marked the way a run marks its own. The dead owner is a
    real child process — spawned, killed and reaped, so the pid is genuinely
    gone before the marker is written. The other host's marker could belong to
    a same-boot twin pid on a different server: this run must never drop it.
    """
    dead = subprocess.Popen(["/bin/sleep", "60"])
    dead.kill()
    dead.wait()
    this_host = socket.gethostname()
    boot = _boot_id()
    litter = f"{LEGACY}_{_tree()}aaaa0000"
    theirs = f"{LEGACY}_{_tree()}aabb0001"
    testsupport.ensure_database(litter)
    testsupport.ensure_database(theirs)
    try:
        run(_mark(litter, host=this_host, boot=boot, pid=dead.pid))
        run(_mark(theirs, host="other-host.example", boot=boot, pid=dead.pid))
        assert run(_exists(litter)) is True
        assert run(_exists(theirs)) is True

        testsupport.sweep()

        assert _gone(litter) is True
        assert run(_exists(theirs)) is True
    finally:
        testsupport.drop_database(litter)
        testsupport.drop_database(theirs)


def test_the_sweep_leaves_a_shape_matching_database_without_a_marker_alone() -> None:
    """A hand-made database in the namespace is not this run's to drop."""
    handmade = f"{LEGACY}_{_tree()}aaaa0002"
    testsupport.ensure_database(handmade)
    try:
        testsupport.sweep()

        assert run(_exists(handmade)) is True
    finally:
        testsupport.drop_database(handmade)


def test_the_sweep_leaves_the_legacy_name_and_an_unshaped_probe_alone() -> None:
    """The shape check — not a marker's absence — is what spares unshaped names.

    The shared legacy name is only read, never created or dropped here:
    creating it raced another run of this very test (A creates, B sees it
    present, A drops, B asserts). A private probe is marked with a dead
    owner yet does not carry the 16-hex shape, so the sweep that just dropped
    shaped litter must still leave it: if the shape check were gone, the
    marker alone would hand it over.
    """
    had_legacy = run(_exists(LEGACY))
    dead = subprocess.Popen(["/bin/sleep", "60"])
    dead.kill()
    dead.wait()
    probe = f"{LEGACY}_probe_{token_hex(4)}"
    testsupport.ensure_database(probe)
    try:
        run(_mark(probe, host=socket.gethostname(), boot=_boot_id(), pid=dead.pid))
        assert run(_exists(probe)) is True

        testsupport.sweep()

        if had_legacy:
            assert run(_exists(LEGACY)) is True
        assert run(_exists(probe)) is True
    finally:
        testsupport.drop_database(probe)
