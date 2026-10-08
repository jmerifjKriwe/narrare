# apps/api/narrare/analytics/router.py
"""Analytics costs routes — thin delegation (RULE-06: no business logic here).

The :func:`invalid_month_error_handler` below must be registered app-level in
``_app/main.create_app`` (Task 11 wiring):
``app.exception_handler(InvalidMonthError)(invalid_month_error_handler)`` —
the decorator form, which mirrors the ``ScopeError`` precedent and accepts the
narrow exc type under pyright (``add_exception_handler`` does not). Without
it, regex-valid but unconstructible months (``0000-01``, ``9999-12``) pass the
Query pattern, are rejected by the service's defensive validation, and would
surface as 500 instead of 422.

The CSV export route depends on the concrete ``CostQueryService`` (house
pattern: chat/series/wiki routers inject concrete services): its streaming
methods are beyond the read-only ``CostQueryServiceProtocol`` seam, and no
typed stream protocol was warranted for this one surface.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep
from narrare.analytics.contracts import (
    CostMonthReport,
    CostQueryServiceProtocol,
    WritingQueryServiceProtocol,
    WritingReport,
)
from narrare.analytics.dependencies import (
    get_cost_query_service,
    get_writing_query_service,
    verify_writing_novel_scope,
)
from narrare.analytics.service import CostQueryService, InvalidMonthError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/costs", response_model=CostMonthReport)
async def get_monthly_costs(
    user_id: CurrentUserIdDep,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    service: CostQueryServiceProtocol = Depends(get_cost_query_service),
) -> CostMonthReport:
    """Monthly AI cost report for the authenticated user (spec §4)."""
    return await service.month_report(uuid.UUID(user_id), month)


@router.get("/writing", response_model=WritingReport)
async def get_writing_report(
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID | None = Query(default=None),
    service: WritingQueryServiceProtocol = Depends(get_writing_query_service),
    _: None = Depends(verify_writing_novel_scope),
) -> WritingReport:
    """Writing report for the authenticated user (STATS-001 spec E-5).

    Optional ``novel_id`` narrows dailies/streaks/today and the all-time
    total to one novel and adds the goal block; ownership is enforced by the
    ``verify_writing_novel_scope`` dependency BEFORE the service runs
    (foreign ≡ unknown → 404).
    """
    return await service.writing_report(uuid.UUID(user_id), novel_id)


@router.get("/costs/export")
async def export_costs_csv(
    user_id: CurrentUserIdDep,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    service: CostQueryService = Depends(get_cost_query_service),
) -> StreamingResponse:
    """Stream the month's usage records as a CSV download (spec B-1..B-5)."""
    headers = service.export_csv_headers(month)  # eager validation → 422 pre-stream
    return StreamingResponse(
        service.export_csv_lines(uuid.UUID(user_id), month),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


async def invalid_month_error_handler(_: Request, exc: InvalidMonthError) -> JSONResponse:
    """Map ``InvalidMonthError`` to 422 (spec §4: invalid month ⇒ 422).

    App-registered handler (Task 11) so the router stays free of try/except
    (RULE-06) — same shape as the ``ScopeError`` handler in ``_app/main.py``.
    """
    logger.warning("invalid_month", detail=str(exc))
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "code": "INVALID_MONTH"},
    )
