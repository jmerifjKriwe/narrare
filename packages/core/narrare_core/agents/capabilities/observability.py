"""NarrareObservability — Standard-Observability-Capability für alle Agents.

Trackt LLM-Calls (Success/Failure/Dauer/Token) via AbstractCapability-Hooks.
Ersetzt die manuellen record_success/record_failure-Aufrufe im Legacy-Gateway.

Siehe ADR-015 Phase 1.2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from pydantic_ai.capabilities import AbstractCapability

from narrare_core.llm.metrics import record_cache_usage, record_failure, record_success
from narrare_core.llm.result import TokenUsage
from narrare_core.llm.usage_events import (
    UsageEvent,
    emit_usage_event,
    estimate_cost_usd,
    usage_novel_id,
    usage_user_id,
)

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from pydantic_ai.messages import ModelResponse
    from pydantic_ai.models import ModelRequestContext


@dataclass
class NarrareObservability(AbstractCapability):
    """Standard-Observability-Capability für alle Narrare-Agents.

    Hooks in den Model-Request-Lifecycle:
    - ``before_model_request``: Startzeit erfassen
    - ``after_model_request``: Success loggen (Dauer + Tokens)
    - ``on_model_request_error``: Failure loggen
    """

    # Template state — set once on the agent's capability instance
    # (class-identity intent, ADR-093) and preserved into the per-run
    # copy by ``for_run``.
    intent: str = ""

    # Per-run State (wird in for_run frisch initialisiert)
    _start_time: float = 0.0
    _model_id: str = ""
    _provider_name: str = ""

    async def for_run(self, ctx: RunContext[Any]) -> NarrareObservability:
        """Frische Instanz pro Run — isoliert Per-Run-State.

        Template state (``intent``) is preserved into the per-run copy;
        per-run state (``_start_time`` etc.) starts fresh.

        Versucht Observability-Kontext aus ``ctx.deps`` zu extrahieren.
        Unterstützt aktuell das ``WritingDeps``-Pattern (``model_config``
        mit ``provider_name`` + ``model_id``). Für andere Deps-Types
        fallen die Werte auf ``"unknown"`` zurück (bisheriges Verhalten).
        """
        obs = NarrareObservability(intent=self.intent)

        deps = ctx.deps
        if deps is not None:
            # WritingDeps / agents mit model_config-Attribut
            model_config = getattr(deps, "model_config", None)
            if model_config is not None:
                provider = getattr(model_config, "provider_name", None)
                model_id = getattr(model_config, "model_id", None)
                if provider:
                    obs._provider_name = provider
                if model_id:
                    obs._model_id = model_id

        return obs

    async def before_model_request(
        self,
        ctx: RunContext[Any],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        """Startzeit erfassen."""
        self._start_time = time.monotonic()
        return request_context

    async def after_model_request(
        self,
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        """Success loggen: Dauer, Token-Verbrauch."""
        elapsed = time.monotonic() - self._start_time

        # Extract cache statistics from usage details
        raw_details = getattr(ctx.usage, "details", None)
        if isinstance(raw_details, dict):
            details = cast("dict[str, Any]", raw_details)
        else:
            details: dict[str, Any] = {}
        cache_read = int(details.get("cache_read_input_tokens", 0) or 0)
        cache_creation = int(details.get("cache_creation_input_tokens", 0) or 0)

        # Aus ctx.usage die Token extrahieren
        # ctx.usage is always populated (RunUsage, not Optional)
        token_usage = TokenUsage(
            prompt_tokens=ctx.usage.input_tokens or 0,
            completion_tokens=ctx.usage.output_tokens or 0,
            total_tokens=ctx.usage.total_tokens or 0,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )

        record_success(
            intent=self.intent or "unknown",
            model=self._model_id or "unknown",
            provider=self._provider_name or "unknown",
            usage=token_usage,
            duration_seconds=elapsed,
        )

        # Record cache metrics
        if cache_read > 0 or cache_creation > 0:
            record_cache_usage(
                intent=self.intent or "unknown",
                model=self._model_id or "unknown",
                provider=self._provider_name or "unknown",
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
            )

        # Emit one billable UsageEvent per model request (ADR-093 decision 4).
        await emit_usage_event(
            UsageEvent(
                timestamp=datetime.now(UTC),
                intent=self.intent or "unknown",
                provider=self._provider_name or "unknown",
                model_id=self._model_id or "unknown",
                tokens_in=token_usage.prompt_tokens,
                tokens_out=token_usage.completion_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
                duration_seconds=elapsed,
                cost_usd=estimate_cost_usd(
                    self._provider_name or "unknown",
                    self._model_id or "unknown",
                    tokens_in=token_usage.prompt_tokens,
                    tokens_out=token_usage.completion_tokens,
                    cache_read_tokens=cache_read,
                    cache_creation_tokens=cache_creation,
                ),
                user_id=usage_user_id.get(),
                novel_id=usage_novel_id.get(),
            )
        )

        return response

    async def on_model_request_error(
        self,
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        error: Exception,
    ) -> ModelResponse:
        """Failure loggen bei Fehlschlag."""
        elapsed = time.monotonic() - self._start_time
        error_type = type(error).__name__

        record_failure(
            intent=self.intent or "unknown",
            model=self._model_id or "unknown",
            provider=self._provider_name or "unknown",
            error_type=error_type,
            duration_seconds=elapsed,
        )
        raise error  # propagate
