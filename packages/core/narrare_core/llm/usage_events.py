"""Usage-event sink seam — ADR-093.

Core emits one ``UsageEvent`` per billable LLM call at two disjoint points
(the observability capability and ``ModelRegistry.run()/stream()``); the app
registers a DB-writing sink at startup. The seam never raises into a run.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import structlog

from narrare_core.llm.cost_rates import get_rates_strict

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

logger = structlog.get_logger(__name__)

usage_user_id: ContextVar[UUID | None] = ContextVar("usage_user_id", default=None)
usage_novel_id: ContextVar[UUID | None] = ContextVar("usage_novel_id", default=None)


def set_usage_context(*, user_id: UUID | None, novel_id: UUID | None) -> None:
    """Set attribution ContextVars (API middleware / WS bootstrap call this)."""
    usage_user_id.set(user_id)
    usage_novel_id.set(novel_id)


@dataclass(frozen=True)
class UsageEvent:
    timestamp: datetime
    intent: str
    provider: str
    model_id: str
    tokens_in: int
    tokens_out: int
    cache_read_tokens: int
    cache_creation_tokens: int
    duration_seconds: float
    cost_usd: float | None
    user_id: UUID | None
    novel_id: UUID | None


class UsageEventSink(Protocol):
    async def record(self, event: UsageEvent) -> None: ...


_sink: UsageEventSink | None = None


def set_usage_event_sink(sink: UsageEventSink | None) -> None:
    global _sink
    _sink = sink


def get_usage_event_sink() -> UsageEventSink | None:
    return _sink


async def emit_usage_event(event: UsageEvent) -> None:
    """Guarded emission — never raises into the product run (ADR-093 D1)."""
    sink = _sink
    if sink is None:
        return
    try:
        await sink.record(event)
    except Exception as exc:  # deliberate catch-all — seam must never raise
        logger.warning("usage_event_sink_failed", error=str(exc))


def estimate_cost_usd(
    provider: str,
    model_id: str,
    *,
    tokens_in: int,
    tokens_out: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float | None:
    """Strict write-time cost. None = model not exactly priced (unpriced)."""
    rates: dict[str, float] | None = get_rates_strict(provider, model_id)
    if rates is None:
        return None
    non_cached_in = max(tokens_in - cache_read_tokens, 0)
    cost = (
        non_cached_in / 1e6 * rates.get("input", 0.0)
        + cache_read_tokens / 1e6 * rates.get("cache_read", rates.get("input", 0.0))
        + cache_creation_tokens / 1e6 * rates.get("cache_write", rates.get("input", 0.0))
        + tokens_out / 1e6 * rates.get("output", 0.0)
    )
    return round(cost, 6)
