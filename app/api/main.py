"""The FastAPI app: startup validation and every capability router, found by
convention. Adding a capability touches only its folder (spec §12.1): every
``app/capabilities/<name>/router.py`` is mounted, in alphabetical order.
"""

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path

from fastapi import FastAPI

from app.kernel.embeddings import validate_configuration

CAPABILITIES = Path(__file__).resolve().parent.parent / "capabilities"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    validate_configuration()
    yield


app = FastAPI(title="Narrare", version="2.0.0", lifespan=lifespan)

for folder in sorted(path for path in CAPABILITIES.iterdir() if (path / "router.py").exists()):
    app.include_router(import_module(f"app.capabilities.{folder.name}.router").router)
