"""
Fake LLM Gateway — implements the LLMGateway interface for unit tests.

Supports:
- Programmable responses via returns() / returns_stream()
- Programmable errors via raises()
- Full call tracking and assertions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from narrare_core.llm.result import LLMResult, StreamChunk, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig


@dataclass
class GatewayCall:
    """Record of a single gateway.run() call."""

    intent: LLMIntent
    system_prompt: str
    user_prompt: str
    config: ResolvedModelConfig | None = None
    api_key: str | None = None
    base_url: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeLLMGateway:
    """
    Fake LLM gateway for unit tests.

    Implements the same public interface as LLMGateway (run + stream).
    Responses are queued — each call consumes the next queued response.

    Usage:
        fake = FakeLLMGateway()
        fake.returns("Hello world")
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        result = await fake.run(intent=LLMIntent.WRITE, config=config, ...)
        assert result.text == "Hello world"
    """

    def __init__(self) -> None:
        self._responses: list[LLMResult] = []
        self._stream_responses: list[list[str]] = []
        self._errors: list[Exception] = []
        self._call_queue: list[str] = []  # "response" | "stream" | "error"
        self.calls: list[GatewayCall] = []

    # ------------------------------------------------------------------
    # Setup methods (configure in test setup)
    # ------------------------------------------------------------------

    def returns(self, text: str, *, model: str = "fake-model") -> None:
        """Queue a successful response for the next run() call."""
        self._responses.append(
            LLMResult(
                text=text,
                usage=TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60),
                model=model,
                intent="fake",
            )
        )
        self._call_queue.append("response")

    def returns_stream(self, chunks: list[str], *, model: str = "fake-model") -> None:
        """Queue a successful streaming response for the next stream() call."""
        self._stream_responses.append(chunks)
        self._call_queue.append("stream")

    def raises(self, error: Exception) -> None:
        """Queue an error for the next run() or stream() call."""
        self._errors.append(error)
        self._call_queue.append("error")

    # ------------------------------------------------------------------
    # Protocol implementation (same signature as LLMGateway)
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Execute a fake non-streaming LLM call."""
        self.calls.append(
            GatewayCall(
                intent=intent,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                config=config,
                api_key=api_key,
                base_url=base_url,
                kwargs=kwargs,
            )
        )

        if not self._call_queue:
            return LLMResult(
                text="",
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                model="fake",
                intent=intent.value,
            )

        next_type = self._call_queue.pop(0)
        if next_type == "error":
            raise self._errors.pop(0)
        if next_type == "response":
            result = self._responses.pop(0)
            # Update intent to match what was requested
            return LLMResult(
                text=result.text,
                usage=result.usage,
                model=result.model,
                intent=intent.value,
            )
        # If a stream was queued but run() was called, return empty
        return LLMResult(
            text="",
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            model="fake",
            intent=intent.value,
        )

    async def stream(
        self,
        *,
        intent: LLMIntent,
        system_prompt: str,
        user_prompt: str,
        config: ResolvedModelConfig | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Execute a fake streaming LLM call."""
        self.calls.append(
            GatewayCall(
                intent=intent,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                config=config,
                api_key=api_key,
                base_url=base_url,
                kwargs=kwargs,
            )
        )

        if not self._call_queue:
            return

        next_type = self._call_queue.pop(0)
        if next_type == "error":
            raise self._errors.pop(0)

        if next_type == "stream" and self._stream_responses:
            chunks = self._stream_responses.pop(0)
            for chunk in chunks:
                yield StreamChunk(text=chunk)
            yield StreamChunk(
                text="",
                is_final=True,
                usage=TokenUsage(
                    prompt_tokens=10,
                    completion_tokens=len("".join(chunks).split()) * 2,
                    total_tokens=10 + len("".join(chunks).split()) * 2,
                ),
            )

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Total number of run() or stream() calls."""
        return len(self.calls)

    def assert_called_with_intent(self, intent: LLMIntent) -> None:
        """Assert that at least one call was made with the given intent."""
        for call in self.calls:
            if call.intent == intent:
                return
        raise AssertionError(
            f"Expected call with intent={intent.value}, "
            f"but calls were: {[c.intent.value for c in self.calls]}"
        )

    def assert_called_once(self) -> None:
        """Assert exactly one call was made."""
        if len(self.calls) != 1:
            raise AssertionError(f"Expected 1 call, got {len(self.calls)}")

    def assert_not_called(self) -> None:
        """Assert no calls were made."""
        if self.calls:
            raise AssertionError(f"Expected 0 calls, got {len(self.calls)}")

    def last_call(self) -> GatewayCall:
        """Return the last call record."""
        if not self.calls:
            raise AssertionError("No calls recorded")
        return self.calls[-1]
