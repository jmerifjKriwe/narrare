"""Bulk extraction job routes — start/status/results/cancel/resume (ADR-092 §4).

Thin delegation to :class:`BulkExtractionService` (RULE-06); a separate
module from ``router_extraction.py`` because that file is already at its
RULE-04 budget (106/150 lines). Routes mirror the export-job shape
(owner-pinned in-memory job + poll endpoints, ADR-081).

Error translation lives in the global ``NarrareError`` handler
(``_app/main.py``): the services' ``NotFoundError`` → 404 (foreign novel
AND foreign/unknown job — foreign ≡ unknown), ``ConflictError`` → 409,
``ValidationError`` → 422 — so this router carries no try/except (the
``router_canon.py`` precedent).

NO ``AI_ANALYSIS_LIMITER`` dependency on this surface: no LLM call happens
in-request — the background runner paces its agent calls against the same
shared analysis budget (ADR-092 D7a). A limiter here would throttle only
the cheap bookkeeping calls.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.bulk_extraction.dependencies import get_bulk_extraction_service
from narrare.kb.bulk_extraction.schemas import (
    BulkExtractionJobView,
    BulkExtractionResultsView,
    BulkExtractionStartRequest,
    BulkExtractionStatusView,
)
from narrare.kb.bulk_extraction.service import BulkExtractionService

router = APIRouter(tags=["kb-extraction"])


@router.post(
    "/novels/{novel_id}/kb/extract/bulk",
    response_model=BulkExtractionJobView,
    status_code=status.HTTP_201_CREATED,
)
async def start_bulk_extraction(
    novel_id: UUID,
    body: BulkExtractionStartRequest,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> BulkExtractionJobView:
    """Start a bulk extraction job over the given chapters (spec §4.1).

    Returns the job view (201, status ``pending``); the chapter list is
    NOT echoed — the status endpoint carries it.
    """
    return await service.start(novel_id, UUID(user_id), body.chapter_ids)


@router.get(
    "/novels/{novel_id}/kb/extract/bulk/{job_id}/status",
    response_model=BulkExtractionStatusView,
)
async def get_bulk_extraction_status(
    novel_id: UUID,
    job_id: str,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> BulkExtractionStatusView:
    """Poll one job: totals plus per-chapter states (spec §4.2)."""
    return await service.status(novel_id, job_id, UUID(user_id))


@router.get(
    "/novels/{novel_id}/kb/extract/bulk/{job_id}/results",
    response_model=BulkExtractionResultsView,
)
async def get_bulk_extraction_results(
    novel_id: UUID,
    job_id: str,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> BulkExtractionResultsView:
    """Full extraction outputs for the review panel (spec §4.3).

    Readable in ANY job state — partial results of a cancelled job are the
    resume baseline; ``output`` is present iff the chapter is ``done``.
    """
    return await service.results(novel_id, job_id, UUID(user_id))


@router.post(
    "/novels/{novel_id}/kb/extract/bulk/{job_id}/cancel",
    response_model=BulkExtractionJobView,
)
async def cancel_bulk_extraction(
    novel_id: UUID,
    job_id: str,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> BulkExtractionJobView:
    """Request a cooperative cancel (spec §4.4); terminal jobs conflict (409)."""
    return await service.cancel(novel_id, job_id, UUID(user_id))


@router.post(
    "/novels/{novel_id}/kb/extract/bulk/{job_id}/resume",
    response_model=BulkExtractionJobView,
)
async def resume_bulk_extraction(
    novel_id: UUID,
    job_id: str,
    user_id: CurrentUserIdDep,
    service: BulkExtractionService = Depends(get_bulk_extraction_service),
) -> BulkExtractionJobView:
    """Reset a cancelled/failed job and re-dispatch its runner (spec §4.5)."""
    return await service.resume(novel_id, job_id, UUID(user_id))
