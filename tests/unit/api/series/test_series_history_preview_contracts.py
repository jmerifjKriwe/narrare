"""Contract tests for the C1 series-history preview surface (RULE-03).

Schemas mirror the Core SeriesHistoryPreview field-for-field (the service
maps via dataclasses.asdict — name parity is load-bearing) and the Protocol
fixes the service surface the router will depend on.
"""

from __future__ import annotations

from narrare.series.series_history_preview_contracts import (
    SeriesHistoryPreviewServiceProtocol,
)
from narrare.series.series_history_preview_schemas import (
    SeriesHistoryPreviewEntry,
    SeriesHistoryPreviewResponse,
)


class TestEntrySchema:
    def test_mirrors_core_preview_fields(self) -> None:
        from dataclasses import fields as dc_fields

        from narrare_core.context.series_history import SeriesHistoryPreview

        core_names = {f.name for f in dc_fields(SeriesHistoryPreview)}
        schema_names = set(SeriesHistoryPreviewEntry.model_fields)
        assert schema_names == core_names

    def test_constructs_from_core_dict(self) -> None:
        payload = {
            "window_size": 3,
            "token_budget": 16_000,
            "estimated_tokens": 440,
            "bands_total": 5,
            "bands_full": 3,
            "bands_short": 2,
            "bands_truncated": 0,
            "bands_dropped": 0,
            "bands_missing": 0,
            "budget_clipped": False,
        }
        entry = SeriesHistoryPreviewEntry.model_validate(payload)
        assert entry.bands_full == 3
        assert entry.budget_clipped is False


class TestResponseSchema:
    def test_holds_effective_budget_metadata(self) -> None:
        response = SeriesHistoryPreviewResponse(
            series_id="00000000-0000-0000-0000-000000000001",  # pyright: ignore[reportArgumentType]
            current_window_size=3,
            effective_series_history_budget=16_000,
            effective_context_total=32_000,
            effective_tier_base=16_000,
            model_context_window=128_000,
            budget_source="cascade:uncapped",
            previews=[
                SeriesHistoryPreviewEntry.model_validate(
                    {
                        "window_size": 1,
                        "token_budget": 16_000,
                        "estimated_tokens": 150,
                        "bands_total": 5,
                        "bands_full": 1,
                        "bands_short": 4,
                        "bands_truncated": 0,
                        "bands_dropped": 0,
                        "bands_missing": 0,
                        "budget_clipped": False,
                    }
                )
            ],
        )
        assert response.model_context_window == 128_000
        assert response.previews[0].window_size == 1

    def test_model_context_window_allows_none(self) -> None:
        response = SeriesHistoryPreviewResponse(
            series_id="00000000-0000-0000-0000-000000000001",  # pyright: ignore[reportArgumentType]
            current_window_size=3,
            effective_series_history_budget=16_000,
            effective_context_total=32_000,
            effective_tier_base=16_000,
            model_context_window=None,
            budget_source="cascade:window_unknown",
            previews=[],
        )
        assert response.model_context_window is None


class TestProtocol:
    def test_protocol_exposes_get_preview(self) -> None:
        assert hasattr(SeriesHistoryPreviewServiceProtocol, "get_preview")
