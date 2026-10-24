"""Router discovery: a capability folder with a router.py is mounted, by convention.

The reviewer's §12.1 check: adding a capability must touch only its folder. The
probe in the fix round proves it live; this test keeps it true afterwards.
"""

from pathlib import Path

from app.api import main

CAPABILITIES = Path(main.__file__).parent.parent / "capabilities"


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
