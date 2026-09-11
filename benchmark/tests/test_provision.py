"""Unit tests for ``benchmark.provision`` — idempotent setup-path provisioning.

All flows run against the scripted MockTransport backend (``client_helpers``)
via the real ``BenchmarkClient`` — no network. Endpoint SEQUENCE, register-
conflict login fallback, ``Step4ProviderRequest`` payload fidelity,
already-configured short-circuit (map §2.5), wizard-state shape (map §3),
error propagation, and secret redaction are pinned here. Sequence truth:
benchmark/docs/api-surface.md §2/§3.
"""

from __future__ import annotations

from typing import Any, Final

import httpx
import pytest

from benchmark.client import ApiError
from benchmark.config import (
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.provision import ProvisioningError, ProvisionOutcome, provision
from benchmark.tests.client_helpers import (
    LOGIN_PATH,
    ME_PATH,
    REFRESH_PATH,
    REGISTER_PATH,
    RecordedCall,
    Responder,
    ScriptedApi,
    make_client,
    token_response,
)

STEP4_PATH: Final[str] = "/api/v1/setup/validate/step-4"
COMPLETE_PATH: Final[str] = "/api/v1/setup/complete"
SECRET_KEY: Final[str] = "sk-benchmark-secret-42"

FRESH_SEQUENCE: Final[list[str]] = [
    f"POST {REGISTER_PATH}",
    f"GET {ME_PATH}",
    f"POST {STEP4_PATH}",
    f"POST {COMPLETE_PATH}",
]
EXISTS_SEQUENCE: Final[list[str]] = [
    f"POST {REGISTER_PATH}",
    f"POST {LOGIN_PATH}",
    f"GET {ME_PATH}",
    f"POST {STEP4_PATH}",
    f"POST {COMPLETE_PATH}",
]
ALREADY_SEQUENCE: Final[list[str]] = [
    f"POST {REGISTER_PATH}",
    f"POST {LOGIN_PATH}",
    f"GET {ME_PATH}",
]

EXPECTED_STEP4_BODY: Final[dict[str, str]] = {
    "provider": "anthropic",
    "api_key": SECRET_KEY,
    "model": "claude-sonnet-4-5",
    "ollama_url": "http://localhost:11434",
    "zai_endpoint": "general",
}
EXPECTED_WIZARD_STATE: Final[dict[str, object]] = {
    "project_name": "kb-benchmark",
    "writing_language": "de",
    "autosave_interval": 30,
    "title": "KB Benchmark Corpus",
    "author": "",
    "genre": "",
    "logline": "",
    "story_structure": "three_act",
    "tone": "dramatic",
    "starter": "blank",
    "import_path": None,
    "provider": "anthropic",
    "api_key": SECRET_KEY,
    "model": "claude-sonnet-4-5",
    "ollama_url": "http://localhost:11434",
    "zai_endpoint": "general",
    "skip_provider": False,
}


def make_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        stack=StackConfig("narrare-benchmark", 18080, 18180),
        api=ApiConfig(None, 60.0),
        auth=AuthConfig("benchmark@example.com", "benchmark-password"),
        llm=LlmConfig(
            "anthropic", SECRET_KEY, "claude-sonnet-4-5", "http://localhost:11434", "general"
        ),
        run=RunConfig(["clean"], ["incremental"], False, []),
    )


def wizard_responder(
    *,
    register_status: int = 201,
    has_providers: bool = False,
    step4_status: int = 200,
    step4_body: dict[str, object] | None = None,
    complete_status: int = 200,
    complete_body: dict[str, object] | None = None,
) -> Responder:
    """Build a responder for the standard provisioning flows (map §2/§3 shapes)."""

    def respond(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == REGISTER_PATH:
            if register_status == 201:
                return token_response("acc-1", "ref-1", status=201)
            return httpx.Response(
                register_status, json={"detail": "Email already registered", "code": "CONFLICT"}
            )
        if call.path == LOGIN_PATH:
            return token_response("acc-2", "ref-2")
        if call.path == ME_PATH:
            return httpx.Response(200, json={"id": "user-1", "has_providers": has_providers})
        if call.path == STEP4_PATH:
            body = (
                step4_body
                if step4_body is not None
                else {"valid": True, "validation_message": "ok"}
            )
            return httpx.Response(step4_status, json=body)
        if call.path == COMPLETE_PATH:
            return httpx.Response(
                complete_status, json=complete_body if complete_body else complete_ok().json()
            )
        raise AssertionError(f"unexpected call: {call.method} {call.path}")

    return respond


def complete_ok() -> httpx.Response:
    return httpx.Response(
        200, json={"novel_id": "novel-1", "redirect_to": "/novel/novel-1", "message": "done"}
    )


def test_fresh_user_walks_documented_sequence() -> None:
    api = ScriptedApi()
    api.respond_with(wizard_responder())
    client = make_client(api)

    outcome = provision(client, make_config())

    assert isinstance(outcome, ProvisionOutcome)
    assert outcome == ProvisionOutcome(already_configured=False, novel_id="novel-1")
    assert api.paths() == FRESH_SEQUENCE
    assert api.calls[3].authorization == "Bearer acc-1"  # complete requires Bearer (map §3.6)


def test_step4_payload_mirrors_config_llm_field_for_field() -> None:
    api = ScriptedApi()
    api.respond_with(wizard_responder())
    client = make_client(api)

    provision(client, make_config())

    assert api.calls[2].body == EXPECTED_STEP4_BODY  # dict equality: exact field set, no extras


def test_complete_payload_carries_full_wizard_state() -> None:
    api = ScriptedApi()
    api.respond_with(wizard_responder())
    client = make_client(api)

    provision(client, make_config())

    complete_call = api.calls[3]
    assert complete_call.body == {"state": EXPECTED_WIZARD_STATE}


@pytest.mark.parametrize("register_status", [400, 409])
def test_register_duplicate_falls_back_to_login(register_status: int) -> None:
    api = ScriptedApi()
    api.respond_with(wizard_responder(register_status=register_status))
    client = make_client(api)

    outcome = provision(client, make_config())

    assert outcome == ProvisionOutcome(already_configured=False, novel_id="novel-1")
    assert api.paths() == EXISTS_SEQUENCE
    assert all(api.calls[i].authorization is None for i in (0, 1))  # auth endpoints: no Bearer
    assert api.calls[1].body == {
        "email": "benchmark@example.com",
        "password": "benchmark-password",
    }


def test_unrelated_register_failure_propagates_without_login() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(500, json={"detail": "Internal server error"}),
    )
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        provision(client, make_config())

    assert excinfo.value.status == 500
    assert api.paths() == [f"POST {REGISTER_PATH}"]  # no login fallback, no wizard calls


def test_already_configured_short_circuits_before_wizard() -> None:
    api = ScriptedApi()
    api.respond_with(wizard_responder(register_status=409, has_providers=True))
    client = make_client(api)

    outcome = provision(client, make_config())

    assert outcome == ProvisionOutcome(already_configured=True, novel_id=None)
    assert api.paths() == ALREADY_SEQUENCE  # no step-4, no complete → no duplicate novel


def test_second_provision_call_does_not_complete_again() -> None:
    api = ScriptedApi()
    completes: list[RecordedCall] = []
    state = {"has_providers": False}

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == COMPLETE_PATH:
            completes.append(call)
            state["has_providers"] = True
            return complete_ok()
        if call.path == REGISTER_PATH:
            if completes:  # second run: the user already exists
                return httpx.Response(
                    409, json={"detail": "Email already registered", "code": "CONFLICT"}
                )
            return token_response("acc-1", "ref-1", status=201)
        if call.path == LOGIN_PATH:
            return token_response("acc-2", "ref-2")
        if call.path == ME_PATH:
            return httpx.Response(
                200, json={"id": "user-1", "has_providers": state["has_providers"]}
            )
        if call.path == STEP4_PATH:
            return httpx.Response(
                200,
                json={
                    "valid": True,
                    "provider": "anthropic",
                    "model": "x",
                    "validation_message": "ok",
                },
            )
        raise AssertionError(f"unexpected call: {call.method} {call.path}")

    api.respond_with(responder)
    client = make_client(api)

    first = provision(client, make_config())
    second = provision(client, make_config())

    assert first.already_configured is False
    assert second == ProvisionOutcome(already_configured=True, novel_id=None)
    assert len(completes) == 1  # exactly one complete across both runs (idempotent)


def test_step4_rejection_raises_provisioning_error() -> None:
    api = ScriptedApi()
    api.respond_with(
        wizard_responder(
            register_status=409,
            step4_body={
                "valid": False,
                "provider": "anthropic",
                "model": "claude-sonnet-4-5",
                "validation_message": "provider rejected the credentials",
            },
        )
    )
    client = make_client(api)

    with pytest.raises(ProvisioningError, match="provider rejected the credentials"):
        provision(client, make_config())

    assert api.paths() == EXISTS_SEQUENCE[:-1]  # complete never reached


def test_step4_http_error_propagates_as_api_error() -> None:
    api = ScriptedApi()

    def responder(_index: int, call: RecordedCall) -> httpx.Response:
        if call.path == REFRESH_PATH:
            return token_response("acc-fresh", "ref-fresh")
        return wizard_responder(
            register_status=409,
            step4_status=401,
            step4_body={"detail": "Invalid or expired token"},
        )(_index, call)

    api.respond_with(responder)
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        provision(client, make_config())

    assert excinfo.value.status == 401  # retried 401 after the single refresh (map §2)


def test_me_missing_has_providers_is_rejected() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, call: (
            token_response("acc-1", "ref-1", status=201)
            if call.path == REGISTER_PATH
            else httpx.Response(200, json={"id": "user-1"})
        )
    )
    client = make_client(api)

    with pytest.raises(ProvisioningError, match="has_providers"):
        provision(client, make_config())


@pytest.mark.parametrize("novel_id", [None, ""])
def test_complete_missing_novel_id_is_rejected(novel_id: str | None) -> None:
    body: dict[str, object] = {"redirect_to": "/dashboard", "message": "done"}
    if novel_id is not None:
        body["novel_id"] = novel_id
    api = ScriptedApi()
    api.respond_with(wizard_responder(complete_body=body))
    client = make_client(api)

    with pytest.raises(ProvisioningError, match="novel_id"):
        provision(client, make_config())


def test_complete_http_error_propagates_as_api_error() -> None:
    api = ScriptedApi()
    api.respond_with(
        wizard_responder(
            complete_status=409,
            complete_body={"detail": "Setup already completed", "code": "CONFLICT"},
        )
    )
    client = make_client(api)

    with pytest.raises(ApiError) as excinfo:
        provision(client, make_config())

    assert excinfo.value.status == 409
    assert excinfo.value.code == "CONFLICT"


@pytest.mark.parametrize(
    ("scenario", "kwargs"),
    [
        ("step4_http_error", {"step4_status": 422, "step4_body": {"detail": "invalid payload"}}),
        (
            "step4_rejected",
            {
                "step4_body": {
                    "valid": False,
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "validation_message": "rejected",
                }
            },
        ),
        ("complete_http_error", {"complete_status": 400, "complete_body": {"detail": "bad state"}}),
    ],
)
def test_api_key_never_reaches_error_strings(scenario: str, kwargs: dict[str, Any]) -> None:
    api = ScriptedApi()
    api.respond_with(wizard_responder(register_status=409, **kwargs))
    client = make_client(api)

    with pytest.raises((ApiError, ProvisioningError)) as excinfo:
        provision(client, make_config())

    assert SECRET_KEY not in str(excinfo.value), scenario
