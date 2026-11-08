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

The messages vendor speaks the Anthropic ``/messages`` SSE shape (a start
frame carrying the input tokens, ``text_delta`` pieces, one delta frame with
the output tokens, one stop) under the same contract: it records, and it can
refuse — the anthropic adapter is pinned against the same kind of socket.
"""

import hashlib
import json
import math
import re
import threading
import time
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


def _split_answer(text: str) -> tuple[str, ...]:
    """Cut prose into stream-sized pieces without changing one character.

    Four words per piece, and each piece carries the whitespace that preceded its
    first word: an answer that begins with a space keeps it, because what the
    adapter and the editor see is the stream's exact bytes.
    """
    tokens = re.findall(r"\s*\S+|\s+$", text)
    return tuple("".join(tokens[index : index + 4]) for index in range(0, len(tokens), 4))


def _chat_frames(*, done_line: bool, answer: tuple[str, ...]) -> str:
    """The SSE answer: a delta per piece, a finish frame, the usage, maybe [DONE].

    The first delta carries the role as a real server's does; every delta carries
    its own piece, so a caller can watch the answer assemble in order.
    """
    input_tokens, output_tokens = CHAT_USAGE
    deltas = "".join(
        'data: {"choices":[{"index":0,"delta":{'
        + ('"role":"assistant",' if index == 0 else "")
        + '"content":'
        + json.dumps(piece)
        + "}}]}\n\n"
        for index, piece in enumerate(answer)
    )
    frames = (
        deltas + 'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
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
    def completions(self) -> int:
        """How many chat completions the vendor finished serving.

        A timed-out read never gets here: the answer is counted only once the
        delayed reply was written, so a timeout test can prove deterministically
        that the answer never arrived.
        """
        return self._server.completions

    @property
    def last(self) -> dict[str, Any]:
        """The most recent request the vendor saw."""
        return self._server.received[-1]

    def refuse_requests(self, status: int = 401, payload: dict[str, Any] | None = None) -> None:
        """Answer every chat completion with ``status`` from now on.

        The body is the vendor-shaped error the client maps: the default is
        the 401 message a wrong key produces; a 404 test passes the shape the
        wire's own ``not_found_error`` carries, so the adapter's mapping is
        pinned against the body a real server sends.
        """
        self._server.refuse = True
        self._server.refuse_status = status
        self._server.refuse_payload = payload

    def omit_done_marker(self) -> None:
        """End the SSE answer without the wire's ``[DONE]`` line, like a local server."""
        self._server.done_line = False

    def set_answer(self, text: str) -> None:
        """Answer every chat completion with ``text`` from now on, in pieces.

        The default is :data:`CHAT_DELTAS`; a caller with its own prose — the
        screenshot capture, for one — says it here instead of renaming a constant
        every test asserts verbatim.
        """
        self._server.answer = _split_answer(text)

    def delay_completions(self, seconds: float) -> None:
        """Sleep ``seconds`` before every completions answer from now on.

        The slow endpoint a stored ``request_timeout`` exists for: the read
        timeout tests need a vendor that takes longer to answer than the
        profile allows, or a timeout that never reached the socket would
        pass unnoticed.
        """
        self._server.delay = seconds

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _JsonHandler(BaseHTTPRequestHandler):
    """The two moves both wire handlers share: a JSON reply, and the record.

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

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Silence the request log; the record is what tests assert on."""


class _ChatHandler(_JsonHandler):
    """Answers the OpenAI chat shape from the server object's mutable switches."""

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
            payload = json.dumps(
                server.refuse_payload or {"error": {"message": "Incorrect API key provided"}}
            ).encode()
            self._reply(server.refuse_status, "application/json", payload)
            return
        if server.delay:
            # The slow answer the read-timeout tests need: this request's own
            # thread sleeps, so other requests are unaffected.
            time.sleep(server.delay)
        self._reply(
            200,
            "text/event-stream",
            _chat_frames(done_line=server.done_line, answer=server.answer).encode(),
        )
        server.completions += 1

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


@contextmanager
def chat_vendor() -> Generator[ChatVendor]:
    """A real HTTP server on a free port, answering the OpenAI chat shape."""
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _ChatHandler)
    server.refuse = False
    server.refuse_status = 401
    server.refuse_payload = None
    server.done_line = True
    server.answer = CHAT_DELTAS
    server.delay = 0.0
    server.received = []
    server.completions = 0
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


MESSAGES_DELTAS = ("Hel", "lo")
"""The streamed answer, in order: the adapter's tests assert these verbatim."""

MESSAGES_USAGE = (4, 2)
"""The stream's token counts, as the start and delta frames report them:
``(input_tokens, output_tokens)``."""


def _messages_frames(*, stop_frame: bool, error_type: str | None) -> str:
    """The Messages SSE answer: a start, the deltas, one delta frame, the stop.

    The framing is the real API's — ``event:`` and ``data:`` lines, blank line
    between frames — and the ``type`` in every ``data:`` payload repeats the
    event's name, the way a real stream carries it.
    """
    input_tokens, output_tokens = MESSAGES_USAGE
    start = (
        "event: message_start\n"
        "data: "
        + json.dumps(
            {
                "type": "message_start",
                "message": {
                    "id": "msg_vendor",
                    "role": "assistant",
                    "usage": {"input_tokens": input_tokens, "output_tokens": 0},
                },
            }
        )
        + "\n\n"
    )
    deltas = "".join(
        "event: content_block_delta\n"
        "data: "
        + json.dumps(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": piece},
            }
        )
        + "\n\n"
        for piece in MESSAGES_DELTAS
    )
    delta_frame = (
        "event: message_delta\n"
        "data: "
        + json.dumps(
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": output_tokens},
            }
        )
        + "\n\n"
    )
    stop = delta_frame + (
        'event: message_stop\ndata: {"type":"message_stop"}\n\n' if stop_frame else ""
    )
    error = (
        "event: error\n"
        "data: "
        + json.dumps(
            {
                "type": "error",
                "error": {"type": error_type, "message": "the stand-in refused"},
            }
        )
        + "\n\n"
    )
    return start + deltas + (error if error_type else stop)


class MessagesVendor:
    """The Messages stand-in's address, its switches, and every request it received."""

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

    def refuse_requests(self, status: int = 401, payload: Any = None) -> None:
        """Answer every message request with ``status`` from now on.

        The payload is whatever JSON the body should carry: normally the
        wire's own error envelope, but a non-object (``[]``) travels
        verbatim — that is how the adapter's body guards are pinned against
        a proxy that answers the wrong shape. ``None`` means the empty
        object: ``{}`` is what goes on the wire.
        """
        self._server.refuse = True
        self._server.refuse_status = status
        self._server.refuse_payload = payload

    def fail_stream(self, error_type: str) -> None:
        """Answer with a 200 stream that ends in an ``error`` event, no stop.

        A refusal can arrive mid-stream on the real wire: the status was 200,
        the headers are sent, and the error travels as an event of its own.
        """
        self._server.fail_stream = error_type

    def omit_stop_frame(self) -> None:
        """End the SSE answer without the wire's ``message_stop``, the proxy's way.

        The usage frame stays; only the stop event is dropped, so the stream
        simply ends — what the one-DONE-on-EOF claim has to survive.
        """
        self._server.stop_frame = False

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _MessagesHandler(_JsonHandler):
    """Answers the Anthropic Messages shape from the server object's switches."""

    def do_POST(self) -> None:
        server: Any = self.server
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length)
        body: dict[str, Any] | None = json.loads(raw) if raw else None
        if self.path != "/v1/messages":
            self._record(None)
            self._reply(404, "application/json", b"{}")
            return
        self._record(body)
        if server.refuse:
            # `is not None`, not truthiness: the whole point of a `[]` payload
            # is that it travels verbatim, and `[] or {}` would coerce it to
            # `{}` before the socket ever saw it.
            payload = json.dumps(
                server.refuse_payload if server.refuse_payload is not None else {}
            ).encode()
            self._reply(server.refuse_status, "application/json", payload)
            return
        self._reply(
            200,
            "text/event-stream",
            _messages_frames(stop_frame=server.stop_frame, error_type=server.fail_stream).encode(),
        )


@contextmanager
def messages_vendor() -> Generator[MessagesVendor]:
    """A real HTTP server on a free port, answering the Anthropic Messages shape."""
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _MessagesHandler)
    server.refuse = False
    server.refuse_status = 401
    server.refuse_payload = None
    server.fail_stream = None
    server.stop_frame = True
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield MessagesVendor(
            base_url=f"http://127.0.0.1:{server.server_port}/v1", server=server, thread=thread
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
