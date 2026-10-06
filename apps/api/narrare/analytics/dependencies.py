# apps/api/narrare/analytics/dependencies.py
"""Analytics dependency injection factories — wiring only, no business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analytics.service import CostQueryService


def get_cost_query_service(session: SessionDep) -> CostQueryService:
    """Production wiring: usage-record repository + cost query service."""
    from narrare.analytics.repository import UsageRecordRepository
    from narrare.analytics.service import CostQueryService

    return CostQueryService(UsageRecordRepository(session))
