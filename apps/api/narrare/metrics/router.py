"""Health, readiness, and Prometheus metrics endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from narrare._app.database import get_engine

router = APIRouter(tags=["monitoring"])

logger = structlog.get_logger(__name__)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus scraping endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check — confirms the process is running."""
    return {"status": "ok"}


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
