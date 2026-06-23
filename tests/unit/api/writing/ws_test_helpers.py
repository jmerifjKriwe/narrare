"""Shared helpers for WebSocket writing-session unit tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import Mock


async def wait_for_gateway_calls(gateway: Mock, expected: int) -> None:
    """Wait until decoupled streaming tasks reach the model registry."""
    for _ in range(50):
        if gateway.stream.call_count >= expected:
            return
        await asyncio.sleep(0.02)
    assert gateway.stream.call_count >= expected


def stream_kwargs_for_intent(gateway: Mock, intent_value: str) -> dict[str, Any]:
    """Return kwargs for the first model-registry stream call by intent."""
    for call in gateway.stream.call_args_list:
        if call.kwargs["intent"].value == intent_value:
            return dict(call.kwargs)
    raise AssertionError(f"No stream call for intent {intent_value!r}")
