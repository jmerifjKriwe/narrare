"""
LLM cost tracking and telemetry hooks.

All metrics are recorded here. The gateway calls these functions
after every LLM call (successful or failed).

Prometheus metrics are exposed at /metrics by the API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram

if TYPE_CHECKING:
    from narrare_core.llm.result import TokenUsage

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

llm_requests_total = Counter(
    "narrare_llm_requests_total",
    "Total LLM requests",
    ["intent", "model", "provider", "status"],
)

llm_tokens_total = Counter(
    "narrare_llm_tokens_total",
    "Total tokens used",
    ["intent", "model", "token_type"],  # token_type: prompt | completion
)

llm_request_duration_seconds = Histogram(
    "narrare_llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["intent", "model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

llm_cost_usd_total = Counter(
    "narrare_llm_cost_usd_total",
    "Estimated LLM cost in USD (approximate)",
    ["intent", "model"],
)

llm_retry_attempts_total = Counter(
    "narrare_llm_retry_attempts_total",
    "Total LLM retry attempts",
    ["intent", "error_type"],
)


# ---------------------------------------------------------------------------
# Recording functions — called by the gateway
# ---------------------------------------------------------------------------


def record_success(
    *,
    intent: str,
    model: str,
    provider: str,
    usage: TokenUsage,
    duration_seconds: float,
) -> None:
    """Record a successful LLM call."""
    llm_requests_total.labels(intent=intent, model=model, provider=provider, status="success").inc()

    llm_tokens_total.labels(  # nosec B105 B106
        intent=intent, model=model, token_type="prompt"
    ).inc(usage.prompt_tokens)

    llm_tokens_total.labels(  # nosec B105 B106
        intent=intent, model=model, token_type="completion"
    ).inc(usage.completion_tokens)

    llm_request_duration_seconds.labels(intent=intent, model=model).observe(duration_seconds)

    llm_cost_usd_total.labels(intent=intent, model=model).inc(usage.cost_estimate_usd)


def record_failure(
    *,
    intent: str,
    model: str,
    provider: str,
    error_type: str,
    duration_seconds: float,
) -> None:
    """Record a failed LLM call."""
    llm_requests_total.labels(intent=intent, model=model, provider=provider, status="error").inc()

    llm_request_duration_seconds.labels(intent=intent, model=model).observe(duration_seconds)


def record_retry(*, intent: str, error_type: str) -> None:
    """Record a retry attempt."""
    llm_retry_attempts_total.labels(intent=intent, error_type=error_type).inc()
