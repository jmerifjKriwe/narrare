"""Router discovery: a capability folder with a router.py is mounted, by convention.

The reviewer's §12.1 check: adding a capability must touch only its folder. The
probe in the fix round proves it live; this test keeps it true afterwards.
"""

from pathlib import Path

from app.api import main

CAPABILITIES = Path(main.__file__).parent.parent / "capabilities"


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
