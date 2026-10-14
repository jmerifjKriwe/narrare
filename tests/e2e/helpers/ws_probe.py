"""WS observation probe for writing-session E2E specs (spec §4 helpers).

Extracted verbatim from ``tests/e2e/test_ws_ticket_session.py`` — the
ADR-084 acceptance gate — at the second consumer (Task 11, WRITE-005 spec):
the tracker owns every "what happened on the writing-session WebSocket"
concern so specs assert instead of wiring frame listeners.

The WebSocket upgrade itself is NOT interceptable by page.route() — it goes
through the Next.js rewrite to the API (empirically verified as part of the
ADR-084 acceptance gate: Next 16.3.1 rewrites DO proxy WS upgrades).
Assertions therefore observe the real network via ``page.on("websocket")``
frame events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from playwright.sync_api import Page, WebSocket

WS_SESSION_PATH = "/api/v1/writing/sessions/"


@dataclass
class SocketRecord:
    """One writing-session WebSocket and its observed text-frame traffic."""

    url: str
    raw: WebSocket | None = None
    frames: list[str] = field(default_factory=list)
    sent: list[str] = field(default_factory=list)


def append_text_frame(target: list[str], payload: bytes | str) -> None:
    """Record a WS frame payload, skipping binary frames (defensive)."""
    if isinstance(payload, str):
        target.append(payload)


def json_frame_types(frames: Iterable[str]) -> list[str]:
    """Parsed ``type`` field of every JSON frame in ``frames``."""
    types: list[str] = []
    for raw in frames:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict):
            types.append(str(msg.get("type")))
    return types


class WritingSocketTracker:
    """Collects writing-session WebSockets and their frames/sent messages.

    Filters out the Next.js/Turbopack HMR socket by URL path. Frame payloads
    are text (JSON) frames; binary frames arrive as bytes and are skipped.
    """

    def __init__(self, page: Page) -> None:
        self.sockets: list[SocketRecord] = []
        page.on("websocket", self._on_websocket)

    def _on_websocket(self, ws: WebSocket) -> None:
        if WS_SESSION_PATH not in ws.url:
            return
        record = SocketRecord(url=ws.url, raw=ws)
        self.sockets.append(record)
        ws.on("framereceived", lambda payload: append_text_frame(record.frames, payload))
        ws.on("framesent", lambda payload: append_text_frame(record.sent, payload))

    @property
    def urls(self) -> list[str]:
        return [record.url for record in self.sockets]

    def frame_types(self, index: int) -> list[str]:
        """Parsed ``type`` field of every server frame on socket ``index``."""
        return json_frame_types(self.sockets[index].frames)

    def sent_types(self, index: int) -> list[str]:
        """Parsed ``type`` field of every client frame on socket ``index``."""
        return json_frame_types(self.sockets[index].sent)
