# apps/api/narrare/analytics/dependencies.py
"""Analytics dependency injection factories — wiring only, no business logic."""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI DI resolution
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Query

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare.analytics.writing_stats_recorder import WritingStatsRecorder
from narrare.novels.ownership import require_owned_novel

if TYPE_CHECKING:
    from narrare.analytics.service import CostQueryService
    from narrare.analytics.writing_service import WritingQueryService


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


def get_writing_query_service(session: SessionDep) -> WritingQueryService:
    """Production wiring: writing read repository + query service (STATS-001 E4).

    The goal overlay reads through the ``GoalSource`` seam (spec E-4): until
    E5 lands ``ProjectSettings.writing_goals`` the ``NullGoalSource``
    placeholder reports "no goal" — E5 swaps exactly this one argument and
    nothing else changes.
    """
    from narrare.analytics.writing_repository import WritingStatsQueryRepository
    from narrare.analytics.writing_service import NullGoalSource, WritingQueryService

    return WritingQueryService(
        WritingStatsQueryRepository(session),
        goal_source=NullGoalSource(),
    )


async def verify_writing_novel_scope(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID | None = Query(default=None),  # noqa: B008 — FastAPI DI pattern
) -> None:
    """Ownership gate for the OPTIONAL ``novel_id`` filter on GET /analytics/writing.

    No-op for the user-scope report (``novel_id`` absent — no query). When
    present, the canonical ``require_owned_novel`` gate applies: foreign ≡
    unknown → ``NotFoundError`` → 404 (anti-enumeration semantics pinned by
    the IDOR matrices). Lives here, not in the router, so the route stays
    pure delegation (RULE-06) — same shape as the S11a/S13 route gates.
    """
    if novel_id is not None:
        await require_owned_novel(session, user_id, novel_id)
