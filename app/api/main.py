"""The FastAPI app: startup validation and every capability router, found by
convention. Adding a capability touches only its folder (spec §12.1): every
``app/capabilities/<name>/router.py`` is mounted, in alphabetical order.
"""

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from importlib import import_module
from logging import INFO, basicConfig, getLogger
from pathlib import Path

from fastapi import FastAPI

from app.generated.capabilities import CAPABILITIES as REGISTERED
from app.kernel.configuration import validate_configuration

CAPABILITIES = Path(__file__).resolve().parent.parent / "capabilities"

# Uvicorn configures its own loggers, not the root one, so the kernel's startup
# line about the configured providers would be dropped as an INFO record without
# this. One handler, installed once, for the app's own logger.
basicConfig(level=INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    validate_configuration()
    yield


app = FastAPI(title="Narrare", version="2.0.0", lifespan=lifespan)

for folder in sorted(path for path in CAPABILITIES.iterdir() if (path / "router.py").exists()):
    app.include_router(import_module(f"app.capabilities.{folder.name}.router").router)

# The facts files and the routers must name the same capabilities: a folder with
# a router but no capability.yaml is a half-built capability, and it stops here
# instead of shipping silently. `just generate` writes the registry back.
mounted = {folder.name for folder in CAPABILITIES.iterdir() if (folder / "router.py").exists()}
registered = {capability.id for capability in REGISTERED}
if mounted != registered:
    raise RuntimeError(
        f"capability folders and capability.yaml disagree on {sorted(mounted ^ registered)};"
        " run `just generate` and commit the result"
    )
getLogger("narrare").info(
    "capabilities %s",
    ", ".join(
        f"{capability.id}({', '.join(capability.needs)})" if capability.needs else capability.id
        for capability in REGISTERED
    ),
)
