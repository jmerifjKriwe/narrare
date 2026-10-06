"""Usage attribution middleware — STATS-002 / ADR-093 D3.

Pure ASGI middleware that binds the ``usage_novel_id`` ContextVar
(:mod:`narrare_core.llm.usage_events`) from the ``/api/v1/novels/{uuid}``
path prefix before the request enters the app, so every LLM call emitted
while the request is in flight carries novel attribution.

Race safety: the vars are set before ``await self._app(...)`` and never
reset afterwards — per-request isolation comes from context-copy at task
creation (uvicorn creates one task per request/response cycle; the same
precedent the structlog contextvars binding in ``_app/middleware.py``
relies on).

Non-http scopes (websocket, lifespan) pass through untouched — websocket
attribution is a separate concern (STATS-002 Task 12).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID

from narrare_core.llm.usage_events import usage_novel_id

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

_NOVEL_PATH_PATTERN = re.compile(
    r"^/api/v1/novels/"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    r"(?:/|$)"
)


class UsageAttributionMiddleware:
    """Pure ASGI (http scope only): sets ``usage_novel_id`` from path prefix.

    * Novel route path (``/api/v1/novels/{uuid}`` or any subpath) → var set
      to that UUID.
    * Any other http path, or a malformed UUID → var set to ``None``
      (overwrites stale values from a reused context).
    * Non-http scopes → passed through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        match = _NOVEL_PATH_PATTERN.match(scope["path"])
        novel_id: UUID | None = UUID(match.group(1)) if match else None
        usage_novel_id.set(novel_id)
        await self._app(scope, receive, send)
