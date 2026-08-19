"""SeriesHistoryProvider — Backend→Core bridge for ``{{series_history}}``.

Spec 2, Task 7 (SERIES-002). Pre-fetches the data the pure-Core
:class:`~narrare_core.context.series_history.SeriesHistoryTier` needs
(prior bands' ``BandSummary`` rows + their ``series_position`` / ``title``),
builds the cross-boundary :class:`BandSummaryData` value objects, and calls
``SeriesHistoryTier.assemble``. The resulting string is injected by the
writing service into the ``{{series_history}}`` governed prompt variable.

Why this lives in the Backend (RULE-07): the tier is pure formatting +
truncation with zero ``apps/`` imports; every DB read happens here. This
mirrors how :class:`~narrare.kb._context_provider.KBContextProvider`
(ADR-067) wraps a Core render contract behind Backend fetches.

KB-Redirect (Spec 2 §3.1): :meth:`resolve_kb_fetch_mode` encodes the
series-vs-standalone KB decision — series novels use
``find_merged_for_novel`` (Canon + Overlay); standalones keep the
per-novel query.

RULE-11 (graceful degradation): standalone novels, band 1 (no prior), and
missing summaries all yield ``""`` so generation proceeds unchanged.

See:
    docs/superpowers/plans/2026-08-02-series-generation-context.md (Task 7),
    docs/_shared/CONSTRAINTS.md (RULE-06, RULE-07, RULE-11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET
from narrare_core.context.series_history import BandSummaryData, SeriesHistoryTier

if TYPE_CHECKING:
    import uuid

    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.band_summary_contracts import BandSummaryRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.series.schemas import NovelRow

logger = structlog.get_logger(__name__)

#: Default token budget for the series-history block (ADR-082 D1: 16,000,
#: derived from the Core constant — the old 512/512 mirror pair was the C5
#: defect). The production call site passes the resolved cascade value
#: (writing/_helpers.py, Task 3); this default covers unparameterized calls.
_DEFAULT_TOKEN_BUDGET: int = DEFAULT_SERIES_HISTORY_BUDGET

#: Default recency window when no SeriesSettings row exists (mirrors the ORM
#: + migration 0038 server_default of 3).
_DEFAULT_WINDOW_SIZE: int = 3


class SeriesHistoryProvider:
    """Assembles the series-history context string for the writing pipeline.

    The class is stateless apart from its injected repositories; all inputs
    are parameters to :meth:`assemble_series_history`.
    """

    def __init__(
        self,
        *,
        novel_repo: NovelRepositoryProtocol,
        series_repo: SeriesRepositoryProtocol,
        band_summary_repo: BandSummaryRepositoryProtocol,
        tier: SeriesHistoryTier | None = None,
    ) -> None:
        """Initialise the provider with its Backend repositories.

        Args:
            novel_repo: Loads the current novel (series_id, series_position).
            series_repo: Lists member novels + reads ``context_window_size``.
            band_summary_repo: Loads each prior band's summary row.
            tier: Optional Core :class:`SeriesHistoryTier` (default → real).
        """
        self._novel_repo = novel_repo
        self._series_repo = series_repo
        self._band_summary_repo = band_summary_repo
        self._tier = tier or SeriesHistoryTier()

    async def assemble_series_history(
        self,
        novel_id: uuid.UUID,
        *,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> str:
        """Assemble the ``Previously in this series:`` block for a novel.

        Args:
            novel_id: The novel (band) being generated for.
            token_budget: Maximum estimated tokens for the block.

        Returns:
            The formatted series-history string, or ``""`` when the novel is
            standalone, is band 1 (no prior bands), or no prior band has a
            usable summary (RULE-11 graceful degradation).
        """
        novel = await self._novel_repo.get(novel_id)
        # Standalone novel (or missing) → no series history.
        if novel is None or novel.series_id is None or novel.series_position is None:
            return ""

        members = await self._series_repo.list_novels(novel.series_id)
        prior = [
            m
            for m in members
            if m.series_position is not None and m.series_position < novel.series_position
        ]
        if not prior:
            return ""  # band 1 — nothing came before

        window_size = await self._resolve_window_size(novel.series_id)
        bands = await self._collect_band_data(prior)

        if not bands:
            return ""

        return await self._tier.assemble(
            bands,
            window_size=window_size,
            token_budget=token_budget,
        )

    async def collect_series_band_data(self, series_id: uuid.UUID) -> list[BandSummaryData]:
        """Fetch band data for EVERY positioned member of a series (C1).

        Next-band semantics: unlike :meth:`assemble_series_history` (which
        keeps only positions below the current novel), this returns all
        positioned members — the Series-Workspace preview describes the
        generation of the NEXT band, for which every existing band is a
        prior band. Pure data fetch; no windowing or budgeting here (the
        caller runs the Core tier's ``preview`` over the result).
        """
        members = await self._series_repo.list_novels(series_id)
        positioned = [m for m in members if m.series_position is not None]
        return await self._collect_band_data(positioned)

    async def resolve_kb_fetch_mode(self, novel_id: uuid.UUID) -> str:
        """Return the KB fetch strategy for a novel (Spec 2 §3.1 KB-Redirect).

        Args:
            novel_id: The novel whose KB context is being assembled.

        Returns:
            ``"merged"`` for series novels (Canon + Overlay via
            ``find_merged_for_novel``), ``"per_novel"`` for standalone novels
            (the existing per-novel query). An unknown novel safely defaults
            to ``"per_novel"`` (RULE-11 — never merged for a novel whose
            series membership can't be confirmed).
        """
        novel = await self._novel_repo.get(novel_id)
        if novel is not None and novel.series_id is not None:
            return "merged"
        return "per_novel"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _resolve_window_size(self, series_id: uuid.UUID) -> int:
        """Load ``context_window_size`` from SeriesSettings (default 3)."""
        settings = await self._series_repo.get_settings(series_id)
        if settings is None:
            return _DEFAULT_WINDOW_SIZE
        # ``context_window_size`` is an explicit Core-schema field (default 3);
        # ``getattr`` keeps this robust if a caller supplies a stripped view.
        value = getattr(settings, "context_window_size", _DEFAULT_WINDOW_SIZE)
        return int(value) if value is not None else _DEFAULT_WINDOW_SIZE

    async def _collect_band_data(
        self,
        prior_novels: list[NovelRow],
    ) -> list[BandSummaryData]:
        """Build BandSummaryData for each prior band (skip empty)."""
        bands: list[BandSummaryData] = []
        # Mechanical narrowing: both callers pass position-filtered members,
        # but the ``int | None`` attribute type survives the list boundary.
        # The comprehension's ``if`` clause narrows ``series_position`` for
        # the tuple body, so ``position`` is a plain ``int`` below.
        positioned = [
            (member, member.series_position)
            for member in prior_novels
            if member.series_position is not None
        ]
        for member, position in positioned:
            summary = await self._band_summary_repo.get(member.id)
            bands.append(
                BandSummaryData(
                    position=position,
                    title=member.title,
                    full_summary=summary.full_summary if summary else None,
                    short_summary=summary.short_summary if summary else None,
                    override=summary.override if summary else None,
                )
            )
        return bands
