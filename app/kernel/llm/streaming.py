"""Close audited event generators before the response releases their resources."""

from collections.abc import AsyncGenerator, Mapping  # noqa: TC003
from typing import TYPE_CHECKING

from anyio import CancelScope
from starlette.responses import StreamingResponse

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send


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
