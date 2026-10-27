"""ASGI disconnect probes for the real streaming response and database audits."""

from collections.abc import AsyncIterator  # noqa: TC003
from typing import TYPE_CHECKING

import pytest
from anyio import Event, sleep_forever
from starlette.requests import ClientDisconnect

from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta, Usage
from app.kernel.llm.fake import FakeProvider

if TYPE_CHECKING:
    from starlette.responses import StreamingResponse
    from starlette.types import Message


class StreamProbeProvider(FakeProvider):
    """Report known text and usage, then complete, fail, or wait for cancellation."""

    def __init__(self, *, fail: bool = False, waiting: Event | None = None) -> None:
        """Choose how the provider ends after reporting its partial answer."""
        self.fail = fail
        self.waiting = waiting

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Expose cancellation while awaiting the provider as well as at a yield."""
        yield Delta("partial")
        yield Usage(3, 2)
        if self.fail:
            raise RuntimeError("provider failed")
        if self.waiting is not None:
            self.waiting.set()
            await sleep_forever()
        yield DONE


async def interrupt_response(
    response: StreamingResponse,
    *,
    spec_version: str,
    frame: str,
    disconnected: Event | None = None,
) -> None:
    """Disconnect through ASGI receive or send; return only after cleanup finishes."""
    disconnected = disconnected if disconnected is not None else Event()

    async def receive() -> Message:
        """Wait until the send or provider probe reaches the interruption point."""
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        """Stop on the chosen SSE frame without resuming the suspended iterator."""
        if frame and frame.encode() in message.get("body", b""):
            if spec_version == "2.4":
                raise OSError("client disconnected")
            disconnected.set()
            await sleep_forever()

    scope = {"type": "http", "asgi": {"spec_version": spec_version}}
    if spec_version == "2.4":
        with pytest.raises(ClientDisconnect):
            await response(scope, receive, send)
    else:
        await response(scope, receive, send)
