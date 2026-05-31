"""Tests for llm/observability.py — Langfuse cache observability.

Covers:
1. ``finish_trace()`` with cache data does not raise (no Langfuse configured)
2. ``finish_trace()`` sends ``cache_read`` / ``cache_creation`` to ``generation.end()``
3. ``finish_trace()`` computes ``cache_savings_pct`` from cache_read tokens
4. ``cache_savings_pct`` is 0 when no cache data present
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from narrare_core.llm.observability import LLMObservability
from narrare_core.llm.result import TokenUsage


class TestLLMObservabilityCache:
    """LLMObservability.finish_trace handles cache data correctly."""

    def test_finish_trace_with_cache_data_does_not_raise(self) -> None:
        """Calling finish_trace with cache fields doesn't raise when Langfuse disabled."""
        obs = LLMObservability()
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=30,
            cache_creation_tokens=10,
        )
        # Should not raise even without Langfuse configured
        obs.finish_trace(None, "result", usage, 1000)

    @patch("narrare_core.llm.observability._create_client")
    def test_finish_trace_sends_cache_data_to_generation_end(
        self,
        mock_create: MagicMock,
    ) -> None:
        """finish_trace sends cache_read/cache_creation in the usage dict."""
        mock_client = MagicMock(spec=["trace"])
        mock_trace = MagicMock(spec=["generation"])
        mock_generation = MagicMock(spec=["end"])
        mock_client.trace.return_value = mock_trace
        mock_trace.generation.return_value = mock_generation
        mock_create.return_value = mock_client

        obs = LLMObservability()
        ctx = {"trace": mock_trace, "generation": mock_generation}

        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=30,
            cache_creation_tokens=10,
        )
        obs.finish_trace(ctx, "generated text", usage, 1000)

        mock_generation.end.assert_called_once()
        call_kwargs = mock_generation.end.call_args[1]
        assert call_kwargs["usage"]["cache_read"] == 30
        assert call_kwargs["usage"]["cache_creation"] == 10

    @patch("narrare_core.llm.observability._create_client")
    def test_finish_trace_computes_cache_savings_pct(
        self,
        mock_create: MagicMock,
    ) -> None:
        """finish_trace computes cache_savings_pct = cache_read / prompt_tokens."""
        mock_client = MagicMock(spec=["trace"])
        mock_gen = MagicMock(spec=["end"])
        mock_client.trace.return_value.generation.return_value = mock_gen
        mock_create.return_value = mock_client

        obs = LLMObservability()
        ctx = {
            "trace": mock_client.trace.return_value,
            "generation": mock_gen,
        }

        # 30 cache_read out of 100 prompt tokens = 30%
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=30,
            cache_creation_tokens=0,
        )
        obs.finish_trace(ctx, "result", usage, 1000)

        metadata = mock_gen.end.call_args[1]["metadata"]
        assert metadata["cache_savings_pct"] == 30.0

    @patch("narrare_core.llm.observability._create_client")
    def test_cache_savings_pct_zero_when_no_cache(
        self,
        mock_create: MagicMock,
    ) -> None:
        """cache_savings_pct is 0 when cache_read_tokens is 0."""
        mock_client = MagicMock(spec=["trace"])
        mock_gen = MagicMock(spec=["end"])
        mock_client.trace.return_value.generation.return_value = mock_gen
        mock_create.return_value = mock_client

        obs = LLMObservability()
        ctx = {
            "trace": mock_client.trace.return_value,
            "generation": mock_gen,
        }

        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        obs.finish_trace(ctx, "result", usage, 1000)

        metadata = mock_gen.end.call_args[1]["metadata"]
        assert metadata["cache_savings_pct"] == 0
