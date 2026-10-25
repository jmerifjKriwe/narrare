"""Fetch strategy for the OpenAI-shaped chat completions API, streamed as SSE.

One shape covers OpenAI, OpenRouter, DeepSeek, Groq and local servers (Ollama,
llama.cpp, vLLM): they differ in base URL, model and key, not in protocol. A
vendor with a different protocol gets its own module next to this one.

The refusal path stays unhandled on purpose: a 401 or a 500 raises, the router
turns it into the stream's error frame, and the UI shows a message instead of an
answer that quietly stopped.
"""

import json
from collections.abc import AsyncIterator  # noqa: TC003
from dataclasses import dataclass
from os import environ
from typing import cast

import httpx

from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta, Usage
from app.kernel.vendor import needs_api_key

DEFAULT_BASE_URL = "https://api.openai.com/v1"

TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
"""Reading waits: a completion streams for as long as the model takes."""

DONE_MARKER = "[DONE]"
"""The wire's own terminal line. Local servers omit it, so the protocol's DONE
does not depend on it."""


@dataclass(frozen=True)
class OpenAISettings:
    """Where to send the prompt. Read from the environment, or passed in tests."""

    base_url: str
    model: str
    api_key: str

    @classmethod
    def from_environment(cls) -> OpenAISettings:
        """Read provider settings from NARRE_LLM variables and remove trailing base URL slashes."""
        return cls(
            base_url=environ.get("NARRE_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=environ.get("NARRE_LLM_MODEL", ""),
            api_key=environ.get("NARRE_LLM_API_KEY", ""),
        )

    def problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready."""
        problems: list[str] = []
        if not self.model:
            problems.append("NARRE_LLM_MODEL is not set")
        if not self.api_key and needs_api_key(self.base_url):
            problems.append("NARRE_LLM_API_KEY is not set (a remote endpoint needs one)")
        return problems


class OpenAICompatibleProvider:
    """Streams a chat completion from any OpenAI-shaped endpoint."""

    def __init__(self, settings: OpenAISettings) -> None:
        """Use the supplied endpoint, model, and API key for subsequent completions."""
        self.settings = settings

    @classmethod
    def from_environment(cls) -> OpenAICompatibleProvider:
        """The catalog's factory: configuration comes from the environment."""
        return cls(OpenAISettings.from_environment())

    def describe(self) -> str:
        """Describe the configured model and endpoint without exposing the API key."""
        return (
            f"openai-compatible model={self.settings.model or '(unset)'}"
            f" base_url={self.settings.base_url}"
        )

    def configuration_problems(self) -> list[str]:
        """Return missing configuration reported by the provider settings."""
        return self.settings.problems()

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Stream text and reported usage, then DONE on normal completion.

        Messages retain their roles; optional completion settings are sent only
        when set. Usage is requested but is yielded only when the server reports
        it. Both the wire's [DONE] marker and a normal EOF end with one DONE.
        HTTP, transport, JSON-decoding, and frame-parsing errors propagate
        without yielding DONE; malformed reported usage raises ValueError.
        """
        headers = (
            {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}
        )
        body: dict[str, object] = {
            "model": self.settings.model,
            "stream": True,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            # Always: without it the stream carries no token counts, and the
            # audit (plan §3.4) would have nothing to record.
            "stream_options": {"include_usage": True},
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": request.response_schema},
            }
        async with (
            httpx.AsyncClient(timeout=TIMEOUT) as client,
            client.stream(
                "POST",
                f"{self.settings.base_url}/chat/completions",
                json=body,
                headers=headers,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if _is_done(line):
                    break
                event = _event(line)
                if event is not None:
                    yield event
        # Exactly one terminal event, whether or not the server sent its own
        # [DONE] line — local servers close the stream without one.
        yield DONE


def _is_done(line: str) -> bool:
    """Recognize an SSE data line containing the terminal wire marker."""
    return line.startswith("data: ") and line[6:].strip() == DONE_MARKER


def _usage(usage: object) -> Usage:
    """The reported token counts, or a loud refusal naming the broken field.

    ``usage: null`` is handled by the caller (absent, valid); a present object
    fails when a count is missing, not an integer, a boolean (``type`` excludes
    the int subclass) or negative. The message carries the field and the
    received value: the generic sentence landed verbatim in ``llm_calls.error``
    and told an operator nothing about which vendor field drifted.
    """
    if not isinstance(usage, dict):
        raise ValueError(f"reported usage is not an object: {usage!r}")
    # JSON object keys are strings by contract (RFC 8259); the cast states
    # that contract on the type level — every value is still checked below.
    report = cast("dict[str, object]", usage)
    counts: list[int] = []
    for field in ("prompt_tokens", "completion_tokens"):
        if field not in report:
            # A dropped field and an explicit null are different vendor bugs;
            # the row's error text should tell an operator which one arrived.
            raise ValueError(f"reported usage is missing {field}")
        value = report.get(field)
        if type(value) is not int or value < 0:
            raise ValueError(
                f"reported usage field {field} is not a non-negative integer count: {value!r}"
            )
        counts.append(value)
    input_tokens, output_tokens = counts
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def _event(line: str) -> CompletionEvent | None:
    """The event one SSE line carries, or None when it carries none.

    Comments and frames without text or usage return None. Reported usage
    takes precedence over text in the same frame and must contain non-negative
    integer token counts (booleans are rejected), or ValueError is raised.
    Invalid JSON raises JSONDecodeError; other malformed frame structures may
    propagate AttributeError, KeyError, or TypeError. The terminal wire marker
    must be handled by the caller before parsing.
    """
    if not line.startswith("data: "):
        return None
    frame = json.loads(line[6:].strip())
    usage = frame.get("usage")
    if usage is not None:
        return _usage(usage)
    choices = frame.get("choices")
    if choices:
        content = choices[0].get("delta", {}).get("content")
        if isinstance(content, str):
            return Delta(text=content)
    return None
