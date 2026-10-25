"""The OpenAI-shaped chat strategy: a real socket, real SSE, no vendor key.

The vendor's side is the local stand-in from ``vendor_server``; everything else is
real — the HTTP request, the SSE framing, the JSON deltas, the refusal path. The
same shape serves OpenAI, OpenRouter, DeepSeek, Groq and local servers (Ollama,
llama.cpp, vLLM).
"""

import httpx
import pytest

from app.kernel.llm.contract import DONE, CompletionRequest, Delta, Message, Usage
from app.kernel.llm.openai_compat import OpenAICompatibleProvider, OpenAISettings
from app.kernel.tests.vendor_server import vendor_server

FRAMES = (
    'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"Der Nebel"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{"content":" hob sich"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":7}}\n\n'
    "data: [DONE]\n\n"
)

# A local server may close without the [DONE] line; the terminal event is the
# protocol's own, not the wire's.
FRAMES_WITHOUT_DONE_LINE = "".join(
    frame for frame in FRAMES if not frame.startswith("data: [DONE]")
)

REFUSAL = '{"error": {"message": "Incorrect API key provided"}}'


def _provider(
    base_url: str, model: str = "test-model", api_key: str = "test-key"
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(OpenAISettings(base_url=base_url, model=model, api_key=api_key))


async def test_the_strategy_streams_the_events_in_order() -> None:
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        events = [
            event async for event in provider.stream(CompletionRequest.user("Erzähl weiter."))
        ]
    assert events == [
        Delta(text="Der Nebel"),
        Delta(text=" hob sich"),
        Usage(input_tokens=12, output_tokens=7),
        DONE,
    ]


async def test_done_is_last_with_or_without_a_done_line() -> None:
    with vendor_server(body=FRAMES_WITHOUT_DONE_LINE, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        events = [
            event async for event in provider.stream(CompletionRequest.user("Erzähl weiter."))
        ]
    assert events[-1] is DONE  # exactly one terminal event, marker or no marker


async def test_the_request_carries_model_messages_stream_options_and_the_key() -> None:
    request = CompletionRequest(
        messages=(
            Message(role="system", content="Du bist eine Erzählerin."),
            Message(role="user", content="Erzähl weiter."),
        )
    )
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        [event async for event in provider.stream(request)]
        sent = vendor.last

    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["model"] == "test-model"
    assert sent["body"]["stream"] is True
    # Messages travel as-is, roles and all.
    assert sent["body"]["messages"] == [
        {"role": "system", "content": "Du bist eine Erzählerin."},
        {"role": "user", "content": "Erzähl weiter."},
    ]
    assert sent["body"]["stream_options"] == {"include_usage": True}
    assert sent["headers"]["Authorization"] == "Bearer test-key"


async def test_unset_optionals_are_absent_from_the_body() -> None:
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        [event async for event in provider.stream(CompletionRequest.user("Erzähl weiter."))]
        body = vendor.last["body"]

    assert "temperature" not in body
    assert "max_tokens" not in body
    assert "response_format" not in body


async def test_set_optionals_travel_in_the_body() -> None:
    request = CompletionRequest(
        messages=CompletionRequest.user("Erzähl weiter.").messages,
        temperature=0.7,
        max_tokens=512,
    )
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        [event async for event in provider.stream(request)]
        body = vendor.last["body"]

    assert body["temperature"] == 0.7
    assert body["max_tokens"] == 512


async def test_a_response_schema_maps_to_the_json_response_format() -> None:
    schema: dict[str, object] = {"type": "object", "properties": {"names": {"type": "array"}}}
    request = CompletionRequest(
        messages=CompletionRequest.user("Nenne die Namen.").messages,
        response_schema=schema,
    )
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        [event async for event in provider.stream(request)]
        body = vendor.last["body"]

    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "answer", "schema": schema},
    }


async def test_a_refused_request_raises_so_the_stream_can_report_it() -> None:
    with vendor_server(body=REFUSAL, status=401) as vendor:
        provider = _provider(vendor.base_url)
        with pytest.raises(httpx.HTTPStatusError):
            [event async for event in provider.stream(CompletionRequest.user("Erzähl weiter."))]


def test_a_remote_provider_without_a_key_reports_what_it_needs() -> None:
    problems = OpenAISettings(base_url="https://api.openai.com/v1", model="", api_key="").problems()
    assert any("NARRE_LLM_MODEL" in problem for problem in problems)
    assert any("NARRE_LLM_API_KEY" in problem for problem in problems)


def test_a_local_provider_needs_no_key() -> None:
    settings = OpenAISettings(base_url="http://localhost:11434/v1", model="llama3", api_key="")
    assert settings.problems() == []


def test_the_description_names_the_model_and_the_endpoint() -> None:
    described = _provider("https://openrouter.ai/api/v1", model="deepseek/deepseek-chat").describe()
    assert "openai-compatible" in described
    assert "deepseek/deepseek-chat" in described
    assert "openrouter.ai" in described
