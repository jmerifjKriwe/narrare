"""The FastAPI app: startup validation and every capability router, found by
convention. Adding a capability touches only its folder (spec §12.1): every
``app/capabilities/<name>/router.py`` is mounted, in alphabetical order.

One process serves the product. ``/api`` is the backend; when a build exists,
the shell and its hashed assets answer everything else. Leaner than a second
web server in production, and the reason the catch-all is guarded: an unknown
``/api`` path must stay JSON, and a missing bundle must stay a 404 instead of
turning into HTML the browser parses as JavaScript.
"""

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from importlib import import_module
from logging import INFO, basicConfig, getLogger
from os import environ
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.generated.capabilities import CAPABILITIES as REGISTERED
from app.kernel.configuration import validate_configuration
from app.kernel.jobs.runtime import start_worker, stop_worker

if TYPE_CHECKING:
    from app.kernel.jobs.worker import JobHandler

CAPABILITIES = Path(__file__).resolve().parent.parent / "capabilities"
DEFAULT_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

# Uvicorn configures its own loggers, not the root one, so the kernel's startup
# line about the configured providers would be dropped as an INFO record without
# this. One handler, installed once, for the app's own logger.
basicConfig(level=INFO)


def _job_handlers() -> dict[str, JobHandler]:
    """Every capability's background handlers, found the way routers are.

    A capability that wants the lane writes ``jobs.py`` exporting ``handlers``;
    nothing else changes (spec §12.1). Later folders win a duplicate kind,
    which is the same last-word rule a dict update always had — and a
    duplicate kind is a capability bug the first claim surfaces anyway.
    """
    handlers: dict[str, JobHandler] = {}
    for folder in sorted(CAPABILITIES.iterdir()):
        if not (folder / "jobs.py").is_file():
            continue
        handlers.update(import_module(f"app.capabilities.{folder.name}.jobs").handlers)
    return handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    validate_configuration()
    await start_worker(app, _job_handlers())
    try:
        yield
    finally:
        await stop_worker(app)


def _serve_shell(app: FastAPI, dist: Path) -> None:
    """Mount the built app: immutable assets, an uncached shell, nothing else."""
    root = dist.resolve()
    assets = root / "assets"

    @app.get("/assets/{path:path}", include_in_schema=False)
    async def asset(path: str) -> FileResponse:
        file = (assets / path).resolve()
        if not file.is_relative_to(assets) or not file.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(file, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/{full_path:path}", include_in_schema=False)
    async def shell(full_path: str) -> FileResponse:
        # Not a route of its own: the API keeps answering, JSON included.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        # A path with a suffix names a file. Serving the shell instead would
        # report a missing bundle as a 200 page and turn it into a syntax error.
        if Path(full_path).suffix:
            raise HTTPException(status_code=404)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})


def create_app(dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Narrare", version="2.0.0", lifespan=lifespan)

    for folder in sorted(path for path in CAPABILITIES.iterdir() if (path / "router.py").exists()):
        app.include_router(import_module(f"app.capabilities.{folder.name}.router").router)

    shell = dist if dist is not None else Path(environ.get("NARRE_WEB_DIST", str(DEFAULT_DIST)))
    if (shell / "index.html").is_file():
        _serve_shell(app, shell)
    return app


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

app = create_app()
