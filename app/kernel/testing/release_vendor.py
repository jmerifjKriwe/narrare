"""A release source for the boundary tests: a real socket, no GitHub.

The update check talks to GitHub's latest-release endpoint, which costs quota
and needs the network. The tests (and the browser E2E) point
``NARRA_UPDATE_CHECK_URL`` at this server instead: the request, the framing,
the JSON parse and the fallback path stay real, only the source is a stand-in.

``state`` is deliberately mutable at runtime — a test changes the tag, the
notes or the link between reads, and a later request sees the new answer. The
default tag is the running version, so an untouched vendor never announces an
update.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType  # noqa: TC003
from typing import Any

from app.kernel.version import __version__

RELEASE_PATH = "/repos/jmerifjKriwe/narrare/releases/latest"


class ReleaseVendor:
    """A real HTTP release source on a free port, usable as a context manager.

    ``base_url`` is the full latest-release URL, so it can be handed to
    ``NARRA_UPDATE_CHECK_URL`` unchanged. ``received`` is every request path the
    server saw, in order; ``status`` lets a test turn the source into an outage.
    """

    def __init__(self, *, tag: str = __version__, notes: str = "", url: str = "") -> None:
        self.state: dict[str, str] = {"tag": tag, "notes": notes, "url": url}
        self.base_url = ""
        self.received: list[str] = []
        self.status = 200
        self._server: Any = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> ReleaseVendor:
        server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        server.vendor = self
        self._server = server
        self.base_url = f"http://127.0.0.1:{server.server_port}{RELEASE_PATH}"
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        server: Any = self._server
        thread = self._thread
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)


class _Handler(BaseHTTPRequestHandler):
    """Answers every GET with the vendor's current state and records the path."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        server: Any = self.server
        vendor: ReleaseVendor = server.vendor
        vendor.received.append(self.path)
        payload = json.dumps(
            {
                "tag_name": vendor.state["tag"],
                "name": vendor.state["tag"],
                "body": vendor.state["notes"],
                "html_url": vendor.state["url"],
            }
        ).encode()
        self.send_response(vendor.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Silence the request log; the tests assert on ``received`` instead."""
