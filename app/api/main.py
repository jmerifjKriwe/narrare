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
from os.path import isfile, realpath, sep
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.generated.capabilities import CAPABILITIES as REGISTERED
from app.kernel.configuration import validate_configuration
from app.kernel.jobs.router import router as jobs_router
from app.kernel.jobs.runtime import start_worker, stop_worker
from app.kernel.version import __version__

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
    nothing else changes (spec §12.1). A kind two capabilities register is an
    assembly bug: the later folder still takes the dict's last word, but the
    merge says so at startup — a warning naming both sources, not a silent
    overwrite. A hard exit guards generated output elsewhere; this is a merge
    of live modules, and one duplicate kind does not outweigh every job.
    """
    logger = getLogger("narrare")
    handlers: dict[str, JobHandler] = {}
    sources: dict[str, str] = {}
    for folder in sorted(CAPABILITIES.iterdir()):
        if not (folder / "jobs.py").is_file():
            continue
        found = import_module(f"app.capabilities.{folder.name}.jobs").handlers
        for kind, handler in found.items():
            if kind in handlers:
                logger.warning(
                    "duplicate job kind %r: %s takes %s's handler",
                    kind,
                    folder.name,
                    sources[kind],
                )
            handlers[kind] = handler
            sources[kind] = folder.name
    return handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Validate configuration and run the jobs worker for the app's lifetime.

    Startup validation, handler discovery, and worker startup errors propagate;
    after a successful startup, exiting the context stops the worker.
    """
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
    inside_assets = f"{assets}{sep}"

    @app.get("/assets/{path:path}", include_in_schema=False)
    async def asset(path: str) -> FileResponse:
        # The request path arrives from the client, so it is attacker-controlled.
        # Resolve it first (symlinks included), then require the result to stay
        # inside assets/. realpath plus a prefix check, not resolve() plus
        # is_relative_to(): the same test in the shape static analysis can
        # verify, so a later regression reaches a reviewer as a finding
        # instead of staying silent.
        file = realpath(assets / path)
        if not file.startswith(inside_assets) or not isfile(file):
            raise HTTPException(status_code=404)
        return FileResponse(file, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/THIRD-PARTY-NOTICES.txt", include_in_schema=False)
    async def notices() -> FileResponse:
        # The bundle inlines third-party code whose license comments the
        # minifier strips; this file is where those licenses reach the
        # recipient. Uncached like the shell: it changes with every build.
        file = root / "THIRD-PARTY-NOTICES.txt"
        if not file.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(file, headers={"Cache-Control": "no-store"})

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
    """Build the API with discovered capability routers and the shared jobs route.

    ``dist`` selects the web build; otherwise use NARRE_WEB_DIST or DEFAULT_DIST.
    Mount the web shell only when that directory contains index.html.
    """
    app = FastAPI(title="Narrare", version=__version__, lifespan=lifespan)

    for folder in sorted(path for path in CAPABILITIES.iterdir() if (path / "router.py").exists()):
        app.include_router(import_module(f"app.capabilities.{folder.name}.router").router)

    # Kernel machinery beside the capability routers: the jobs lane's one read
    # route, which every capability's UI shares (spec §12.1 keeps capability
    # folders self-contained; this route belongs to no capability).
    app.include_router(jobs_router)

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
