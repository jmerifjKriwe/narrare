"""The anthropic adapter: one streamed completion over the Messages wire.

The protocol is one POST with its own headers (``x-api-key``,
``anthropic-version``), system turns hoisted out of the message list, and a
mandatory ``max_tokens`` — one request, no SDK between it and the socket. The
openai-chat adapter's invariants carry over unchanged: one raise (``httpx``
gets no retry count to spend), delta pieces in arrival order, one Usage from
the frames the server reports, and exactly one terminal DONE whether or not
the stream sent its own ``message_stop``. Errors propagate without DONE.

The refusal path maps the two failures a user can act on into the contract's
typed vocabulary — a 404 (or an in-stream ``not_found_error``) names the
model, a 401 (or ``authentication_error``) names the credential, the same two
:class:`app.kernel.llm.contract.ModelNotFoundError` and
:class:`app.kernel.llm.contract.ProviderAuthError` the openai-chat adapter
raises from the SDK's exceptions. Anything else stays an unclassified
exception; the error frames (plan Task 8) are where codes become messages.
"""

import json
from collections.abc import AsyncIterator  # noqa: TC003
from typing import Any, cast

import httpx

from app.kernel.llm.contract import (
    DONE,
    CompletionEvent,
    CompletionRequest,
    Delta,
    ModelNotFoundError,
    ProviderAuthError,
    Usage,
)

ANTHROPIC_VERSION = "2023-06-01"
"""The ``anthropic-version`` header the Messages wire expects on every request."""

STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"
"""The beta feature a ``response_schema`` request needs, sent as
``anthropic-beta`` beside the ``output_format`` body field it unlocks."""

DEFAULT_MAX_TOKENS = 4096
"""The body's ``max_tokens`` when the request sets none: the wire has no
default and refuses the request without one."""

TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
"""Reading waits: a completion streams for as long as the model takes — the
same split-second connect bound and patient read bound the openai-chat
adapter's client carries."""


def _error_detail(body: str) -> str:
    """The vendor's own message from an error body, or the raw body itself.

    The wire's envelope is ``{"type": "error", "error": {"type": …,
    "message": …}}`` — but a proxy may hand back any JSON value, or any
    bytes at all, and those travel verbatim rather than being swallowed or
    crashing the parser. The status, not the body, decides the failure.
    """
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return body
    if not isinstance(payload, dict):
        return body
    envelope = cast("dict[str, Any]", payload)
    error = envelope.get("error")
    if isinstance(error, dict):
        message = cast("dict[str, Any]", error).get("message")
        if isinstance(message, str):
            return message
    return body


def _refusal(model: str, status: int, body: str) -> RuntimeError:
    """The typed failure a non-2xx answer maps to, or the unclassified one.

    A 404 names the model and a 401 names the credential — the contract's two
    actionable failures, raised the same way the SDK's exceptions are on the
    openai-chat side. Anything else stays unclassified for the error frames
    to translate (plan Task 8).
    """
    detail = _error_detail(body)
    if status == 404:
        return ModelNotFoundError(model)
    if status == 401:
        return ProviderAuthError(f"the endpoint refused the credential (401): {detail}")
    return RuntimeError(f"the endpoint answered {status}: {detail}")


def _stream_error(model: str, payload: dict[str, Any]) -> RuntimeError:
    """The typed failure an in-stream ``error`` event maps to, or the plain one.

    A refusal can arrive after the headers: the status was 200 and the error
    travels as the stream's own event. The same two types map as above, and
    a body that is not the wire's object stays unclassified the same way.
    """
    error = payload.get("error")
    kind = cast("dict[str, Any]", error).get("type") if isinstance(error, dict) else None
    if kind == "not_found_error":
        return ModelNotFoundError(model)
    if kind == "authentication_error":
        return ProviderAuthError(f"the endpoint refused the credential ({kind})")
    return RuntimeError(f"the stream carried an error event ({kind})")


class AnthropicMessagesProvider:
    """Streams a chat completion from the Messages wire, hand-rolled over httpx."""

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

        ``request_timeout`` is the HTTP timeout for every call;
        ``temperature_default`` applies only to requests that set no
        temperature of their own.
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.request_timeout = request_timeout
        self.temperature_default = temperature_default

    def describe(self) -> str:
        """Describe the configured model and endpoint without exposing the API key."""
        return f"anthropic model={self.model or '(unset)'} base_url={self.base_url}"

    def configuration_problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready.

        The adapter itself knows only the model string — the endpoint and key
        facts are the provider row's, and the settings gate refuses them at
        write time under the same rules openai-chat is gated by.
        """
        problems: list[str] = []
        if not self.model:
            problems.append("model is not set")
        return problems

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Stream text and reported usage, then DONE on normal completion.

        System turns are hoisted out of the message list and joined with one
        newline — the wire wants them in a ``system`` field, and a prompt
        builder stacking instructions expects its paragraphs to survive.
        ``max_tokens`` always travels (the wire refuses the request without
        it), the temperature only when set, and a ``response_schema`` adds
        the structured-outputs beta header beside its ``output_format``.
        Usage is yielded once, from the counts the start and delta frames
        report. Both the wire's own ``message_stop`` and a normal EOF end
        with exactly one DONE; a refusal or an error event raises without one.
        """
        system = "\n".join(
            message.content for message in request.messages if message.role == "system"
        )
        body: dict[str, Any] = {
            "model": self.model,
            # The wire carries the non-system roles verbatim (contract:
            # "system" | "user").
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
                if message.role != "system"
            ],
            "max_tokens": request.max_tokens or DEFAULT_MAX_TOKENS,
            "stream": True,
        }
        if system:
            body["system"] = system
        temperature = (
            request.temperature if request.temperature is not None else self.temperature_default
        )
        if temperature is not None:
            body["temperature"] = temperature
        if request.response_schema is not None:
            body["output_format"] = {
                "type": "json_schema",
                "schema": request.response_schema,
            }
        headers = {"anthropic-version": ANTHROPIC_VERSION}
        if self.api_key:
            # The wire authenticates with its own header, not a bearer scheme;
            # a keyless local endpoint sends none, as on the openai-chat side.
            headers["x-api-key"] = self.api_key
        if request.response_schema is not None:
            headers["anthropic-beta"] = STRUCTURED_OUTPUTS_BETA

        input_tokens: int | None = None
        usage: Usage | None = None
        async with (
            httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.request_timeout if self.request_timeout is not None else TIMEOUT,
            ) as client,
            client.stream("POST", "/messages", headers=headers, json=body) as response,
        ):
            if response.status_code >= 300:
                detail = (await response.aread()).decode("utf-8", errors="replace")
                raise _refusal(self.model, response.status_code, detail)
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    # The ``event:`` lines repeat the payload's type; the
                    # payload is the one authority this parser needs.
                    continue
                event: dict[str, Any] = json.loads(line.removeprefix("data:").strip())
                kind = event.get("type")
                if kind == "message_start":
                    start: dict[str, Any] = event.get("message") or {}
                    reported_start: dict[str, Any] = start.get("usage") or {}
                    input_tokens = reported_start.get("input_tokens")
                elif kind == "content_block_delta":
                    delta: dict[str, Any] = event.get("delta") or {}
                    text = delta.get("text")
                    if delta.get("type") == "text_delta" and isinstance(text, str):
                        yield Delta(text=text)
                elif kind == "message_delta":
                    reported_delta: dict[str, Any] = event.get("usage") or {}
                    output = reported_delta.get("output_tokens")
                    if output is not None and usage is None:
                        usage = Usage(
                            input_tokens=input_tokens if input_tokens is not None else 0,
                            output_tokens=output,
                        )
                        yield usage
                elif kind == "message_stop":
                    break
                elif kind == "error":
                    raise _stream_error(self.model, event)
        # Exactly one terminal event, whether or not the server sent its own
        # message_stop — a proxy may close the stream without one.
        yield DONE
