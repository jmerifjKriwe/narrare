"""A stand-in embedding vendor for the E2E stacks: real HTTP, no key, no cost.

It speaks the OpenAI ``/embeddings`` shape and answers with signed feature
hashing over the lowercased words — the same idea as the kernel fake, so a query
sharing words with a passage ranks it first through the real pgvector cosine
ordering. The width is mutable: a test flipping it is a user switching models,
and everything downstream (the corpus guard, re-embedding) runs for real.
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
