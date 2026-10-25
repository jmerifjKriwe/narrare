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
        self.settings = settings

    @classmethod
    def from_environment(cls) -> OpenAICompatibleProvider:
        """The catalog's factory: configuration comes from the environment."""
        return cls(OpenAISettings.from_environment())

    def describe(self) -> str:
        return (
            f"openai-compatible model={self.settings.model or '(unset)'}"
            f" base_url={self.settings.base_url}"
        )

    def configuration_problems(self) -> list[str]:
        return self.settings.problems()

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
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
    return line.startswith("data: ") and line[6:].strip() == DONE_MARKER


def _event(line: str) -> CompletionEvent | None:
    """The event one SSE line carries, or None when it carries none.

    Keep-alive comments, the role frame and the finish frame are data lines
    without content; only text and usage reach the caller.
    """
    if not line.startswith("data: "):
        return None
    frame = json.loads(line[6:].strip())
    usage = frame.get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValueError("reported usage must be an object")
        reported_usage = cast("dict[str, object]", usage)
        prompt_tokens = reported_usage.get("prompt_tokens")
        completion_tokens = reported_usage.get("completion_tokens")
        if (
            type(prompt_tokens) is not int
            or type(completion_tokens) is not int
            or prompt_tokens < 0
            or completion_tokens < 0
        ):
            raise ValueError("reported usage must contain non-negative integer token counts")
        return Usage(input_tokens=prompt_tokens, output_tokens=completion_tokens)
    choices = frame.get("choices")
    if choices:
        content = choices[0].get("delta", {}).get("content")
        if isinstance(content, str):
            return Delta(text=content)
    return None
