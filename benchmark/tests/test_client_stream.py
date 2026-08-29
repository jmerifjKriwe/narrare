"""Unit tests for ``benchmark.client`` — SSE streaming behavior.

Covers the streaming half of the client contract against a scripted
``httpx.MockTransport`` backend (no network): line collection via
``benchmark.sse.collect_events``, single 401 → refresh → reopen on
pre-stream auth errors, and pre-stream error statuses (429) raising
without a refresh attempt (map §6 + OPEN-4).
"""

from __future__ import annotations

import httpx
import pytest

from benchmark.client import ApiError
from benchmark.sse import SseItem, SseSentinel, collect_events
from benchmark.tests.client_helpers import (
    FLAVOR_A_BYTES,
    LOGIN_PATH,
    REFRESH_PATH,
    SSE_RESPONSE_HEADERS,
    STREAM_PATH,
    RecordedCall,
    ScriptedApi,
    make_client,
    token_response,
)


def test_stream_collects_sse_lines_from_mock_transport() -> None:
    api = ScriptedApi()

    def responder(index: int, call: RecordedCall) -> httpx.Response:
        if index == 0:
            return token_response("acc-1", "ref-1")
        assert call.path == STREAM_PATH
        return httpx.Response(200, headers=SSE_RESPONSE_HEADERS, content=FLAVOR_A_BYTES)

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    with client.stream("POST", STREAM_PATH, json={"chapter_ids": []}) as lines:
        result = collect_events(lines)

    assert len(result.events) == 1
    assert isinstance(result.events[0], SseItem)
    assert result.events[0].payload["expression"] == "Klaus betrat die Bibliothek."
    assert isinstance(result.terminal, SseSentinel)


def test_stream_401_refreshes_then_retries_stream() -> None:
    api = ScriptedApi()

    def responder(index: int, call: RecordedCall) -> httpx.Response:
        if index == 0:
            return token_response("acc-1", "ref-1")
        if call.path == REFRESH_PATH:
            return token_response("acc-2", "ref-2")
        if call.authorization == "Bearer acc-1":
            return httpx.Response(401, json={"detail": "Invalid or expired token"})
        return httpx.Response(200, headers=SSE_RESPONSE_HEADERS, content=FLAVOR_A_BYTES)

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    with client.stream("POST", STREAM_PATH) as lines:
        result = collect_events(lines)

    assert isinstance(result.terminal, SseSentinel)
    assert api.paths() == [
        f"POST {LOGIN_PATH}",
        f"POST {STREAM_PATH}",
        f"POST {REFRESH_PATH}",
        f"POST {STREAM_PATH}",
    ]


def test_stream_pre_stream_error_status_raises_without_refresh() -> None:
    api = ScriptedApi()

    def responder(index: int, call: RecordedCall) -> httpx.Response:
        if index == 0:
            return token_response("acc-1", "ref-1")
        assert call.path == STREAM_PATH
        return httpx.Response(429, json={"detail": "Rate limit exceeded"})

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    with pytest.raises(ApiError) as excinfo, client.stream("POST", STREAM_PATH) as lines:
        collect_events(lines)

    assert excinfo.value.status == 429  # status is the signal (map OPEN-4)
    assert api.paths() == [f"POST {LOGIN_PATH}", f"POST {STREAM_PATH}"]


def test_stream_second_401_raises_without_second_refresh() -> None:
    api = ScriptedApi()

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == REFRESH_PATH:
            return token_response("acc-2", "ref-2")
        if call.path == LOGIN_PATH:
            return token_response("acc-1", "ref-1")
        return httpx.Response(401, json={"detail": "Invalid or expired token"})

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    with pytest.raises(ApiError) as excinfo, client.stream("POST", STREAM_PATH) as lines:
        collect_events(lines)

    assert excinfo.value.status == 401
    assert api.paths() == [
        f"POST {LOGIN_PATH}",
        f"POST {STREAM_PATH}",
        f"POST {REFRESH_PATH}",
        f"POST {STREAM_PATH}",
    ]
