"""The OpenAI-shaped fetch strategy: a real socket, real SSE, no vendor key.

A local server stands in for the vendor because the vendor needs a key and bills
per token; everything else is real — the HTTP request, the SSE framing, the JSON
deltas, the refusal path. The same shape serves OpenAI, OpenRouter, DeepSeek,
Groq and local servers (Ollama, llama.cpp, vLLM).
"""

import json
import threading
from collections.abc import Generator  # noqa: TC003
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
import pytest

from app.kernel.llm.openai_compat import OpenAICompatibleProvider, OpenAISettings

FRAMES = (
    'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"Der Nebel"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{"content":" hob sich"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    "data: [DONE]\n\n"
)

REFUSAL = '{"error": {"message": "Incorrect API key provided"}}'


class _Handler(BaseHTTPRequestHandler):
    """Answers like a chat completions endpoint and records what it received.

    The server object carries this test's state, and http.server's types are off
    repository-wide (``useLibraryCodeForTypes``), hence ``Any`` on the members.
    """

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        server: Any = self.server
        length = int(self.headers.get("content-length", 0))
        body: Any = json.loads(self.rfile.read(length))
        server.received.append({"path": self.path, "headers": dict(self.headers), "body": body})
        payload: bytes = server.payload.encode()
        self.send_response(server.status)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Silence the request log; the test asserts on the record instead."""


@contextmanager
def _vendor(status: int = 200, payload: str = FRAMES) -> Generator[dict[str, Any]]:
    """A real HTTP server on a free port, reachable at ``/v1``."""
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.status = status
    server.payload = payload
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # http.server's own members are untyped repository-wide; the state this
        # test attached to the server is typed by the annotation below.
        received: list[dict[str, Any]] = server.received  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        yield {
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "received": received,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _provider(
    base_url: str, model: str = "test-model", api_key: str = "test-key"
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(OpenAISettings(base_url=base_url, model=model, api_key=api_key))


async def test_the_strategy_streams_the_deltas_in_order() -> None:
    with _vendor() as vendor:
        provider = _provider(vendor["base_url"])
        deltas = [delta async for delta in provider.stream("Erzähl weiter.")]
    assert deltas == ["Der Nebel", " hob sich"]


async def test_the_request_carries_model_messages_and_the_key() -> None:
    with _vendor() as vendor:
        provider = _provider(vendor["base_url"])
        [delta async for delta in provider.stream("Erzähl weiter.")]
        sent = vendor["received"][0]

    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["model"] == "test-model"
    assert sent["body"]["stream"] is True
    assert sent["body"]["messages"] == [{"role": "user", "content": "Erzähl weiter."}]
    assert sent["headers"]["Authorization"] == "Bearer test-key"


async def test_a_refused_request_raises_so_the_stream_can_report_it() -> None:
    with _vendor(status=401, payload=REFUSAL) as vendor:
        provider = _provider(vendor["base_url"])
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
