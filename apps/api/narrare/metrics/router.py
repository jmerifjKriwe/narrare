"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import text

from narrare._app.database import get_engine
from narrare._app.observability import get_observability_status

router = APIRouter(tags=["monitoring"])

logger = structlog.get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness check — confirms the process is running.

    Includes OTel availability status so operators can detect degraded
    observability from the health endpoint.
    """
    return {"status": "ok", "observability": get_observability_status()}


@router.get("/ready")
async def ready() -> Response:
    """Readiness check — confirms the service can handle requests."""
    try:
        engine = await get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse(content={"status": "ready"})
    except Exception as e:
        logger.warning("readiness_check_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest

    return PlainTextResponse(content=generate_latest(), media_type="text/plain")
