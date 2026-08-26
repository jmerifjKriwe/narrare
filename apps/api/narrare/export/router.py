"""FastAPI routes for manuscript export (RULE-06: thin router).

Every handler delegates immediately to :class:`ExportServiceImpl`. There is no
business logic, no try/except, and no SQLAlchemy in this file — the
architecture checker (``router_queries``) mechanically enforces that. Domain
errors (:class:`ExportError` subclasses) are mapped to HTTP by the
:class:`ExportError` exception handler registered in
:mod:`narrare._app.main` (404 not-found, 410 expired/gone, 503 format-
unavailable) — mirroring how the global ``NarrareError`` handler covers the
other domains.

Routes
------
- ``GET  /api/v1/export/formats``                → ``list_formats``
- ``POST /api/v1/export``                        → ``export`` (201)
- ``GET  /api/v1/export/jobs/{job_id}``          → ``get_job``
- ``GET  /api/v1/export/jobs/{job_id}/artifact`` → ``consume_artifact`` (proxied
  ``FileResponse`` stream with ``Content-Disposition: attachment``, NOT a 302)

The artifact endpoint proxies the file (200 + attachment) and registers a
``BackgroundTask`` to unlink the temp file once the stream completes — the
on-consume half of the belt-and-braces cleanup (the periodic sweep is the
other half). This response construction is wiring, not business logic.
"""

from __future__ import annotations

import os
from contextlib import suppress
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from narrare._app.dependencies_auth import CurrentUserIdDep
from narrare.export.contracts import ExportJob
from narrare.export.dependencies import get_export_service
from narrare.export.schemas import ExportRequest, FormatAvailability
from narrare.export.service import ExportServiceImpl

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/formats", response_model=list[FormatAvailability])
async def list_formats(
    service: ExportServiceImpl = Depends(get_export_service),
) -> list[FormatAvailability]:
    """List every format + whether its render binary is available (RULE-11)."""
    available = await service.list_formats()
    return [FormatAvailability(format=fmt, available=ok) for fmt, ok in available]


@router.post("", response_model=ExportJob, status_code=status.HTTP_201_CREATED)
async def create_export(
    request: ExportRequest,
    user_id: CurrentUserIdDep,
    service: ExportServiceImpl = Depends(get_export_service),
) -> ExportJob:
    """Create + dispatch an export job (201). 404 if the novel is not owned by
    the caller (foreign ≡ unknown); 503 if the format is unavailable."""
    return await service.export(request.novel_id, request.options, UUID(user_id))


@router.get("/jobs/{job_id}", response_model=ExportJob)
async def get_export_job(
    job_id: str,
    user_id: CurrentUserIdDep,
    service: ExportServiceImpl = Depends(get_export_service),
) -> ExportJob:
    """Poll an export job's status (owner-only; 404 if unknown or foreign —
    including lost on restart, D1)."""
    return await service.get_job(job_id, UUID(user_id))


@router.get("/jobs/{job_id}/artifact")
async def download_export_artifact(
    job_id: str,
    user_id: CurrentUserIdDep,
    token: str = Query(..., description="Single-use artifact token from the job's artifact_url."),
    service: ExportServiceImpl = Depends(get_export_service),
) -> FileResponse:
    """Download the artifact once (200 stream, 404 unknown/foreign, 410 gone).

    Proxies the file as an attachment (per the IO-001 decision: a proxied
    stream, NOT a 302 redirect). The temp file is unlinked after the response
    stream completes via the ``BackgroundTask``.
    """
    artifact = await service.consume_artifact(job_id, token, UUID(user_id))
    return FileResponse(
        path=str(artifact.path),
        media_type=artifact.media_type,
        filename=artifact.suggested_filename,
        background=BackgroundTask(_unlink, str(artifact.path)),
    )


def _unlink(path: str) -> None:
    """Best-effort temp-file unlink (the sweep is the safety net)."""
    # Already gone (sweep ran first, or double-download guarded by the
    # registry's single-use flag) — silent: not an error.
    with suppress(OSError):
        os.unlink(path)
