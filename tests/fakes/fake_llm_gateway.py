"""
Fake Model Registry — implements the ModelRegistry interface for unit tests.

Supports:
- Programmable responses via returns() / returns_stream()
- Programmable errors via raises()
- Full call tracking and assertions

Migrated from FakeLLMGateway — the signature matches ModelRegistry's
run() and stream() methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic_ai.models.test import TestModel

from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.result import LLMResult, StreamChunk, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm import LLMIntent, ResolvedModelConfig


@dataclass
class RegistryCall:
    """Record of a single registry.run() or registry.stream() call."""

    intent: LLMIntent
    prompt: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    config: ResolvedModelConfig | None = None
    api_key: str | None = None
    base_url: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeModelRegistry:
    """
    Fake Model Registry for unit tests.

    Implements the same public interface as ModelRegistry (run + stream).
    Responses are queued — each call consumes the next queued response.

    Usage:
        fake = FakeModelRegistry()
        fake.returns("Hello world")
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        result = await fake.run(LLMIntent.WRITE, "test prompt", config)
        assert result == "Hello world"
    """

    def __init__(self) -> None:
        self._responses: list[str] = []
        self._stream_responses: list[list[str]] = []
        self._errors: list[Exception] = []
        self._call_queue: list[str] = []  # "response" | "stream" | "error"
        self.calls: list[RegistryCall] = []
        self.prepare_calls: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Setup methods (configure in test setup)
    # ------------------------------------------------------------------

    def returns(self, text: str) -> None:
        """Queue a successful response for the next run() call."""
        self._responses.append(text)
        self._call_queue.append("response")

    def returns_stream(self, chunks: list[str]) -> None:
        """Queue a successful streaming response for the next stream() call."""
        self._stream_responses.append(chunks)
        self._call_queue.append("stream")

    def raises(self, error: Exception) -> None:
        """Queue an error for the next run() or stream() call."""
        self._errors.append(error)
        self._call_queue.append("error")

    # ------------------------------------------------------------------
    # Protocol implementation (same signature as ModelRegistry)
    # ------------------------------------------------------------------

    async def run(
        self,
        intent: LLMIntent,
        prompt: str,
        config: ResolvedModelConfig | None = None,
        *,
        system_prompt: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute a fake non-streaming LLM call."""
        self.calls.append(
            RegistryCall(
                intent=intent,
                prompt=prompt,
                system_prompt=system_prompt,
                config=config,
                api_key=api_key,
                base_url=base_url,
                kwargs=kwargs,
            )
        )

        if not self._call_queue:
            return ""

        next_type = self._call_queue.pop(0)
        if next_type == "error":
            raise self._errors.pop(0)
        if next_type == "response":
            return self._responses.pop(0)
        # If a stream was queued but run() was called, return empty
        return ""

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
            RegistryCall(
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

    async def prepare(
        self,
        config: ResolvedModelConfig | None = None,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        """Fake single assembly point — returns a canned coherent triple.

        Records the call in ``prepare_calls`` for wiring assertions.  The
        canned ``model_settings`` are ``None``; tests that need the real
        settings composition should mirror ``ModelRegistry.prepare`` in
        their domain fake instead.
        """
        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
            }
        )
        return PreparedModelCall(
            model=TestModel(),
            model_settings=None,
            usage_limits=usage_limits,
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

    def last_call(self) -> RegistryCall:
        """Return the last call record."""
        if not self.calls:
            raise AssertionError("No calls recorded")
        return self.calls[-1]


# ---------------------------------------------------------------------------
# Backward compatibility — FakeLLMGateway delegates to FakeModelRegistry
# ---------------------------------------------------------------------------


@dataclass
class GatewayCall:
    """Record of a single gateway.run() call (backward compat)."""

    intent: LLMIntent
    system_prompt: str
    user_prompt: str
    config: ResolvedModelConfig | None = None
    api_key: str | None = None
    base_url: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeLLMGateway:
    """
    Backward-compatible fake gateway for tests that haven't migrated yet.

    Delegates to FakeModelRegistry internally but exposes the old
    LLMGateway-style keyword-only interface (run/stream with *,
    system_prompt, user_prompt, config kwargs).

    Prefer FakeModelRegistry for new tests.
    """

    def __init__(self) -> None:
        self._registry = FakeModelRegistry()
        self.calls: list[GatewayCall] = []

    def returns(self, text: str, *, model: str = "fake-model") -> None:
        self._registry.returns(text)

    def returns_stream(self, chunks: list[str], *, model: str = "fake-model") -> None:
        self._registry.returns_stream(chunks)

    def raises(self, error: Exception) -> None:
        self._registry.raises(error)

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
        result_text = await self._registry.run(
            intent,
            prompt=user_prompt,
            config=config,
            system_prompt=system_prompt,
            api_key=api_key,
            base_url=base_url,
        )
        return LLMResult(
            text=result_text,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60),
            model="fake-model",
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
        async for chunk in self._registry.stream(
            intent=intent,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config,
            api_key=api_key,
            base_url=base_url,
        ):
            yield chunk

    async def prepare(
        self,
        config: ResolvedModelConfig | None = None,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        """Delegates to the inner ``FakeModelRegistry.prepare``."""
        return await self._registry.prepare(
            config,
            intent=intent,
            usage_limits=usage_limits,
            api_key=api_key,
            base_url=base_url,
        )

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def assert_called_with_intent(self, intent: LLMIntent) -> None:
        for call in self.calls:
            if call.intent == intent:
                return
        raise AssertionError(
            f"Expected call with intent={intent.value}, "
            f"but calls were: {[c.intent.value for c in self.calls]}"
        )

    def assert_called_once(self) -> None:
        if len(self.calls) != 1:
            raise AssertionError(f"Expected 1 call, got {len(self.calls)}")

    def assert_not_called(self) -> None:
        if self.calls:
            raise AssertionError(f"Expected 0 calls, got {len(self.calls)}")

    def last_call(self) -> GatewayCall:
        if not self.calls:
            raise AssertionError("No calls recorded")
        return self.calls[-1]
