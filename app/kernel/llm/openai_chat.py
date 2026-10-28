"""The openai-chat adapter: one streamed completion over the official SDK.

One shape covers OpenAI, OpenRouter, DeepSeek, Groq and local servers (Ollama,
llama.cpp, vLLM): they differ in base URL, model and key, not in protocol. A
vendor with a different protocol gets its own module next to this one.

The refusal path stays unhandled on purpose: a 401 or a 500 raises exactly
once — the client is built with ``max_retries=0``, as the hand-rolled client
before it — the router turns the raise into the stream's error frame, and the
UI shows a message instead of an answer that quietly stopped.

Wire semantics are the ones the deleted hand-rolled parser had: delta frames
in arrival order, one Usage when the server reports it (requested always —
without ``stream_options.include_usage`` the stream carries no token counts,
and the audit would have nothing to record), and exactly one terminal DONE
whether or not the server sent its own ``[DONE]`` line. Errors propagate
without DONE.
"""

from collections.abc import AsyncIterator, Mapping  # noqa: TC003
from os import environ
from typing import TYPE_CHECKING, cast

from openai import AsyncOpenAI, Omit, Timeout, omit

from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta, Usage
from app.kernel.vendor import needs_api_key

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam
    from openai.types.chat.completion_create_params import ResponseFormat

DEFAULT_BASE_URL = "https://api.openai.com/v1"

TIMEOUT = Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
"""Reading waits: a completion streams for as long as the model takes.

``Timeout`` is the SDK's own re-export of its HTTP layer's type — the same
object it hands its client — so the split-second connect bound and the patient
read bound of the hand-rolled era both survive the swap, and the module stays
inside the SDK's public surface.
"""

_NO_KEY = "narrare-no-key-configured"
"""The placeholder a keyless endpoint needs: the SDK refuses an empty api_key
at construction because it cannot know this endpoint does not want one."""

_KEYLESS_HEADERS: Mapping[str, Omit] = {"Authorization": Omit()}
"""Per-request headers that drop the placeholder's Authorization header."""


def client_for(
    base_url: str, api_key: str, *, timeout: float | Timeout | None = None
) -> AsyncOpenAI:
    """One SDK client aimed at the endpoint, with the adapter's two invariants.

    ``max_retries=0`` preserves the raise-once error semantics, and a missing
    timeout keeps the reading-waits default of the hand-rolled era.
    """
    return AsyncOpenAI(
        base_url=base_url,
        api_key=api_key or _NO_KEY,
        max_retries=0,
        timeout=timeout,
    )


def keyless_headers(api_key: str) -> Mapping[str, Omit] | None:
    """The extra headers one request needs so a keyless endpoint stays keyless.

    ``None`` when a key is configured: the client's own Authorization header
    is correct. Without a key the placeholder would send ``Bearer
    narrare-no-key-configured``; the Omit drops the header instead, the way
    the hand-rolled client simply sent none.
    """
    return None if api_key else _KEYLESS_HEADERS


class OpenAIChatProvider:
    """Streams a chat completion from any OpenAI-shaped endpoint, over the SDK."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        request_timeout: float | None = None,
        temperature_default: float | None = None,
    ) -> None:
        """Use the supplied endpoint, model, and API key for subsequent completions.

        ``request_timeout`` is the SDK timeout for every call; ``temperature_default``
        applies only to requests that set no temperature of their own.
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.request_timeout = request_timeout
        self.temperature_default = temperature_default

    @classmethod
    def from_environment(cls) -> OpenAIChatProvider:
        """The environment tier's factory: ``NARRE_LLM_*`` decides, semantics unchanged."""
        return cls(
            base_url=environ.get("NARRE_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=environ.get("NARRE_LLM_MODEL", ""),
            api_key=environ.get("NARRE_LLM_API_KEY", ""),
        )

    def describe(self) -> str:
        """Describe the configured model and endpoint without exposing the API key."""
        return f"openai-chat model={self.model or '(unset)'} base_url={self.base_url}"

    def configuration_problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready.

        The names are the environment tier's, whose provider this factory
        builds; a half-configured *profile* is the settings gate's to refuse
        with 422s naming its fields, not this method's to log at startup.
        """
        problems: list[str] = []
        if not self.model:
            problems.append("NARRE_LLM_MODEL is not set")
        if not self.api_key and needs_api_key(self.base_url):
            problems.append("NARRE_LLM_API_KEY is not set (a remote endpoint needs one)")
        return problems

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Stream text and reported usage, then DONE on normal completion.

        Messages retain their roles; optional completion settings travel only
        when set — the request's temperature over the configured default, and
        neither when both are absent. Usage is yielded only when the server
        reports it. Both the wire's ``[DONE]`` marker and a normal EOF end
        with one DONE. Transport and response-parsing errors (the SDK's own
        validation included) propagate without yielding DONE.
        """
        temperature = (
            request.temperature if request.temperature is not None else self.temperature_default
        )
        response_format: ResponseFormat | None = None
        if request.response_schema is not None:
            # The dict is the wire shape the hand-rolled client sent; the
            # SDK's param type is a TypedDict spelling of the same keys.
            response_format = cast(
                "ResponseFormat",
                {
                    "type": "json_schema",
                    "json_schema": {"name": "answer", "schema": request.response_schema},
                },
            )
        client = client_for(
            self.base_url,
            self.api_key,
            timeout=self.request_timeout if self.request_timeout is not None else TIMEOUT,
        )
        try:
            completion = await client.chat.completions.create(
                model=self.model,
                # The wire carries the roles verbatim (contract: "system" |
                # "user"); the cast states that contract over the SDK's literals.
                messages=cast(
                    "list[ChatCompletionMessageParam]",
                    [
                        {"role": message.role, "content": message.content}
                        for message in request.messages
                    ],
                ),
                # Always: without it the stream carries no token counts, and
                # the audit (plan §3.4) would have nothing to record.
                stream=True,
                stream_options={"include_usage": True},
                temperature=temperature if temperature is not None else omit,
                max_tokens=request.max_tokens if request.max_tokens is not None else omit,
                response_format=response_format if response_format is not None else omit,
                extra_headers=keyless_headers(self.api_key),
            )
            async for chunk in completion:
                if chunk.usage is not None:
                    # A usage frame yields its counts; the same frame's text
                    # deltas still follow below — both events yield, neither
                    # takes precedence. The counts arrive validated by the SDK.
                    yield Usage(
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                    )
                for choice in chunk.choices:
                    content = choice.delta.content
                    if isinstance(content, str):
                        yield Delta(text=content)
        finally:
            await client.close()
        # Exactly one terminal event, whether or not the server sent its own
        # [DONE] line — local servers close the stream without one.
        yield DONE
