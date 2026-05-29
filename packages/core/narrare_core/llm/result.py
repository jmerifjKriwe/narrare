"""LLM call result types."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage statistics from an LLM call.

    When ``provider`` and ``model`` are populated, ``cost_estimate_usd``
    uses per-model pricing from models.dev. Otherwise falls back to a
    blended rate of $3 per 1M tokens.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str = ""
    model: str = ""
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def cost_estimate_usd(self) -> float:
        """
        Cost estimate in USD based on per-model rates from models.dev.

        Uses per-model pricing when ``provider`` and ``model`` are set,
        with fallback to provider-level defaults and finally a blended
        rate of $3 per 1M tokens.

        Returns:
            Estimated cost in USD (not for billing — rough comparison only).
        """
        if self.provider and self.model:
            # Lazy import to avoid circular dependency at module level
            from narrare_core.llm.cost_rates import get_rates

            rates = get_rates(self.provider, self.model)
            if rates is not None:
                input_cost = self.prompt_tokens * rates["input"] / 1_000_000
                output_cost = self.completion_tokens * rates["output"] / 1_000_000
                return input_cost + output_cost

        # Fallback: blended rate of $3 per 1M tokens
        return self.total_tokens * 0.000003


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Result from a non-streaming LLM call."""

    text: str
    usage: TokenUsage
    model: str
    intent: str
    # Raw provider response metadata (for debugging)
    metadata: dict[str, object] = field(default_factory=dict[str, object])

    @property
    def ok(self) -> bool:
        return bool(self.text)


@dataclass(slots=True)
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    text: str
    is_final: bool = False
    usage: TokenUsage | None = None  # only on final chunk
    context_meta: dict[str, Any] | None = None  # CR-07: context metadata for first chunk


# Type alias for streaming responses
LLMStream = AsyncIterator[StreamChunk]
