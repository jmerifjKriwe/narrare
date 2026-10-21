"""A vendor-shaped HTTP server for the boundary tests: a real socket, no vendor.

The vendors the two boundaries talk to cost money and need keys, so their tests
point the strategy at a local server that speaks the same wire format. Everything
else stays real: the HTTP request, the framing, the parsing, the refusal path.
"""

import json
import threading
from collections.abc import Generator  # noqa: TC003
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class Vendor:
    """The stand-in's address, and every request it received, in order."""

    base_url: str
    # The parameterized factory keeps the field's type visible to pyright; a bare
    # ``list`` factory leaves it unknown repository-wide (types come from typeshed).
    received: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    @property
    def last(self) -> dict[str, Any]:
        return self.received[-1]


class _Handler(BaseHTTPRequestHandler):
    """Answers with one canned body and records what it received.

    The server object carries this test's state, and http.server's types are off
    repository-wide (``useLibraryCodeForTypes``), hence ``Any`` on the members.
    """

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        server: Any = self.server
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length)
        server.received.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": json.loads(raw) if raw else None,
            }
        )
        payload: bytes = server.body.encode()
        self.send_response(server.status)
        self.send_header("Content-Type", server.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Silence the request log; the tests assert on the record instead."""


@contextmanager
def vendor_server(
    *, body: str = "", status: int = 200, content_type: str = "application/json"
) -> Generator[Vendor]:
    """A real HTTP server on a free port, reachable at ``/v1``."""
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.status = status
    server.body = body
    server.content_type = content_type
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        vendor = Vendor(base_url=f"http://127.0.0.1:{server.server_port}/v1")
        # http.server's own members are untyped; the state attached above is what
        # the annotation promises.
        vendor.received = server.received  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        yield vendor
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
