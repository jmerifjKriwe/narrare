"""DI factory for the Series History Preview endpoint (C1, Task 4).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress —
the file-size ratchet enforces a 200-line hard limit for dependency
modules; ``dependencies_voice_drift.py`` precedent). The context-window
slider preview is logically separable from the CRUD/join factories and
lives behind its own route, so it gets its own dependency module (one
responsibility per file, RULE-06).

The ADR-082 budget resolution is wired LAZILY (ADR-086, M-budget /
S4b shape — ``dependencies_beta_reader.py`` precedent): the factory
wires a ``LazyModelResolution`` around the WRITE-intent routing cascade
and a deferred budgets composition awaiting BOTH cascades (routing +
token limits, RULE-18/18b — sources unchanged, only timing moves) plus
``resolve_context_budgets(series_in_scope=True)``. No resolution happens
at construction: FastAPI solves all sub-dependencies BEFORE request
validation, so an eager resolve here would preempt legitimate 422s with
a 400 ``NO_AI_PROVIDER``. The composition runs once at the service's
first use (``ensure_resolved``, after the ownership gate);
``ConfigurationError`` propagates loudly from the entry point
(RULE-11 — auth-mandatory router). No business logic lives here — only
wiring (RULE-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import SessionDep, get_current_user_id
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
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

    Wires the budgets composition over the exact ADR-082 production
    chain so the preview can never drift from generation-time values:
    WRITE-intent model routing → TokenLimitsService cascade →
    resolve_context_budgets(series_in_scope=True). ``project_id=None``
    because the preview subject is the NEXT band (no novel id yet) —
    user/operator-level routing and cascade overrides apply; the
    project-level caveat is documented in the SERIES-002 spec.

    Neither cascade resolves here (ADR-086): construction happens
    pre-validation, and eager resolution would preempt 422s with the
    routing cascade's 400. Both run once inside the deferred
    composition at the service's first use.
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
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.WRITE, UUID(user_id), None)
    )

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )

    async def compose_budgets() -> EffectiveContextBudgets:
        """Compose the effective budgets at first use (ADR-082/086).

        Awaits the (cached) WRITE-intent routing resolution and the
        token-limits cascade, then freezes the series-scoped budgets
        the preview fits against.
        """
        resolved = await model_resolution.resolve()
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=None,
        )
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
        budgets_factory=compose_budgets,
    )
