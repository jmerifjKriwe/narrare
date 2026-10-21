"""The OpenAI-shaped chat strategy: a real socket, real SSE, no vendor key.

The vendor's side is the local stand-in from ``vendor_server``; everything else is
real — the HTTP request, the SSE framing, the JSON deltas, the refusal path. The
same shape serves OpenAI, OpenRouter, DeepSeek, Groq and local servers (Ollama,
llama.cpp, vLLM).
"""

import httpx
import pytest

from app.kernel.llm.openai_compat import OpenAICompatibleProvider, OpenAISettings
from app.kernel.tests.vendor_server import vendor_server

FRAMES = (
    'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"Der Nebel"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{"content":" hob sich"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    "data: [DONE]\n\n"
)

REFUSAL = '{"error": {"message": "Incorrect API key provided"}}'


def _provider(
    base_url: str, model: str = "test-model", api_key: str = "test-key"
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(OpenAISettings(base_url=base_url, model=model, api_key=api_key))


async def test_the_strategy_streams_the_deltas_in_order() -> None:
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        deltas = [delta async for delta in provider.stream("Erzähl weiter.")]
    assert deltas == ["Der Nebel", " hob sich"]


async def test_the_request_carries_model_messages_and_the_key() -> None:
    with vendor_server(body=FRAMES, content_type="text/event-stream") as vendor:
        provider = _provider(vendor.base_url)
        [delta async for delta in provider.stream("Erzähl weiter.")]
        sent = vendor.last

    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["model"] == "test-model"
    assert sent["body"]["stream"] is True
    assert sent["body"]["messages"] == [{"role": "user", "content": "Erzähl weiter."}]
    assert sent["headers"]["Authorization"] == "Bearer test-key"


async def test_a_refused_request_raises_so_the_stream_can_report_it() -> None:
    with vendor_server(body=REFUSAL, status=401) as vendor:
        provider = _provider(vendor.base_url)
        with pytest.raises(httpx.HTTPStatusError):
            [delta async for delta in provider.stream("Erzähl weiter.")]


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
