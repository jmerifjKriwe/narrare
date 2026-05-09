"""LLM call result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage statistics from an LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @property
    def cost_estimate_usd(self) -> float:
        """
        Very rough cost estimate in USD.
        Actual cost depends on provider and model.
        Use this only for relative comparisons, not billing.
        """
        # Approximate: $3 per 1M tokens (blended input/output)
        return self.total_tokens * 0.000003


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Result from a non-streaming LLM call."""

    text: str
    usage: TokenUsage
    model: str
    intent: str
    # Raw provider response metadata (for debugging)
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.text)


@dataclass(slots=True)
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    text: str
    is_final: bool = False
    usage: TokenUsage | None = None  # only on final chunk


# Type alias for streaming responses
LLMStream = AsyncIterator[StreamChunk]
