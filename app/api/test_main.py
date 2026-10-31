"""Router discovery: a capability folder with a router.py is mounted, by convention.

The reviewer's §12.1 check: adding a capability must touch only its folder. The
probe in the fix round proves it live; this test keeps it true afterwards.

The lifespan tests live here too: startup is where the schema, the
configuration check and the jobs lane meet, so their order is pinned next to
the wiring it governs.
"""

from asyncio import run
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api import main
from app.kernel.db.migrate import head_revision
from app.kernel.db.testsupport import url_for

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from fastapi.testclient import TestClient

CAPABILITIES = Path(main.__file__).parent.parent / "capabilities"

DATABASE = "narrare_v2_test"


async def _version_rows(database: str) -> list[str]:
    """The ``alembic_version`` rows — reading the table proves it exists."""
    engine = create_async_engine(database)
    try:
        async with engine.connect() as connection:
            # The existence probe first, then the row it guards.
            await connection.execute(text("SELECT 1 FROM alembic_version"))
            return [
                str(row[0])
                for row in (
                    await connection.execute(text("SELECT version_num FROM alembic_version"))
                ).fetchall()
            ]
    finally:
        await engine.dispose()


def test_startup_migrates_before_the_worker(client: TestClient) -> None:
    """Startup brings a models-created database under the history's control.

    The ``client`` fixture hands the lifespan a database with tables but no
    ``alembic_version`` — the shape an installation built from the models
    has. After startup the version row is back and names head, and the jobs
    worker is up: the migration ran before the worker, not after it.
    """
    assert run(_version_rows(url_for(DATABASE))) == [head_revision()]
    # The worker the lifespan starts after the migration: up, not done.
    task = main.app.state.jobs_task
    assert task is not None and not task.done()


def test_startup_refuses_a_drifted_database(
    client_factory: Callable[[], AbstractContextManager[TestClient]],
) -> None:
    """A database whose schema no longer matches the models is refused by name.

    The drift is a dropped column on chapters; the refusal must say what
    differs — that is the message an operator can act on (design D4) — and
    the app must not come up on top of it. The history row goes too: a
    *versioned* database's drift belongs to the upgrade path, which fails on
    its own; the bootstrap branch is where startup can name the difference.
    """
    url = url_for(DATABASE)

    async def drift() -> None:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
                await connection.execute(text("ALTER TABLE chapters DROP COLUMN title"))
        finally:
            await engine.dispose()

    run(drift())
    try:
        with (
            pytest.raises(RuntimeError) as refused,
            client_factory(),
        ):
            pass
    finally:
        # pytest-randomly may run any suite next: the shared database goes
        # back to the state the session fixture left — tables from the
        # models, history at head — even if the assertions above fail.
        from app.kernel.db.init import init_schema, reset_schema

        run(reset_schema(url))
        run(init_schema(url))
    message = str(refused.value)
    assert "chapters" in message and "title" in message


async def test_the_lifespan_starts_and_stops_the_jobs_lane() -> None:
    # The lane is part of startup: the lifespan starts the worker (whose
    # stuck-row reset writes to jobs) with whatever handlers the capability
    # convention found, and stops it without abandoning a job mid-flight. The
    # E2E stacks drive the same startup for real; this keeps the wiring honest
    # at unit speed.
    async with main.lifespan(main.app):
        task = main.app.state.jobs_task
        assert task is not None and not task.done()
    assert task.done()


def test_every_capability_with_a_router_is_mounted() -> None:
    # FastAPI mounts lazily: the built OpenAPI document is the flat route truth.
    mounted = set(main.app.openapi()["paths"])
    for folder in sorted(CAPABILITIES.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        if not (folder / "router.py").exists():
            continue
        assert any(path.startswith(f"/api/{folder.name}") for path in mounted), (
            f"{folder.name} has a router.py but no mounted route"
        )


def test_the_generated_registry_names_exactly_the_mounted_capabilities() -> None:
    # The facts files and the routers are two hands writing one truth; the
    # startup cross-check in main.py refuses to boot on a disagreement, and
    # this test keeps that disagreement from ever reaching a boot.
    from app.generated import capabilities as generated

    mounted = {
        folder.name
        for folder in CAPABILITIES.iterdir()
        if folder.is_dir() and (folder / "router.py").exists()
    }
    assert {capability.id for capability in generated.CAPABILITIES} == mounted, (
        "capability folders and capability.yaml disagree: run `just generate`"
    )
