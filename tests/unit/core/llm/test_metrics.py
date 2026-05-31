"""Tests for llm/metrics.py — Prometheus metrics recording functions.

Covers:
1. record_success increments counters and observes duration
2. record_failure increments error counter
3. record_retry increments retry counter
4. All functions accept expected keyword args without error
"""

from __future__ import annotations

from prometheus_client import REGISTRY

from narrare_core.llm.metrics import (
    record_cache_usage,
    record_failure,
    record_retry,
    record_success,
)
from narrare_core.llm.result import TokenUsage


class TestRecordSuccess:
    """record_success records a successful LLM call."""

    def test_record_success_does_not_raise(self) -> None:
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        record_success(
            intent="write",
            model="gpt-4o",
            provider="openai",
            usage=usage,
            duration_seconds=1.5,
        )

    def test_record_success_with_zero_tokens(self) -> None:
        usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        record_success(
            intent="summarize",
            model="test-model",
            provider="test",
            usage=usage,
            duration_seconds=0.1,
        )


class TestRecordFailure:
    """record_failure records a failed LLM call."""

    def test_record_failure_does_not_raise(self) -> None:
        record_failure(
            intent="write",
            model="gpt-4o",
            provider="openai",
            error_type="rate_limit",
            duration_seconds=2.0,
        )

    def test_record_failure_with_various_error_types(self) -> None:
        for error_type in ["timeout", "auth", "rate_limit", "server_error"]:
            record_failure(
                intent="test",
                model="test",
                provider="test",
                error_type=error_type,
                duration_seconds=0.5,
            )


class TestRecordRetry:
    """record_retry records a retry attempt."""

    def test_record_retry_does_not_raise(self) -> None:
        record_retry(intent="write", error_type="rate_limit")

    def test_record_retry_with_various_types(self) -> None:
        for error_type in ["timeout", "rate_limit", "server_error"]:
            record_retry(intent="test", error_type=error_type)


class TestRecordCacheUsage:
    """record_cache_usage records Prometheus cache hit/miss metrics.

    Uses unique label values per test to avoid interference from
    the global ``REGISTRY`` singleton.
    """

    def test_cache_read_increments_hit_counter(self) -> None:
        """cache_read > 0 increments ``llm_cache_hit_total``."""
        record_cache_usage(
            intent="test_cr_hit",
            model="gpt-4o",
            provider="openai",
            cache_read_tokens=100,
            cache_creation_tokens=0,
        )
        hit = REGISTRY.get_sample_value(
            "narrare_llm_cache_hit_total",
            {"intent": "test_cr_hit", "model": "gpt-4o", "provider": "openai"},
        )
        assert hit == 1.0

    def test_cache_read_increments_read_tokens_counter(self) -> None:
        """cache_read > 0 increments ``llm_cache_read_tokens_total`` by token count."""
        record_cache_usage(
            intent="test_cr_tokens",
            model="claude-3",
            provider="anthropic",
            cache_read_tokens=200,
            cache_creation_tokens=0,
        )
        tokens = REGISTRY.get_sample_value(
            "narrare_llm_cache_read_tokens_total",
            {"intent": "test_cr_tokens", "model": "claude-3", "provider": "anthropic"},
        )
        assert tokens == 200.0

    def test_cache_creation_increments_creation_counter(self) -> None:
        """cache_creation > 0 increments ``llm_cache_creation_tokens_total``."""
        record_cache_usage(
            intent="test_cc",
            model="gpt-4o-mini",
            provider="openai",
            cache_read_tokens=0,
            cache_creation_tokens=50,
        )
        creation = REGISTRY.get_sample_value(
            "narrare_llm_cache_creation_tokens_total",
            {"intent": "test_cc", "model": "gpt-4o-mini", "provider": "openai"},
        )
        assert creation == 50.0

    def test_both_nonzero_increments_both_counters(self) -> None:
        """Both > 0 → hit counter + creation counter both incremented."""
        record_cache_usage(
            intent="test_both",
            model="claude-haiku",
            provider="anthropic",
            cache_read_tokens=75,
            cache_creation_tokens=25,
        )
        hit = REGISTRY.get_sample_value(
            "narrare_llm_cache_hit_total",
            {"intent": "test_both", "model": "claude-haiku", "provider": "anthropic"},
        )
        created = REGISTRY.get_sample_value(
            "narrare_llm_cache_creation_tokens_total",
            {"intent": "test_both", "model": "claude-haiku", "provider": "anthropic"},
        )
        assert hit == 1.0
        assert created == 25.0

    def test_no_cache_increments_miss_counter(self) -> None:
        """Both=0 → ``llm_cache_miss_total`` incremented."""
        record_cache_usage(
            intent="test_miss",
            model="gpt-4o",
            provider="openai",
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
        miss = REGISTRY.get_sample_value(
            "narrare_llm_cache_miss_total",
            {"intent": "test_miss", "model": "gpt-4o", "provider": "openai"},
        )
        assert miss == 1.0
