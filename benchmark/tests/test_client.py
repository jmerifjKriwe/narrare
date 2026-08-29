"""Unit tests for ``benchmark.client`` — auth flow, error shapes, REST.

All requests run against ``httpx.MockTransport`` via a scripted recording
backend — no network. Exercises the verified auth map
(benchmark/docs/api-surface.md §2: register/login → TokenResponse body,
Bearer injection, refresh via JSON body, single 401 → refresh → retry)
and the error-shape conventions (§1: domain ``{"detail", "code"}``,
FastAPI 422 list detail, unhandled 500, status-only 429). Streaming
behavior lives in ``test_client_stream.py``.
"""

from __future__ import annotations

import httpx
import pytest

from benchmark.client import ApiError, BenchmarkClient, TokenPair
from benchmark.tests.client_helpers import (
    LOGIN_PATH,
    ME_PATH,
    REFRESH_PATH,
    REGISTER_PATH,
    RecordedCall,
    ScriptedApi,
    make_client,
    token_response,
)

# --- register / login -------------------------------------------------------


def test_register_sends_register_schema_and_stores_tokens() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: token_response("acc-1", "ref-1", status=201))
    client = make_client(api)

    tokens = client.register("benchmark@example.com", "secret-password", "Benchmark Runner")

    assert isinstance(tokens, TokenPair)
    assert tokens == TokenPair(
        access_token="acc-1", refresh_token="ref-1", token_type="bearer", expires_in=3600
    )
    assert api.paths() == [f"POST {REGISTER_PATH}"]
    call = api.calls[0]
    assert call.body == {
        "email": "benchmark@example.com",
        "password": "secret-password",
        "display_name": "Benchmark Runner",
    }


def test_login_sends_login_schema_and_stores_tokens() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: token_response("acc-1", "ref-1"))
    client = make_client(api)

    tokens = client.login("benchmark@example.com", "secret-password")

    assert tokens.access_token == "acc-1"
    assert api.paths() == [f"POST {LOGIN_PATH}"]
    assert api.calls[0].body == {
        "email": "benchmark@example.com",
        "password": "secret-password",
    }


def test_register_and_login_send_no_authorization_header() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: token_response("acc-1", "ref-1"))
    client = make_client(api)

    client.login("benchmark@example.com", "secret-password")
    client.login("benchmark@example.com", "secret-password")  # re-login with tokens held

    assert all(call.authorization is None for call in api.calls)


# --- error-shape parsing (map §1) --------------------------------------------


def test_domain_error_shape_detail_and_code_parsed() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            409, json={"detail": "Email already registered", "code": "CONFLICT"}
        )
    )
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        client.register("dup@example.com", "secret-password")

    err = excinfo.value
    assert err.status == 409
    assert err.detail == "Email already registered"
    assert err.code == "CONFLICT"
    assert "409" in str(err) and "CONFLICT" in str(err)


def test_validation_422_list_detail_rendered() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "email"],
                        "msg": "value is not a valid email",
                        "type": "value_error",
                    },
                    {
                        "loc": ["body", "password"],
                        "msg": "shorter than minimum",
                        "type": "value_error",
                    },
                ]
            },
        )
    )
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        client.register("nope", "x")

    assert excinfo.value.status == 422
    assert excinfo.value.code is None
    assert "value is not a valid email" in excinfo.value.detail
    assert "shorter than minimum" in excinfo.value.detail


def test_unhandled_500_shape_without_code() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: httpx.Response(500, json={"detail": "Internal server error"}))
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        client.request("GET", ME_PATH)

    assert excinfo.value.status == 500
    assert excinfo.value.detail == "Internal server error"
    assert excinfo.value.code is None


def test_non_json_error_body_falls_back_to_text() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: httpx.Response(502, text="bad gateway from proxy"))
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        client.request("GET", ME_PATH)

    assert excinfo.value.status == 502
    assert excinfo.value.detail == "bad gateway from proxy"
    assert excinfo.value.code is None


def test_empty_error_body_falls_back_to_placeholder() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: httpx.Response(502, content=b""))
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        client.request("GET", ME_PATH)

    assert excinfo.value.status == 502
    assert excinfo.value.detail == "<empty body>"
    assert excinfo.value.code is None


# --- auth header injection ----------------------------------------------------


def test_request_injects_bearer_after_login() -> None:
    api = ScriptedApi()
    seen: list[str | None] = []

    def responder(index: int, call: RecordedCall) -> httpx.Response:
        if index == 0:
            return token_response("acc-1", "ref-1")
        seen.append(call.authorization)
        return httpx.Response(200, json={"id": "user-1"})

    api.respond_with(responder)
    client = make_client(api)

    client.login("benchmark@example.com", "secret-password")
    client.request("GET", ME_PATH)

    assert seen == ["Bearer acc-1"]


def test_request_without_tokens_sends_no_header_and_raises_401() -> None:
    api = ScriptedApi()
    api.respond_with(lambda _i, _c: httpx.Response(401, json={"detail": "Not authenticated"}))
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        client.request("GET", ME_PATH)

    assert excinfo.value.status == 401
    assert api.paths() == [f"GET {ME_PATH}"]  # no refresh attempted


# --- single 401 → refresh → retry ---------------------------------------------


def test_401_refreshes_and_retries_exactly_once() -> None:
    api = ScriptedApi()

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == LOGIN_PATH:
            return token_response("acc-1", "ref-1")
        if call.path == REFRESH_PATH:
            assert call.body == {"refresh_token": "ref-1"}
            return token_response("acc-2", "ref-2")
        if call.authorization == "Bearer acc-1":
            return httpx.Response(401, json={"detail": "Invalid or expired token"})
        assert call.authorization == "Bearer acc-2"  # retried with fresh token
        return httpx.Response(200, json={"id": "user-1"})

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    response = client.request("GET", ME_PATH)

    assert response.status_code == 200
    assert api.paths() == [
        f"POST {LOGIN_PATH}",
        f"GET {ME_PATH}",
        f"POST {REFRESH_PATH}",
        f"GET {ME_PATH}",
    ]


def test_second_401_raises_without_second_refresh() -> None:
    api = ScriptedApi()

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == LOGIN_PATH:
            return token_response("acc-1", "ref-1")
        if call.path == REFRESH_PATH:
            return token_response("acc-2", "ref-2")
        return httpx.Response(401, json={"detail": "Invalid or expired token"})

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    with pytest.raises(ApiError) as excinfo:
        client.request("GET", ME_PATH)

    assert excinfo.value.status == 401
    assert api.paths() == [
        f"POST {LOGIN_PATH}",
        f"GET {ME_PATH}",
        f"POST {REFRESH_PATH}",
        f"GET {ME_PATH}",
    ]  # one refresh, one retry, then raise


def test_refresh_failure_raises_and_propagates() -> None:
    api = ScriptedApi()

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == LOGIN_PATH:
            return token_response("acc-1", "ref-1")
        if call.path == REFRESH_PATH:
            return httpx.Response(401, json={"detail": "No refresh token provided"})
        return httpx.Response(401, json={"detail": "Invalid or expired token"})

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    with pytest.raises(ApiError) as excinfo:
        client.request("GET", ME_PATH)

    assert excinfo.value.status == 401
    assert excinfo.value.detail == "No refresh token provided"
    assert api.paths() == [f"POST {LOGIN_PATH}", f"GET {ME_PATH}", f"POST {REFRESH_PATH}"]


def test_manual_refresh_rotates_tokens() -> None:
    api = ScriptedApi()

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == LOGIN_PATH:
            return token_response("acc-1", "ref-1")
        return token_response("acc-2", "ref-2")

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    tokens = client.refresh()

    assert tokens.access_token == "acc-2"
    assert tokens.refresh_token == "ref-2"
    assert api.calls[0].path == LOGIN_PATH  # login seeded the tokens
    assert api.calls[1].body == {"refresh_token": "ref-1"}


# --- timeout -------------------------------------------------------------------


def test_timeout_from_constructor_reaches_http_layer() -> None:
    api = ScriptedApi()
    client = make_client(api, timeout_seconds=7.5)

    assert client.http_timeout.connect == 7.5
    assert client.http_timeout.read == 7.5


def test_network_timeout_propagates_as_httpx_exception() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out")

    client = BenchmarkClient("http://api.test", 5.0, transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.ConnectTimeout):
        client.request("GET", ME_PATH)


# --- generic request passthrough -------------------------------------------------


def test_request_json_payload_round_trip() -> None:
    api = ScriptedApi()
    payload_seen: list[object] = []

    def responder(index: int, call: RecordedCall) -> httpx.Response:
        if index == 0:
            return token_response("acc-1", "ref-1")
        payload_seen.append(call.body)
        return httpx.Response(200, json=call.body)

    api.respond_with(responder)
    client = make_client(api)
    client.login("benchmark@example.com", "secret-password")

    response = client.request("POST", "/api/v1/novels", json={"title": "Der Testroman"})

    assert response.status_code == 200
    assert payload_seen == [{"title": "Der Testroman"}]
