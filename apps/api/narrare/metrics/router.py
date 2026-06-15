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

    Includes OTel health-severity status so operators can detect degraded
    observability from the health endpoint.

    ``status`` reflects the OTel severity (``healthy`` | ``degraded`` |
    ``critical``).  HTTP 200 is returned for both ``healthy`` and ``degraded``
    per liveness semantics (INV-OH-5).  ``critical`` semantics are reserved for
    a future mandatory-telemetry deployment profile.
    """
    obs = get_observability_status()
    return {"status": obs["severity"], "observability": obs}


@router.get("/ready")
async def ready() -> Response:
    """Readiness check — confirms the service can handle requests."""
    try:
        engine = await get_engine()
        async with engine.connect() as conn:
            # narrare: allow reason="Health check bypasses repository to verify raw DB connectivity"
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
