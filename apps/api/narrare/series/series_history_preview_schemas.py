"""Pydantic schemas for the series-history preview (C1 — Context-Window
Slider, design §4; RULE-04: separate file because ``series/schemas.py`` is
at its 200-line limit — ``series_voice_schemas.py`` precedent).

The response is a derived READ MODEL, not persisted state: per-window
predictions computed from the series' actual band summaries against the
effective ADR-082 budgets. ``SeriesHistoryPreviewEntry`` mirrors the Core
``SeriesHistoryPreview`` dataclass field-for-field so the service can map
via ``dataclasses.asdict`` (name parity is load-bearing).

Next-band semantics: the preview describes generating the NEXT band of
this series — every positioned member novel is a prior band (the exact
view ``SeriesHistoryProvider.assemble_series_history`` would have for
that novel). See the feature spec (SERIES-002) and the service docstring.
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution

from pydantic import BaseModel


class SeriesHistoryPreviewEntry(BaseModel):
    """Prediction for one candidate window size (mirrors Core)."""

    window_size: int
    token_budget: int
    """Effective series-history ceiling this prediction was computed against."""
    estimated_tokens: int
    bands_total: int
    bands_full: int
    bands_short: int
    bands_truncated: int
    bands_dropped: int
    bands_missing: int
    budget_clipped: bool


class SeriesHistoryPreviewResponse(BaseModel):
    """GET /api/v1/series/{id}/settings/context-preview response.

    Budget metadata is ``EffectiveContextBudgets`` verbatim (ADR-082 — the
    same resolver output the writing pipeline consumes; no second
    computation path): series novels carve the series-history ceiling out
    of the context total, and the remaining tier base serves the current
    band's own context — the preview copy states this asymmetry.
    """

    series_id: uuid.UUID
    current_window_size: int
    """Saved setting (default 3 when no settings row exists)."""
    effective_series_history_budget: int
    """EffectiveContextBudgets.series_history — the preview's token ceiling."""
    effective_context_total: int
    """EffectiveContextBudgets.context_total."""
    effective_tier_base: int
    """EffectiveContextBudgets.writing_tier_base (total - series history)."""
    model_context_window: int | None
    """Window used for capping (None = unknown/offline, RULE-11 — uncapped)."""
    budget_source: str
    """EffectiveContextBudgets.source provenance tag."""
    previews: list[SeriesHistoryPreviewEntry]
    """Window sizes 1..max(slider top, current_window_size) — one snapshot."""
