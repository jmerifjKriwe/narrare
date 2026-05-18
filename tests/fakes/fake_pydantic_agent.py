"""
Fake pydantic-ai Agent for unit testing the LLM Gateway.

Simulates the pydantic-ai Agent interface without requiring real LLM calls.
Used in gateway tests via patch.object(gateway, "_make_agent", return_value=fake_agent).

---

## Deprecation Notice (2026-05-17)

`FakePydanticAgent` is deprecated. Use pydantic-ai's built-in `TestModel` instead.

- `TestModel` stays in sync with pydantic-ai releases automatically
- `TestModel` supports all pydantic-ai Agent features (tools, result_type, etc.)
- Only use `FakePydanticAgent` for the streaming chunk test
  (`test_stream_yields_text_chunks_and_final_chunk`) until pydantic-ai's
  TestModel supports configurable streaming responses

Migration:
```python
# Before
fake_agent = FakePydanticAgent()
fake_agent.returns("text")

# After (preferred)
test_model = TestModel(custom_output_text="text")
# Use gateway_with_test_model fixture from tests/unit/core/llm/conftest.py
```

See: `tests/unit/core/llm/conftest.py` for available fixtures.
See: `docs/development/testing-standards.md` — "LLM Testing — Pydantic AI Tools"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class FakeUsage:
    """Mimics pydantic-ai's AgentRunResult.usage() return."""

    input_tokens: int = 10
    output_tokens: int = 50
    total_tokens: int = 60


@dataclass
class FakeAgentResult:
    """Mimics pydantic-ai's AgentRunResult."""

    data: str = ""
    _usage: FakeUsage = field(default_factory=FakeUsage)

    @property
    def output(self) -> str:
        """The output text — matches pydantic-ai's AgentRunResult.output."""
        return self.data

    @property
    def usage(self) -> FakeUsage:
        return self._usage

    def __str__(self) -> str:
        return self.data


class FakeStreamContext:
    """Async context manager returned by fake_agent.run_stream()."""

    def __init__(self, chunks: list[str], usage: FakeUsage | None = None) -> None:
        self._chunks = chunks
        self._usage = usage or FakeUsage()

    async def __aenter__(self) -> FakeStreamContext:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def stream_text(self, *, delta: bool = True) -> AsyncIterator[str]:
        for chunk in self._chunks:
            yield chunk

    @property
    def usage(self) -> FakeUsage:
        return self._usage


class FakePydanticAgent:
    """
    Fake pydantic-ai Agent for gateway tests.

    Usage:
        fake_agent = FakePydanticAgent()
        fake_agent.returns("Generated text", input_tokens=10, output_tokens=50)

        with patch.object(gateway, "_make_agent", return_value=fake_agent):
            result = await gateway.run(...)
    """

    def __init__(self) -> None:
        self._result: FakeAgentResult | None = None
        self._error: Exception | None = None
        self._stream_chunks: list[str] = []
        self._stream_error: Exception | None = None
        self._stream_usage: FakeUsage | None = None
        self.run_call_count = 0
        self.run_stream_call_count = 0

    # --- Setup ---

    def returns(self, text: str, *, input_tokens: int = 10, output_tokens: int = 50) -> None:
        """Configure a successful run() response."""
        self._result = FakeAgentResult(
            data=text,
            _usage=FakeUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    def raises(self, error: Exception) -> None:
        """Configure run() to raise an error."""
        self._error = error

    def returns_stream(
        self,
        chunks: list[str],
        *,
        input_tokens: int = 10,
        output_tokens: int = 50,
    ) -> None:
        """Configure a successful run_stream() response."""
        self._stream_chunks = chunks
        self._stream_usage = FakeUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    def raises_on_stream(self, error: Exception) -> None:
        """Configure run_stream() to raise an error."""
        self._stream_error = error

    # --- Protocol: pydantic-ai Agent interface ---

    async def run(self, user_prompt: str) -> FakeAgentResult:
        """Simulate Agent.run()."""
        self.run_call_count += 1
        if self._error:
            raise self._error
        if self._result is None:
            return FakeAgentResult(data="")
        return self._result

    def run_stream(self, user_prompt: str) -> FakeStreamContext | _FailingStreamContext:
        """Simulate Agent.run_stream() — returns async context manager."""
        self.run_stream_call_count += 1
        if self._stream_error:
            # The error needs to be raised inside __aenter__
            return _FailingStreamContext(self._stream_error)
        return FakeStreamContext(self._stream_chunks, self._stream_usage)


class _FailingStreamContext:
    """Async context manager that raises on __aenter__."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def __aenter__(self) -> None:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        pass
