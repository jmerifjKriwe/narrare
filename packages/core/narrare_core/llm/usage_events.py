"""Usage-event sink seam — ADR-093.

Core emits one ``UsageEvent`` per billable LLM call at three disjoint points
(the observability capability, ``ModelRegistry.run()/stream()``, and the
OpenAI embedding provider); the app registers a DB-writing sink at startup.
The seam never raises into a run.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Protocol, cast

import structlog

from narrare_core.llm.cost_rates import get_rates_strict

if TYPE_CHECKING:
    from typing import Any
    from uuid import UUID

    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.model_config import ResolvedModelConfig

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


async def emit_registry_usage_event(
    *,
    intent: LLMIntent,
    config: ResolvedModelConfig,
    usage: Any,  # pydantic_ai RunUsage
    duration_seconds: float,
) -> None:
    """Emit one ``UsageEvent`` for an ephemeral registry run (ADR-093 D4).

    Second, disjoint emission point next to the observability capability:
    ``ModelRegistry.run()``/``stream()`` agents carry no capabilities, so
    without this emitter their calls (name generation, WS writing turns, …)
    would be invisible to cost tracking. Attribution comes from the resolved
    ``config`` (exact — no "unknown" fallbacks here); the guarded seam
    (:func:`emit_usage_event`) never raises into the product run.

    Lives here — at the seam — so ``gateway.py`` stays within its RULE-04
    file-size limit; the gateway only wires the call sites.

    FU-1 (STATS-002 hardening): event CONSTRUCTION (details coercion,
    ``estimate_cost_usd``) runs before the guarded seam call, so a
    malformed provider payload could raise into the product run. The whole
    construction + emission is guarded here — never re-raises (ADR-093 D1);
    ``emit_usage_event``'s own internal guard stays as defense in depth.
    """
    try:
        raw_details = getattr(usage, "details", None)
        if isinstance(raw_details, dict):
            details = cast("dict[str, Any]", raw_details)
        else:
            details: dict[str, Any] = {}
        cache_read = int(details.get("cache_read_input_tokens", 0) or 0)
        cache_creation = int(details.get("cache_creation_input_tokens", 0) or 0)
        tokens_in = usage.input_tokens or 0
        tokens_out = usage.output_tokens or 0
        await emit_usage_event(
            UsageEvent(
                timestamp=datetime.now(UTC),
                intent=intent.value,
                provider=config.provider_name,
                model_id=config.model_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
                duration_seconds=duration_seconds,
                cost_usd=estimate_cost_usd(
                    config.provider_name,
                    config.model_id,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cache_read_tokens=cache_read,
                    cache_creation_tokens=cache_creation,
                ),
                user_id=usage_user_id.get(),
                novel_id=usage_novel_id.get(),
            )
        )
    except Exception as exc:  # deliberate catch-all — construction must never raise either
        logger.warning(
            "usage_event_emission_failed",
            error=str(exc),
            intent=intent.value,
            provider=config.provider_name,
            model_id=config.model_id,
        )


async def emit_embedding_usage_event(
    *,
    model_name: str,
    tokens_in: int,
    duration_seconds: float,
) -> None:
    """Guarded emission for one embedding API batch call (ADR-093 surface c).

    Third disjoint emission point (ADR-093 Post-Implementation Amendment):
    ``OpenAIEmbeddingProvider.embed_texts`` is the only seam that sees
    embedding token counts (the SDK response's ``usage.total_tokens``), so it
    emits one event per API batch response. Shape per the binding spec:
    ``intent="embeddings"``, ``provider="openai"`` (the provider class is
    OpenAI-specific), input-only tokens (``prompt_tokens == total_tokens``
    for embeddings), strict cost (unknown model ⇒ ``None`` = unpriced),
    attribution from the ContextVars.

    FU-1 pattern (D-4), mirroring :func:`emit_registry_usage_event`: event
    construction — including the defensive ``int`` coercion of a possibly
    runtime-malformed ``total_tokens`` value — and emission run inside the
    never-raise catch-all; ``emit_usage_event``'s own guard stays as defense
    in depth.
    """
    try:
        tokens = int(tokens_in)
        await emit_usage_event(
            UsageEvent(
                timestamp=datetime.now(UTC),
                intent="embeddings",
                provider="openai",
                model_id=model_name,
                tokens_in=tokens,
                tokens_out=0,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                duration_seconds=duration_seconds,
                cost_usd=estimate_cost_usd(
                    "openai",
                    model_name,
                    tokens_in=tokens,
                    tokens_out=0,
                ),
                user_id=usage_user_id.get(),
                novel_id=usage_novel_id.get(),
            )
        )
    except Exception as exc:  # deliberate catch-all — construction must never raise either
        logger.warning(
            "usage_event_emission_failed",
            error=str(exc),
            intent="embeddings",
            provider="openai",
            model_id=model_name,
        )


async def emit_embedding_batch_usage(
    response: Any,
    *,
    model_name: str,
    call_started: float,
) -> None:
    """D-5 guard + per-batch emission for one embedding API batch response.

    Called by ``OpenAIEmbeddingProvider.embed_texts`` right after each
    ``client.embeddings.create`` response; *call_started* is the per-batch
    ``time.monotonic()`` timestamp captured around that single API call (the
    duration is the batch call's, not the whole ``embed_texts`` span). The
    usage read is defensive (spec D-5): a compatible gateway may omit
    ``usage`` despite the SDK type, and falsy/missing ``total_tokens`` skips
    emission with a debug log — no event, no raise. A runtime-malformed
    ``total_tokens`` value is swallowed by :func:`emit_embedding_usage_event`'s
    never-raise catch-all.

    Lives here — at the seam — so ``embedding_providers.py`` stays within its
    RULE-04 file-size limit (same placement rationale as
    :func:`emit_registry_usage_event` vs. ``gateway.py``).
    """
    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", None) if usage is not None else None
    if total_tokens:
        await emit_embedding_usage_event(
            model_name=model_name,
            tokens_in=total_tokens,
            duration_seconds=monotonic() - call_started,
        )
    else:
        logger.debug(
            "embedding_usage_skipped",
            model=model_name,
            reason="usage_missing_or_zero",
        )
