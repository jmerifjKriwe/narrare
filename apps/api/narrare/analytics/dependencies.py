# apps/api/narrare/analytics/dependencies.py
"""Analytics dependency injection factories — wiring only, no business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI
from narrare.analytics.writing_stats_recorder import WritingStatsRecorder

if TYPE_CHECKING:
    from narrare.analytics.service import CostQueryService


def get_cost_query_service(session: SessionDep) -> CostQueryService:
    """Production wiring: usage-record repository + cost query service.

    The budget overlay (spec A-6) reads the caller's settings through the
    user-AI-settings repository over the SAME request session — one
    transaction, no extra connection.
    """
    from narrare.analytics.repository import UsageRecordRepository
    from narrare.analytics.service import CostQueryService
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository

    return CostQueryService(
        UsageRecordRepository(session),
        budget_settings_repo=UserAiSettingsRepository(session),
    )


def get_writing_stats_recorder() -> WritingStatsRecorder:
    """Production wiring for the STATS-001 content-write capture seam.

    The recorder deliberately does NOT use the request session: it opens
    its own short-lived session per event (RULE-08) so a stats write can
    never join — or be rolled back with — the caller's transaction. The
    standalone session factory from ``_app.database`` is exactly the
    infrastructure seam for sessions outside the request lifecycle.
    """
    from narrare._app.database import get_session_factory
    from narrare.analytics.writing_stats_recorder import SqlWritingStatsRecorder

    return SqlWritingStatsRecorder(get_session_factory())


WritingStatsRecorderDep = Annotated[WritingStatsRecorder, Depends(get_writing_stats_recorder)]
