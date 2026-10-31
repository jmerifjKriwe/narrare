"""The openai-chat adapter over the official SDK: a real socket, real SSE, no vendor.

The vendor's side is the local stand-in from :mod:`app.kernel.testing.vendor`;
everything else is real — the SDK client, the HTTP request, the SSE framing,
the JSON deltas, the refusal path. The same shape serves OpenAI, OpenRouter,
DeepSeek, Groq and local servers (Ollama, llama.cpp, vLLM).
"""

from uuid import uuid4

import pytest
from openai import APITimeoutError, AuthenticationError

from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.contract import DONE, CompletionRequest, Delta, Message, Usage
from app.kernel.llm.openai_chat import OpenAIChatProvider
from app.kernel.llm.profiles import ProfileRepository
from app.kernel.llm.resolution import resolve_provider
from app.kernel.testing.vendor import CHAT_DELTAS, CHAT_USAGE, chat_vendor

EXPECTED_EVENTS = [
    Delta(text=CHAT_DELTAS[0]),
    Delta(text=CHAT_DELTAS[1]),
    Usage(input_tokens=CHAT_USAGE[0], output_tokens=CHAT_USAGE[1]),
    DONE,
]


def _provider(
    base_url: str,
    model: str = "vendor-mini",
    api_key: str = "test-key",
    temperature_default: float | None = None,
) -> OpenAIChatProvider:
    """Build a provider for the test endpoint with optional overrides."""
    return OpenAIChatProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature_default=temperature_default,
    )


async def test_the_adapter_streams_the_events_in_order() -> None:
    """Verify socket SSE frames become ordered text, usage, and terminal events."""
    with chat_vendor() as vendor:
        events = [
            event async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
        ]
    assert events == EXPECTED_EVENTS


async def test_a_stored_request_timeout_reaches_the_socket() -> None:
    """The profile's ``request_timeout`` bounds the wait: a slow vendor loses.

    The vendor answers a whole second late; a 0.2 s timeout must give up well
    before that. The vendor's completion counter is the deterministic half:
    the answer never reached the client (0 served), so the exception is the
    configured read timeout firing — not a slow runner's wall clock and not
    the delayed answer arriving. Without the wiring the call would succeed a
    second later and the counter would read 1.
    """
    with chat_vendor() as vendor:
        vendor.delay_completions(1.0)
        provider = OpenAIChatProvider(
            base_url=vendor.base_url,
            model="vendor-mini",
            api_key="test-key",
            request_timeout=0.2,
        )
        with pytest.raises(APITimeoutError):
            [event async for event in provider.stream(CompletionRequest.user("Hi"))]
        assert vendor.completions == 0  # the answer never arrived


async def test_the_stored_request_timeout_reaches_the_socket_through_resolution(
    empty_tables: None, schema: None
) -> None:
    """A stored profile's timeout survives ``from_profile`` and bounds the call.

    The row is read back by the resolution cascade — not handed to the adapter
    directly — so dropping ``request_timeout`` from ``from_profile`` lets the
    delayed vendor answer and this test fail. The counter proves the answer
    never arrived; the resolved fact sheet names the configured 0.2 seconds.
    """
    owner = uuid4()
    await seed_user(owner)
    with chat_vendor() as vendor:
        vendor.delay_completions(1.0)
        async with Session() as session:
            await ProfileRepository(session, owner).create(
                name="Stored",
                kind="openai-chat",
                base_url=vendor.base_url,
                model="vendor-mini",
                request_timeout=0.2,
                is_default=True,
            )
            await session.commit()
        async with Session() as session:
            resolved = await resolve_provider(session, owner, "writing.continuation")
            assert resolved.request_timeout == 0.2
            with pytest.raises(APITimeoutError):
                [event async for event in resolved.provider.stream(CompletionRequest.user("Hi"))]
            assert vendor.completions == 0  # the answer never arrived


async def test_done_is_last_without_the_wires_done_line_too() -> None:
    """A local server closing without ``[DONE]`` still yields exactly one DONE."""
    with chat_vendor() as vendor:
        vendor.omit_done_marker()
        events = [
            event async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
        ]
    assert events == EXPECTED_EVENTS


async def test_a_vendor_answers_with_the_prose_the_caller_chose() -> None:
    """The stand-in says what it was told to say, in pieces, in order.

    The leading space matters: a continuation that follows a full stop arrives
    with one, and the editor shows the stream exactly as it was sent.
    """
    prose = " The fog lifted off the lake and laid itself over the road."
    with chat_vendor() as vendor:
        vendor.set_answer(prose)
        events = [
            event async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
        ]
    deltas = [event.text for event in events if isinstance(event, Delta)]
    assert len(deltas) > 1
    assert "".join(deltas) == prose


async def test_a_vendor_keeps_the_answers_trailing_whitespace() -> None:
    """The stream's last bytes survive: a streamed newline is not trimmed."""
    prose = "The fog lifted off the lake.\n"
    with chat_vendor() as vendor:
        vendor.set_answer(prose)
        events = [
            event async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
        ]
    assert "".join(event.text for event in events if isinstance(event, Delta)) == prose


async def test_a_refusal_raises_exactly_once() -> None:
    """A 401 raises, and the vendor saw one request: ``max_retries=0`` in force."""
    with chat_vendor() as vendor:
        vendor.refuse_requests()
        with pytest.raises(AuthenticationError):
            [
                event
                async for event in _provider(vendor.base_url).stream(CompletionRequest.user("Hi"))
            ]
        assert len(vendor.received) == 1


async def test_the_request_carries_model_messages_stream_options_and_the_key() -> None:
    """Verify request serialization preserves messages and requests usage with auth."""
    request = CompletionRequest(
        messages=(
            Message(role="system", content="Du bist eine Erzählerin."),
            Message(role="user", content="Erzähl weiter."),
        )
    )
    with chat_vendor() as vendor:
        [_ async for _ in _provider(vendor.base_url, model="vendor-max").stream(request)]
        sent = vendor.last

    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["model"] == "vendor-max"
    assert sent["body"]["stream"] is True
    # Messages travel as-is, roles and all.
    assert sent["body"]["messages"] == [
        {"role": "system", "content": "Du bist eine Erzählerin."},
        {"role": "user", "content": "Erzähl weiter."},
    ]
    assert sent["body"]["stream_options"] == {"include_usage": True}
    assert sent["headers"]["authorization"] == "Bearer test-key"


async def test_a_keyless_local_endpoint_sends_no_authorization_header() -> None:
    """A local server configured without a key gets no auth header, as before the SDK."""
    with chat_vendor() as vendor:
        [
            _
            async for _ in _provider(vendor.base_url, api_key="").stream(
                CompletionRequest.user("Hi")
            )
        ]
        sent = vendor.last
    assert "Authorization" not in sent["headers"]


async def test_unset_optionals_are_absent_from_the_body() -> None:
    """Verify unset completion options are omitted for compatibility with local servers."""
    with chat_vendor() as vendor:
        [
            _
            async for _ in _provider(vendor.base_url, temperature_default=None).stream(
                CompletionRequest.user("Erzähl weiter.")
            )
        ]
        body = vendor.last["body"]

    assert "temperature" not in body
    assert "max_tokens" not in body
    assert "response_format" not in body


async def test_the_temperature_default_applies_only_when_the_request_sets_none() -> None:
    """The request's temperature wins; without one, the profile's default travels."""
    with chat_vendor() as vendor:
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


async def test_set_optionals_travel_in_the_body() -> None:
    """Verify an explicit token limit reaches the vendor request."""
    request = CompletionRequest(
        messages=CompletionRequest.user("Erzähl weiter.").messages, max_tokens=512
    )
    with chat_vendor() as vendor:
        [_ async for _ in _provider(vendor.base_url).stream(request)]
        assert vendor.last["body"]["max_tokens"] == 512


async def test_a_response_schema_reaches_the_wire_as_the_json_response_format() -> None:
    """Verify a requested response schema uses the vendor JSON schema format."""
    schema: dict[str, object] = {"type": "object", "properties": {"names": {"type": "array"}}}
    request = CompletionRequest(
        messages=CompletionRequest.user("Nenne die Namen.").messages, response_schema=schema
    )
    with chat_vendor() as vendor:
        [_ async for _ in _provider(vendor.base_url).stream(request)]
        assert vendor.last["body"]["response_format"] == {
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": schema},
        }


# The environment tier: NARRE_LLM_* semantics unchanged, the alias's own factory.


def test_the_environment_factory_reads_the_narre_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the factory reads the same variables the hand-rolled adapter did."""
    monkeypatch.setenv("NARRE_LLM_BASE_URL", "https://openrouter.ai/api/v1/")
    monkeypatch.setenv("NARRE_LLM_MODEL", "deepseek/deepseek-chat")
    monkeypatch.setenv("NARRE_LLM_API_KEY", "sk-env")

    provider = OpenAIChatProvider.from_environment()

    assert provider.base_url == "https://openrouter.ai/api/v1"  # trailing slash dropped
    assert provider.model == "deepseek/deepseek-chat"
    assert provider.api_key == "sk-env"


def test_a_remote_provider_without_a_key_reports_what_it_needs() -> None:
    """Verify remote settings report both missing model and missing API key."""
    provider = OpenAIChatProvider(base_url="https://api.openai.com/v1", model="", api_key="")
    problems = provider.configuration_problems()
    assert any("NARRE_LLM_MODEL" in problem for problem in problems)
    assert any("NARRE_LLM_API_KEY" in problem for problem in problems)


def test_a_local_provider_needs_no_key() -> None:
    """Verify a configured local endpoint is valid without an API key."""
    provider = OpenAIChatProvider(base_url="http://localhost:11434/v1", model="llama3", api_key="")
    assert provider.configuration_problems() == []


def test_the_description_names_the_model_and_the_endpoint() -> None:
    """Verify the provider description identifies its kind, model, and endpoint."""
    described = _provider("https://openrouter.ai/api/v1", model="deepseek/deepseek-chat").describe()
    assert "openai-chat" in described
    assert "deepseek/deepseek-chat" in described
    assert "openrouter.ai" in described
