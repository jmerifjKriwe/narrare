"""Shared scripted httpx backend for ``benchmark.client`` tests.

Provides the recording ``MockTransport`` backend and client factory used
by ``test_client.py`` (auth/REST) and ``test_client_stream.py`` (SSE
streaming). Plain helpers — no fixtures, no network.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from benchmark.client import BenchmarkClient, TokenPair

BASE_URL = "http://api.test"
ME_PATH = "/api/v1/auth/me"
REGISTER_PATH = "/api/v1/auth/register"
LOGIN_PATH = "/api/v1/auth/login"
REFRESH_PATH = "/api/v1/auth/refresh"
STREAM_PATH = "/api/v1/planning/timeline/novel-1/extract"

SSE_RESPONSE_HEADERS = {"content-type": "text/event-stream"}

FLAVOR_A_BYTES = (
    b'data: {"id":"ev-1","expression":"Klaus betrat die Bibliothek.",'
    b'"confidence":0.92}\n\n'
    b"data: [DONE]\n\n"
)


@dataclass
class RecordedCall:
    """One request seen by the mock backend.

    ``params`` (Task 9) records the query string so GET drivers can have
    their query payloads pinned (pagination, search q, max_results, …).
    """

    method: str
    path: str
    authorization: str | None
    body: object
    params: dict[str, str] | None = None


Responder = Callable[[int, RecordedCall], httpx.Response]


class ScriptedApi:
    """MockTransport backend: records calls, answers via a set responder."""

    def __init__(self) -> None:
        self.calls: list[RecordedCall] = []
        self._responder: Responder = self._unscripted

    @staticmethod
    def _unscripted(index: int, call: RecordedCall) -> httpx.Response:
        return httpx.Response(
            500,
            json={
                "detail": f"unscripted call #{index}: {call.method} {call.path}",
                "code": "UNSCRIPTED",
            },
        )

    def respond_with(self, responder: Responder) -> None:
        self._responder = responder

    def handler(self, request: httpx.Request) -> httpx.Response:
        request.read()
        raw_body: object = None
        if request.content:
            raw_body = json.loads(request.content)
        call = RecordedCall(
            method=request.method,
            path=request.url.path,
            authorization=request.headers.get("authorization"),
            body=raw_body,
            params=dict(request.url.params),
        )
        self.calls.append(call)
        return self._responder(len(self.calls) - 1, call)

    def paths(self) -> list[str]:
        return [f"{call.method} {call.path}" for call in self.calls]


def token_response(access: str, refresh: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )


def make_client(
    api: ScriptedApi,
    timeout_seconds: float = 5.0,
    *,
    access_token: str | None = None,
) -> BenchmarkClient:
    """Build a client on the scripted backend.

    ``access_token`` seeds held tokens via the client's ``tokens``
    constructor DI — a scripted login would pollute the recorded call
    sequences and the ingest event sink (ingest tests pin post-auth
    sequences; provisioning owns the real login upstream).
    """
    tokens = (
        TokenPair(
            access_token=access_token,
            refresh_token="ref-seeded",
            token_type="bearer",
            expires_in=3600,
        )
        if access_token is not None
        else None
    )
    return BenchmarkClient(
        BASE_URL,
        timeout_seconds,
        tokens=tokens,
        transport=httpx.MockTransport(api.handler),
    )
