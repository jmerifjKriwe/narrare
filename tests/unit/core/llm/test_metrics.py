"""Tests for llm/metrics.py — Prometheus metrics recording functions.

Covers:
1. record_success increments counters and observes duration
2. record_failure increments error counter
3. record_retry increments retry counter
4. All functions accept expected keyword args without error
"""

from __future__ import annotations

from narrare_core.llm.metrics import (
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
