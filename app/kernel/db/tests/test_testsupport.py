"""The per-run test database: one name per worktree and per process.

Real Postgres, no mocks. The name is formed, the databases are created and
swept, and the ``pg_database`` truth is queried on the server the suites run
against — #611's whole substance is two pytest runs touching one database, so
the proof has to be a live server, not a stub. The tests are sync: the
helpers own their own loop and a test simply drives them.
"""

import os
import subprocess
from asyncio import run
from hashlib import blake2s
from pathlib import Path

from app.kernel.db import testsupport
from app.kernel.db.testsupport import SERVER

LEGACY = "narrare_v2_test"

# The tests restate the helper from this file's own position: this file sits
# four levels under the repository root. ``_tree()`` hashes it, and the worktree
# test pins ``testsupport.REPO_ROOT`` to it — a wrong ``parents[...]`` fails
# there instead of quietly hashing a different root.
ROOT = Path(__file__).resolve().parents[4]


def _tree() -> str:
    """The worktree token, restated here independently of the helper."""
    return blake2s(str(ROOT).encode(), digest_size=4).hexdigest()


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


def test_one_name_per_worktree_and_process() -> None:
    """The name carries both tokens and two calls in one process agree on it."""
    name = testsupport.test_database()

    assert testsupport.REPO_ROOT == ROOT
    assert name != LEGACY
    assert name == f"{LEGACY}_{_tree()}{os.getpid():08x}"
    assert testsupport.test_database() == name


def test_two_processes_name_two_databases() -> None:
    """Only the pid differs — the other run gets its own database."""
    assert testsupport.test_database(pid=0x11111111) != testsupport.test_database(pid=0x22222222)


def test_the_sweep_drops_a_dead_process_database() -> None:
    """A database left behind by a process that is gone is reclaimed."""
    name = f"{LEGACY}_{_tree()}{0x7FFFFFF0:08x}"
    testsupport.ensure_database(name)
    try:
        assert run(_exists(name)) is True

        testsupport.sweep()

        assert _gone(name) is True
    finally:
        testsupport.drop_database(name)


def test_the_sweep_leaves_a_live_process_and_the_legacy_alone() -> None:
    """A live owner's database survives the sweep and the legacy name is untouched.

    The live owner is a real child process, not this one: a database named
    for this pid would *be* the run's working database, and cleaning it up
    would take the suite's own tables away mid-run.
    """
    child = subprocess.Popen(["/bin/sleep", "60"])
    try:
        ours = f"{LEGACY}_{_tree()}{child.pid:08x}"
        testsupport.ensure_database(ours)
        had_legacy = run(_exists(LEGACY))

        testsupport.sweep()

        assert run(_exists(ours)) is True
        assert run(_exists(LEGACY)) is had_legacy
    finally:
        child.kill()
        child.wait()
        testsupport.drop_database(f"{LEGACY}_{_tree()}{child.pid:08x}")
