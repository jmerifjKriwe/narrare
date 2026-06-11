"""Tests für Cache-Hit Observability (ADR-016 Phase 2).

Covers:
- record_cache_usage metrics recording
- TokenUsage cache fields
- NarrareObservability cache stats extraction
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, patch

from narrare_core.agents.capabilities.observability import NarrareObservability
from narrare_core.llm.result import TokenUsage

# ---------------------------------------------------------------------------
# record_cache_usage
# ---------------------------------------------------------------------------


class TestRecordCacheUsage:
    """record_cache_usage records Prometheus cache metrics."""

    @patch("narrare_core.llm.metrics.llm_cache_hit_total")
    @patch("narrare_core.llm.metrics.llm_cache_read_tokens_total")
    def test_cache_read_increments_hit_counter(
        self, mock_read_total: AsyncMock, mock_hit_total: AsyncMock
    ) -> None:
        """cache_read > 0 → increments hit counter and read tokens counter."""
        from narrare_core.llm.metrics import record_cache_usage

        record_cache_usage(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
            cache_read_tokens=500,
            cache_creation_tokens=0,
        )
        mock_hit_total.labels.assert_called_once_with(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
        )
        mock_read_total.labels.assert_called_once_with(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
        )

    @patch("narrare_core.llm.metrics.llm_cache_creation_tokens_total")
    def test_cache_creation_increments_creation_counter(
        self,
        mock_creation_total: AsyncMock,
    ) -> None:
        """cache_creation > 0 → increments creation tokens counter."""
        from narrare_core.llm.metrics import record_cache_usage

        record_cache_usage(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
            cache_read_tokens=0,
            cache_creation_tokens=200,
        )
        mock_creation_total.labels.assert_called_once_with(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
        )

    @patch("narrare_core.llm.metrics.llm_cache_miss_total")
    def test_both_zero_increments_miss_counter(
        self,
        mock_miss_total: AsyncMock,
    ) -> None:
        """cache_read=0 and cache_creation=0 → increments miss counter."""
        from narrare_core.llm.metrics import record_cache_usage

        record_cache_usage(
            intent="write",
            model="gpt-4o",
            provider="openai",
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
        mock_miss_total.labels.assert_called_once_with(
            intent="write",
            model="gpt-4o",
            provider="openai",
        )

    @patch("narrare_core.llm.metrics.llm_cache_hit_total")
    @patch("narrare_core.llm.metrics.llm_cache_read_tokens_total")
    @patch("narrare_core.llm.metrics.llm_cache_creation_tokens_total")
    def test_both_nonzero_increments_hit_and_creation(
        self,
        mock_creation_total: AsyncMock,
        mock_read_total: AsyncMock,
        mock_hit_total: AsyncMock,
    ) -> None:
        """Both cache_read > 0 and cache_creation > 0 → both counters."""
        from narrare_core.llm.metrics import record_cache_usage

        record_cache_usage(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
            cache_read_tokens=500,
            cache_creation_tokens=200,
        )
        mock_hit_total.labels.assert_called_once()
        mock_read_total.labels.assert_called_once()
        mock_creation_total.labels.assert_called_once()


# ---------------------------------------------------------------------------
# TokenUsage cache fields
# ---------------------------------------------------------------------------


class TestTokenUsageCacheFields:
    """TokenUsage supports cache_read_tokens and cache_creation_tokens."""

    def test_cache_fields_default_to_zero(self) -> None:
        """New fields default to 0 (backward compatible)."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0

    def test_cache_fields_can_be_set(self) -> None:
        """Cache fields can be populated."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=500,
            cache_creation_tokens=200,
        )
        assert usage.cache_read_tokens == 500
        assert usage.cache_creation_tokens == 200

    def test_backward_compat_without_cache_fields(self) -> None:
        """Existing TokenUsage creation without cache fields still works."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            provider="anthropic",
            model="claude-sonnet-4-5-20251020",
        )
        assert usage.cache_read_tokens == 0
        with patch(
            "narrare_core.llm.cost_rates.get_rates",
            return_value={"input": 3.0, "output": 15.0},
        ):
            assert usage.cost_estimate_usd > 0


# ---------------------------------------------------------------------------
# NarrareObservability — cache stats extraction
# ---------------------------------------------------------------------------


class TestNarrareObservabilityCache:
    """NarrareObservability extracts cache stats from usage.details."""

    @patch("narrare_core.agents.capabilities.observability.record_success")
    @patch("narrare_core.agents.capabilities.observability.record_cache_usage")
    async def test_extracts_cache_stats_from_details(
        self,
        mock_cache_usage: AsyncMock,
        mock_record_success: AsyncMock,
    ) -> None:
        """after_model_request extracts cache_read + cache_creation from details."""
        obs = NarrareObservability()
        obs._start_time = 0.0
        obs._intent = "write"
        obs._model_id = "claude-sonnet-4-5-20251020"
        obs._provider_name = "anthropic"

        class FakeUsage:
            input_tokens = 100
            output_tokens = 50
            total_tokens = 150

            def __init__(self) -> None:
                self.details: dict[str, int] = {
                    "cache_read_input_tokens": 500,
                    "cache_creation_input_tokens": 200,
                }

        class FakeCtx:
            usage = FakeUsage()

        await obs.after_model_request(
            cast("Any", FakeCtx()),
            request_context=cast("Any", None),
            response=cast("Any", None),
        )

        # record_cache_usage should be called with extracted cache stats
        mock_cache_usage.assert_called_once_with(
            intent="write",
            model="claude-sonnet-4-5-20251020",
            provider="anthropic",
            cache_read_tokens=500,
            cache_creation_tokens=200,
        )

    @patch("narrare_core.agents.capabilities.observability.record_success")
    @patch("narrare_core.agents.capabilities.observability.record_cache_usage")
    async def test_no_cache_stats_does_not_call_record_cache_usage(
        self,
        mock_cache_usage: AsyncMock,
        mock_record_success: AsyncMock,
    ) -> None:
        """No cache stats in details → record_cache_usage not called."""
        obs = NarrareObservability()
        obs._start_time = 0.0

        class FakeUsage:
            input_tokens = 100
            output_tokens = 50
            total_tokens = 150

            def __init__(self) -> None:
                self.details: dict[str, int] = {}

        class FakeCtx:
            usage = FakeUsage()

        await obs.after_model_request(
            cast("Any", FakeCtx()),
            request_context=cast("Any", None),
            response=cast("Any", None),
        )

        mock_cache_usage.assert_not_called()

    @patch("narrare_core.agents.capabilities.observability.record_success")
    @patch("narrare_core.agents.capabilities.observability.record_cache_usage")
    async def test_missing_details_attribute(
        self,
        mock_cache_usage: AsyncMock,
        mock_record_success: AsyncMock,
    ) -> None:
        """Missing details attribute → graceful fallback (no error)."""
        obs = NarrareObservability()
        obs._start_time = 0.0

        class FakeUsage:
            input_tokens = 100
            output_tokens = 50
            total_tokens = 150
            # no details attribute

        class FakeCtx:
            usage = FakeUsage()

        await obs.after_model_request(
            cast("Any", FakeCtx()),
            request_context=cast("Any", None),
            response=cast("Any", None),
        )

        mock_cache_usage.assert_not_called()

    @patch("narrare_core.agents.capabilities.observability.record_success")
    @patch("narrare_core.agents.capabilities.observability.record_cache_usage")
    async def test_token_usage_includes_cache_fields(
        self,
        mock_cache_usage: AsyncMock,
        mock_record_success: AsyncMock,
    ) -> None:
        """TokenUsage built in after_model_request includes cache fields."""
        obs = NarrareObservability()
        obs._start_time = 0.0
        obs._intent = "write"
        obs._model_id = "test-model"
        obs._provider_name = "test-provider"

        class FakeUsage:
            input_tokens = 100
            output_tokens = 50
            total_tokens = 150

            def __init__(self) -> None:
                self.details: dict[str, int] = {
                    "cache_read_input_tokens": 300,
                    "cache_creation_input_tokens": 0,
                }

        class FakeCtx:
            usage = FakeUsage()

        await obs.after_model_request(
            cast("Any", FakeCtx()),
            request_context=cast("Any", None),
            response=cast("Any", None),
        )

        # Verify record_success was called with TokenUsage that has cache fields
        call_args = mock_record_success.call_args
        token_usage = call_args.kwargs["usage"]
        assert isinstance(token_usage, TokenUsage)
        assert token_usage.cache_read_tokens == 300
        assert token_usage.cache_creation_tokens == 0
