"""Series-history preview service (C1 — Context-Window Slider, design §4).

Read model behind ``GET /series/{id}/settings/context-preview``: computes
what the series-history block would contain per candidate window size,
from the series' ACTUAL band summaries against the EFFECTIVE ADR-082
budgets. Honest by construction — no fabricated estimates:

* band data comes from the real ``BandSummary`` rows (via the provider's
  ``collect_series_band_data``, next-band semantics);
* budgets come from the injected ``budgets_factory``, which the DI
  factory builds over the exact production resolution chain
  (``TokenLimitsService`` cascade → model routing →
  ``resolve_context_budgets(series_in_scope=True)``) — the same
  ``EffectiveContextBudgets`` the writing pipeline consumes, never a
  second computation path. Per ADR-086 the composition is LAZY: both
  cascades run once at the service's first use (:meth:`ensure_resolved`,
  after the ownership gate), never at construction — request-validation
  errors surface as 422 before any cascade runs;
* the prediction itself is the Core tier's ``preview`` (same greedy fit
  as real assembly).

Model routing + cascade resolve at user level (``project_id=None``):
the next band has no novel id yet; project-level routing/cascade
overrides for a specific existing novel may differ at that novel's
generation time (documented limitation, see the SERIES-002 spec).

RULE-04: separate file — ``series/service.py`` is at its 300-line limit.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import structlog

from narrare.series.series_history_preview_schemas import (
    SeriesHistoryPreviewEntry,
    SeriesHistoryPreviewResponse,
)
from narrare_core.context.series_history import SeriesHistoryTier
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare.series.series_history_provider import SeriesHistoryProvider
    from narrare_core.context.contracts import EffectiveContextBudgets

logger = structlog.get_logger(__name__)

#: Window used when no SeriesSettings row exists yet (mirrors the ORM
#: default + migration 0038 server_default + provider constant).
_DEFAULT_WINDOW_SIZE: int = 3


class SeriesHistoryPreviewService:
    """Compute per-window series-history previews for the Settings tab."""

    def __init__(
        self,
        *,
        series_repo: SeriesRepositoryProtocol,
        provider: SeriesHistoryProvider,
        budgets_factory: Callable[[], Awaitable[EffectiveContextBudgets]],
        tier: SeriesHistoryTier | None = None,
        slider_max: int = 10,
    ) -> None:
        """Initialize with injected dependencies (all I/O behind fakes-able seams).

        Args:
            series_repo: Ownership check + settings read (window default).
            provider: Band-data fetch (next-band semantics).
            budgets_factory: Zero-arg async callable returning the frozen
                :class:`EffectiveContextBudgets` — built by the DI factory
                over the ADR-082 resolution chain and invoked once at the
                service's first use (ADR-086 lazy resolution; see
                :meth:`ensure_resolved`).
            tier: Optional Core tier override (default → real).
            slider_max: Slider upper bound (design §4: 1-10). Function
                default, not a module constant, by the
                configurable-defaults checker ruling. The computed range
                extends to ``max(slider_max, current_window_size)`` so an
                API-saved value above 10 stays honestly previewable.
        """
        self._series_repo = series_repo
        self._provider = provider
        self._budgets_factory = budgets_factory
        self._budgets: EffectiveContextBudgets | None = None
        self._tier = tier or SeriesHistoryTier()
        self._slider_max = slider_max

    async def ensure_resolved(self) -> EffectiveContextBudgets:
        """Compose the effective budgets at first use (ADR-086, idempotent).

        Invokes the factory's deferred composition — the WRITE-intent
        routing cascade AND the token-limits cascade, then
        ``resolve_context_budgets(series_in_scope=True)`` — exactly once;
        the frozen result is cached for the service's lifetime.
        ``ConfigurationError`` (unconfigured provider) propagates
        un-swallowed (RULE-11 — AI-mandatory endpoint).
        """
        if self._budgets is None:
            self._budgets = await self._budgets_factory()
        return self._budgets

    async def get_preview(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesHistoryPreviewResponse:
        """Compute previews for window sizes 1..max(slider, saved).

        Raises:
            ForbiddenError: If the series is missing or not owned by
                ``user_id`` (anti-enumeration — 403, never 404).
            ConfigurationError: If the user has no AI provider
                configured — resolved lazily at first use, AFTER the
                ownership gate (ADR-086; RULE-11 loud 400).
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")

        # ADR-086: first-use lazy composition of both cascades (routing +
        # token limits), post-validation and post-gate — an unconfigured
        # provider stays a loud 400 (RULE-11), never a preempting
        # factory-time error.
        budgets = await self.ensure_resolved()

        settings = await self._series_repo.get_settings(series_id)
        if settings is None:
            current = _DEFAULT_WINDOW_SIZE
        else:
            value = getattr(settings, "context_window_size", _DEFAULT_WINDOW_SIZE)
            current = int(value) if value is not None else _DEFAULT_WINDOW_SIZE

        bands = await self._provider.collect_series_band_data(series_id)

        top = max(self._slider_max, current)
        previews = [
            SeriesHistoryPreviewEntry.model_validate(
                asdict(
                    await self._tier.preview(
                        bands, window_size=k, token_budget=budgets.series_history
                    )
                )
            )
            for k in range(1, top + 1)
        ]

        logger.info(
            "series_history_preview_computed",
            series_id=str(series_id),
            bands=len(bands),
            current_window=current,
            series_history_budget=budgets.series_history,
        )
        return SeriesHistoryPreviewResponse(
            series_id=series_id,
            current_window_size=current,
            effective_series_history_budget=budgets.series_history,
            effective_context_total=budgets.context_total,
            effective_tier_base=budgets.writing_tier_base,
            model_context_window=budgets.context_window,
            budget_source=budgets.source,
            previews=previews,
        )
