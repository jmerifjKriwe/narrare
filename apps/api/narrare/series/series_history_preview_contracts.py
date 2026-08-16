"""Service contract for the series-history preview (C1 — RULE-03 contract
first; RULE-04: separate file because ``series/contracts.py`` is at its
200-line limit — ``band_summary_contracts.py`` precedent).

Ownership contract (mirrors ``SeriesServiceProtocol``): ``get_preview``
verifies the caller owns the series BEFORE any read; a missing series and
a not-owned series BOTH surface as ``ForbiddenError`` (HTTP 403,
anti-enumeration — never 404).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.series.series_history_preview_schemas import (
        SeriesHistoryPreviewResponse,
    )


@runtime_checkable
class SeriesHistoryPreviewServiceProtocol(Protocol):
    """Read surface for the C1 slider honesty preview."""

    async def get_preview(
        self, series_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesHistoryPreviewResponse:
        """Compute per-window previews for a series' actual summaries.

        Args:
            series_id: The series whose Settings-tab preview is requested.
            user_id: Authenticated caller (ownership enforced, 403 on
                missing/not-owned — anti-enumeration).

        Returns:
            Window sizes 1..max(slider top, current saved window) computed
            against the effective ADR-082 series-history ceiling.
        """
        ...
