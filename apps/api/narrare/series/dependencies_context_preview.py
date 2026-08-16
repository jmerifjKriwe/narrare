"""DI factory for the Series History Preview endpoint (C1, Task 4).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress —
the file-size ratchet enforces a 200-line hard limit for dependency
modules; ``dependencies_voice_drift.py`` precedent). The context-window
slider preview is logically separable from the CRUD/join factories and
lives behind its own route, so it gets its own dependency module (one
responsibility per file, RULE-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import SessionDep, get_current_user_id
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.novels.repository import NovelRepository
from narrare.series.band_summary_repository import BandSummaryRepository
from narrare.series.repository import SeriesRepository
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
    from narrare_core.context.contracts import EffectiveContextBudgets


async def get_series_history_preview_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> SeriesHistoryPreviewService:
    """Request-scoped SeriesHistoryPreviewService (C1 slider preview).

    Resolves the effective budgets through the exact ADR-082 production
    chain so the preview can never drift from generation-time values:
    WRITE-intent model routing → TokenLimitsService cascade →
    resolve_context_budgets(series_in_scope=True). ``project_id=None``
    because the preview subject is the NEXT band (no novel id yet) —
    user/operator-level routing and cascade overrides apply; the
    project-level caveat is documented in the SERIES-002 spec.
    """
    from narrare._app.config import get_settings
    from narrare.series.series_history_preview_service import SeriesHistoryPreviewService
    from narrare.series.series_history_provider import SeriesHistoryProvider
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.WRITE, UUID(user_id), None)

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=None,
    )

    def budgets_provider() -> EffectiveContextBudgets:
        return resolve_context_budgets(
            limits=limits,
            config=resolved.config,
            series_in_scope=True,
        )

    series_repo = SeriesRepository(session)
    provider = SeriesHistoryProvider(
        novel_repo=NovelRepository(session),
        series_repo=series_repo,
        band_summary_repo=BandSummaryRepository(session),
    )
    return SeriesHistoryPreviewService(
        series_repo=series_repo,
        provider=provider,
        budgets_provider=budgets_provider,
    )
