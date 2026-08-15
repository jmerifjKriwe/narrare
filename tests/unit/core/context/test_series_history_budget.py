"""Tests for the SeriesHistoryTier default token budget (ADR-082 D1).

Split out of ``test_series_history.py`` (C5 Task 1b fix): appending the
``TestDefaultBudget`` class there pushed the module past the 400-line
test-file limit (RULE-04 ratchet). The class is unchanged; the ``_band``
/ ``_long`` helpers are imported from the original module.
"""

from __future__ import annotations

from narrare_core.context.budget import DEFAULT_SERIES_HISTORY_BUDGET
from narrare_core.context.series_history import SeriesHistoryTier
from tests.unit.core.context.test_series_history import _band, _long


class TestDefaultBudget:
    """The re-defaulted 16,000-token budget fixes the C5 headline defect:
    the default recency window (3 full band summaries) now fits."""

    async def test_default_budget_delivers_three_full_bands(self) -> None:
        bands = [
            _band(1, full=_long("B1"), short="S1"),
            _band(2, full=_long("B2"), short="S2"),
            _band(3, full=_long("B3"), short="S3"),
        ]
        tier = SeriesHistoryTier()

        result = await tier.assemble(bands=bands, window_size=3)

        # All three bands complete — under the old 512 default, band 2
        # truncated and band 3+ was silently dropped.
        assert "B1START" in result and "B1END" in result
        assert "B2START" in result and "B2END" in result
        assert "B3START" in result and "B3END" in result

    async def test_assemble_default_token_budget_is_core_constant(self) -> None:
        import inspect

        signature = inspect.signature(SeriesHistoryTier.assemble)

        assert signature.parameters["token_budget"].default == DEFAULT_SERIES_HISTORY_BUDGET
