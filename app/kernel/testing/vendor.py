"""Stand-in vendors for the tests and E2E stacks: real HTTP, no key, no cost.

The embeddings vendor speaks the OpenAI ``/embeddings`` shape and answers with
signed feature hashing over the lowercased words — the same idea as the kernel
fake, so a query sharing words with a passage ranks it first through the real
pgvector cosine ordering. The width is mutable: a test flipping it is a user
switching models, and everything downstream (the corpus guard, re-embedding)
runs for real.

The chat vendor speaks the OpenAI ``/chat/completions`` SSE shape (deltas in
order, one usage frame, the ``[DONE]`` line) plus ``GET /models`` for
discovery, so the settings surface's test and discovery endpoints run against
the same kind of socket a real endpoint is. It records every request it
receives and can refuse them: the adapter's raise-once semantics need a vendor
that says no.
"""

import hashlib
import json
import math
import re
import threading
from collections.abc import Generator  # noqa: TC003
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class EmbeddingsVendor:
    """The stand-in's address, its width, and every request it received."""

    def __init__(self, base_url: str, server: Any, thread: threading.Thread) -> None:
        self.base_url = base_url
        self._server = server
        self._thread = thread

    def set_width(self, width: int) -> None:
        """Answer at another width from now on: the model changed."""
        self._server.width = width

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _embed(text: str, width: int) -> list[float]:
    vector = [0.0] * width
    for token in re.findall(r"\w+", text.lower()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % width
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class _Handler(BaseHTTPRequestHandler):
    """Answers the vendor's shape from the server object's mutable width.

    http.server's types are invisible repository-wide (``useLibraryCodeForTypes``),
    hence ``Any`` on the members.
    """

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        server: Any = self.server
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length))
        vectors = [_embed(text, server.width) for text in body["input"]]
        payload = json.dumps(
            {
                "data": [
                    {"object": "embedding", "index": index, "embedding": vector}
                    for index, vector in enumerate(vectors)
                ],
                "model": body.get("model"),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Silence the request log; nothing asserts on it here."""


@contextmanager
def embeddings_vendor(width: int = 384) -> Generator[EmbeddingsVendor]:
    """A real HTTP server on a free port, answering token-hash vectors."""
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.width = width
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield EmbeddingsVendor(
            base_url=f"http://127.0.0.1:{server.server_port}", server=server, thread=thread
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


CHAT_DELTAS = ("Der Nebel", " hob sich")
"""The streamed answer, in order: the adapter's tests assert these verbatim."""

CHAT_USAGE = (12, 7)
"""The one usage frame's counts: (prompt_tokens, completion_tokens)."""

CHAT_MODELS = ("vendor-max", "vendor-mini")
"""The discovery endpoint's catalog, in the sorted order the API returns."""

DONE_LINE = "data: [DONE]\n\n"
"""The wire's own terminal line; local servers omit it, so tests can too."""


def _chat_frames(*, done_line: bool) -> str:
    """The SSE answer: two deltas, a finish frame, the usage, maybe [DONE]."""
    first, second = CHAT_DELTAS
    input_tokens, output_tokens = CHAT_USAGE
    frames = (
        'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":'
        + json.dumps(first)
        + "}}]}\n\n"
        'data: {"choices":[{"index":0,"delta":{"content":' + json.dumps(second) + "}}]}\n\n"
        'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":'
        + str(input_tokens)
        + ',"completion_tokens":'
        + str(output_tokens)
        + "}}\n\n"
    )
    return frames + (DONE_LINE if done_line else "")


class ChatVendor:
    """The chat stand-in's address, its switches, and every request it received."""

    def __init__(self, base_url: str, server: Any, thread: threading.Thread) -> None:
        self.base_url = base_url
        self._server = server
        self._thread = thread

    @property
    def received(self) -> list[dict[str, Any]]:
        """Every request the vendor saw, in arrival order."""
        return self._server.received

    @property
    def last(self) -> dict[str, Any]:
        """The most recent request the vendor saw."""
        return self._server.received[-1]

    def refuse_requests(self) -> None:
        """Answer every chat completion with HTTP 401 from now on."""
        self._server.refuse = True

    def omit_done_marker(self) -> None:
        """End the SSE answer without the wire's ``[DONE]`` line, like a local server."""
        self._server.done_line = False

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _ChatHandler(BaseHTTPRequestHandler):
    """Answers the OpenAI chat shape from the server object's mutable switches.

    http.server's types are invisible repository-wide (``useLibraryCodeForTypes``),
    hence ``Any`` on the members.
    """

    protocol_version = "HTTP/1.1"

    def _reply(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _record(self, body: dict[str, Any] | None) -> None:
        server: Any = self.server
        # Header names fold to lowercase: httpx and httpx2 spell them
        # differently, and the tests assert on the name, not the client's habit.
        folded = {name.lower(): value for name, value in self.headers.items()}
        server.received.append({"path": self.path, "headers": folded, "body": body})

    def do_POST(self) -> None:
        server: Any = self.server
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length)
        body: dict[str, Any] | None = json.loads(raw) if raw else None
        if self.path != "/v1/chat/completions":
            self._record(None)
            self._reply(404, "application/json", b"{}")
            return
        self._record(body)
        if server.refuse:
            payload = json.dumps({"error": {"message": "Incorrect API key provided"}}).encode()
            self._reply(401, "application/json", payload)
            return
        self._reply(
            200,
            "text/event-stream",
            _chat_frames(done_line=server.done_line).encode(),
        )

    def do_GET(self) -> None:
        if self.path != "/v1/models":
            self._record(None)
            self._reply(404, "application/json", b"{}")
            return
        self._record(None)
        payload = json.dumps(
            {
                "object": "list",
                "data": [
                    {"id": model, "object": "model", "created": 0, "owned_by": "vendor"}
                    for model in CHAT_MODELS
                ],
            }
        ).encode()
        self._reply(200, "application/json", payload)

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Silence the request log; the record is what tests assert on."""


@contextmanager
def chat_vendor() -> Generator[ChatVendor]:
    """A real HTTP server on a free port, answering the OpenAI chat shape."""
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _ChatHandler)
    server.refuse = False
    server.done_line = True
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ChatVendor(
            base_url=f"http://127.0.0.1:{server.server_port}/v1", server=server, thread=thread
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
