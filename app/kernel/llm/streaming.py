"""Close audited event generators before the response releases their resources.

The error frame is here too: the one frame a stream ends with when it cannot
deliver an answer, carrying a machine code (and whatever facts name the
cause) instead of the empty payload it used to be. The code is what the web
surfaces translate; the frames' exact bytes are pinned in
``app/kernel/tests/test_llm_streaming.py``.
"""

import json
from collections.abc import AsyncGenerator, Mapping  # noqa: TC003
from typing import TYPE_CHECKING

from anyio import CancelScope
from starlette.responses import StreamingResponse

from app.kernel.llm.contract import error_code

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send


def error_frame(code: str, **params: str) -> str:
    """The one frame a stream ends with when it cannot deliver an answer.

    ``event: error`` with a JSON payload that always names ``code`` — what
    the reader localizes — plus the facts that name the cause (``model`` for
    a missing model, ``detail`` for the provider's own message). The bytes
    are the contract: one line per field, the payload's keys in insertion
    order, exactly what the web reader parses back.
    """
    return f"event: error\ndata: {json.dumps({'code': code, **params})}\n\n"


def failure_frame(failure: BaseException) -> str:
    """The frame for a failure a consumer's ``except`` just caught.

    The code comes from the contract's closed vocabulary; a ``model``
    attribute (``ModelNotFoundError`` carries it) and the failure's own text,
    when it has one, ride along as the facts behind the sentence. One helper
    for writing and chat, so both routers spell the dead-provider frame the
    same way.
    """
    params: dict[str, str] = {}
    model = getattr(failure, "model", None)
    if isinstance(model, str):
        params["model"] = model
    detail = str(failure)
    if detail:
        params["detail"] = detail
    return error_frame(error_code(failure), **params)


async def error_events(code: str = "unknown", **params: str) -> AsyncGenerator[str]:
    """Yield exactly the one error frame: a stream's whole ending, coded."""
    yield error_frame(code, **params)


class FinalizingStreamingResponse(StreamingResponse):
    """Run the event generator's finalizer even when sending a frame fails."""

    def __init__(
        self,
        events: AsyncGenerator[str],
        *,
        media_type: str,
        headers: Mapping[str, str],
    ) -> None:
        """Keep the closable generator alongside Starlette's body iterator."""
        super().__init__(events, media_type=media_type, headers=headers)
        self._events = events

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Finish audit cleanup under both ASGI disconnect mechanisms."""
        try:
            await super().__call__(scope, receive, send)
        finally:
            with CancelScope(shield=True):
                await self._events.aclose()
