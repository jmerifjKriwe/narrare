"""The anthropic adapter over a real socket: real HTTP, real SSE, no vendor.

The vendor's side is the Messages stand-in from :mod:`app.kernel.testing.vendor`;
everything else is real — the httpx client, the POST, the event framing, the
JSON deltas, the refusal path. The typed failures are the contract's: a 404
names the model and a 401 names the credential, the same two the openai-chat
adapter raises, so the surfaces above can name the mistake without knowing
which vendor refused.
"""

import pytest

from app.kernel.llm.anthropic_messages import DEFAULT_MAX_TOKENS, AnthropicMessagesProvider
from app.kernel.llm.contract import (
    DONE,
    CompletionRequest,
    Delta,
    Message,
    ModelNotFoundError,
    ProviderAuthError,
    Usage,
)
from app.kernel.testing.vendor import MESSAGES_DELTAS, MESSAGES_USAGE, messages_vendor

EXPECTED_EVENTS = [
    Delta(text=MESSAGES_DELTAS[0]),
    Delta(text=MESSAGES_DELTAS[1]),
    Usage(input_tokens=MESSAGES_USAGE[0], output_tokens=MESSAGES_USAGE[1]),
    DONE,
]


def _provider(
    base_url: str,
    model: str = "vendor-mini",
    api_key: str = "test-key",
    temperature_default: float | None = None,
) -> AnthropicMessagesProvider:
    """Build a provider for the test endpoint with optional overrides."""
    return AnthropicMessagesProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature_default=temperature_default,
    )


async def test_the_adapter_maps_the_messages_stream() -> None:
    """The frames become ordered text, the reported usage, one terminal DONE."""
    with messages_vendor() as vendor:
        events = [
            event async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
        ]
    assert events == EXPECTED_EVENTS


async def test_the_request_carries_the_headers_the_model_and_the_hoisted_system() -> None:
    """The wire's shape: its own auth headers, the messages, system joined."""
    request = CompletionRequest(
        messages=(
            Message(role="system", content="Du bist eine Erzählerin."),
            Message(role="system", content="Antworte auf Deutsch."),
            Message(role="user", content="Erzähl weiter."),
        )
    )
    with messages_vendor() as vendor:
        [_ async for _ in _provider(vendor.base_url, model="vendor-max").stream(request)]
        sent = vendor.last

    assert sent["path"] == "/v1/messages"
    assert sent["body"]["model"] == "vendor-max"
    assert sent["body"]["stream"] is True
    # System turns are hoisted out of the list and joined with one newline.
    assert sent["body"]["system"] == "Du bist eine Erzählerin.\nAntworte auf Deutsch."
    assert sent["body"]["messages"] == [{"role": "user", "content": "Erzähl weiter."}]
    assert sent["headers"]["x-api-key"] == "test-key"
    assert sent["headers"]["anthropic-version"] == "2023-06-01"


async def test_a_missing_model_is_named() -> None:
    """A 404 raises the contract's :class:`ModelNotFoundError`, naming the model."""
    with messages_vendor() as vendor:
        vendor.refuse_requests(404, {"type": "error", "error": {"type": "not_found_error"}})
        with pytest.raises(ModelNotFoundError) as raised:
            [
                event
                async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
            ]
    assert raised.value.model == "vendor-mini"


async def test_a_refused_key_is_the_typed_auth_failure() -> None:
    """A 401 raises :class:`ProviderAuthError` once: one request, no retry."""
    with messages_vendor() as vendor:
        vendor.refuse_requests(401, {"type": "error", "error": {"type": "authentication_error"}})
        with pytest.raises(ProviderAuthError):
            [
                event
                async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
            ]
        assert len(vendor.received) == 1


async def test_an_error_event_raises_without_done() -> None:
    """A 200 stream that ends in an ``error`` event raises; no DONE is yielded."""
    with messages_vendor() as vendor:
        vendor.fail_stream("overloaded_error")
        events: list[object] = []
        with pytest.raises(RuntimeError, match="overloaded_error"):
            events = [
                event
                async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
            ]
    assert all(event is not DONE for event in events)


async def test_unset_optionals_are_absent_and_max_tokens_gets_the_default() -> None:
    """Temperature travels only when set; the wire's mandatory max_tokens does not.

    The Messages wire has no default for ``max_tokens`` — the request would
    be refused without one — so the module default travels where the request
    set none, and an explicit limit overrides it.
    """
    with messages_vendor() as vendor:
        [_ async for _ in _provider(vendor.base_url).stream(CompletionRequest.user("Erstens"))]
        [
            _
            async for _ in _provider(vendor.base_url).stream(
                CompletionRequest(
                    messages=CompletionRequest.user("Zweitens").messages, max_tokens=512
                )
            )
        ]
        unset, set_explicitly = vendor.received[-2], vendor.received[-1]

    assert unset["body"]["max_tokens"] == DEFAULT_MAX_TOKENS
    assert "temperature" not in unset["body"]
    assert set_explicitly["body"]["max_tokens"] == 512


async def test_the_temperature_default_applies_only_when_the_request_sets_none() -> None:
    """The request's temperature wins; without one, the profile's default travels."""
    with messages_vendor() as vendor:
        provider = _provider(vendor.base_url, temperature_default=0.5)
        [_ async for _ in provider.stream(CompletionRequest.user("Erstens"))]
        [
            _
            async for _ in provider.stream(
                CompletionRequest(
                    messages=CompletionRequest.user("Zweitens").messages, temperature=0.9
                )
            )
        ]
        unset, set_explicitly = vendor.received[-2], vendor.received[-1]

    assert unset["body"]["temperature"] == 0.5
    assert set_explicitly["body"]["temperature"] == 0.9


async def test_a_response_schema_reaches_the_wire_as_the_output_format() -> None:
    """A schema travels as ``output_format`` under its own beta header."""
    schema: dict[str, object] = {"type": "object", "properties": {"names": {"type": "array"}}}
    request = CompletionRequest(
        messages=CompletionRequest.user("Nenne die Namen.").messages, response_schema=schema
    )
    with messages_vendor() as vendor:
        [_ async for _ in _provider(vendor.base_url).stream(request)]
        sent = vendor.last

    assert sent["headers"]["anthropic-beta"] == "structured-outputs-2025-11-13"
    assert sent["body"]["output_format"] == {"type": "json_schema", "schema": schema}


async def test_a_keyless_local_endpoint_sends_no_api_key_header() -> None:
    """A local server configured without a key gets no ``x-api-key``, not an empty one."""
    with messages_vendor() as vendor:
        [
            _
            async for _ in _provider(vendor.base_url, api_key="").stream(
                CompletionRequest.user("Hi")
            )
        ]
        sent = vendor.last
    assert "x-api-key" not in sent["headers"]
