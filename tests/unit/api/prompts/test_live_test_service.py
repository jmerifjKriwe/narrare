"""PROMPT-003 backend live-test service tests (CR-AUFG-07-16).

Tests the API-layer live-test orchestration with fakes for every
dependency (resolver, registry, preview, agent). No LLM, no DB, no
filesystem.

Key invariants proven here:
- Provider gating is enforced via the resolver's ``ConfigurationError``
  (no separate ``ProviderGate`` — mirrors writing endpoints).
- ``acknowledge_token_cost=False`` raises ``ValidationError`` (RULE-11).
- SSE frames contain meta / delta / done events terminated by ``[DONE]``.
- M2 (Core Spec Review): errors during streaming surface as SSE error
  events, not silent failures (RULE-11).
"""

from __future__ import annotations

import json

import pytest

from narrare.prompts.schemas import LiveTestRequest, LiveTestStartedResponse
from narrare_core.shared.errors import ConfigurationError, ValidationError
from tests.unit.api.prompts.live_test_service_fakes import (
    FailingAgent,
    make_live_test_service,
)

# ---------------------------------------------------------------------------
# validate_live_test
# ---------------------------------------------------------------------------


async def test_validate_live_test_returns_started_metadata() -> None:
    """Happy path: returns prompt_id, intent label, model_id, remaining budget."""
    from uuid import uuid4

    service = make_live_test_service()
    meta = await service.validate_live_test(
        prompt_id="writing/en/new_chapter",
        request=LiveTestRequest(
            variables={"language": "en"},
            acknowledge_token_cost=True,
        ),
        user_id=str(uuid4()),
    )
    assert meta.prompt_id == "writing/en/new_chapter"
    assert meta.intent == "writing"
    assert meta.model_id == "test-model"
    assert meta.rate_limit_remaining >= 0


async def test_validate_live_test_rejects_unacknowledged_cost() -> None:
    """acknowledge_token_cost=False → ValidationError before any provider call."""
    from uuid import uuid4

    service = make_live_test_service()
    with pytest.raises(ValidationError, match="acknowledge_token_cost"):
        await service.validate_live_test(
            prompt_id="writing/en/new_chapter",
            request=LiveTestRequest(
                variables={"language": "en"},
                acknowledge_token_cost=False,
            ),
            user_id=str(uuid4()),
        )


async def test_validate_live_test_raises_configuration_error_without_provider() -> None:
    """No provider configured → ConfigurationError propagates (the gate)."""
    from uuid import uuid4

    service = make_live_test_service(resolver_should_fail=True)
    with pytest.raises(ConfigurationError):
        await service.validate_live_test(
            prompt_id="writing/en/new_chapter",
            request=LiveTestRequest(acknowledge_token_cost=True),
            user_id=str(uuid4()),
        )


# ---------------------------------------------------------------------------
# stream_live_test
# ---------------------------------------------------------------------------


async def test_stream_live_test_yields_sse_frames() -> None:
    """Happy path: full meta + delta + done frames, terminated by [DONE]."""
    from uuid import uuid4

    service = make_live_test_service(chunks=["hello ", "world"])
    user_id = str(uuid4())
    metadata = await service.validate_live_test(
        prompt_id="writing/en/new_chapter",
        request=LiveTestRequest(
            variables={"language": "en"},
            acknowledge_token_cost=True,
        ),
        user_id=user_id,
    )
    frames: list[str] = []
    async for frame in service.stream_live_test(
        prompt_id="writing/en/new_chapter",
        request=LiveTestRequest(
            variables={"language": "en"},
            acknowledge_token_cost=True,
        ),
        user_id=user_id,
        metadata=metadata,
    ):
        frames.append(frame)

    joined = "".join(frames)
    assert "event: meta" in joined
    meta_payload = json.loads(frames[0].split("data: ", maxsplit=1)[1])
    assert meta_payload["prompt_id"] == "writing/en/new_chapter"
    assert meta_payload["intent"] == "writing"
    assert meta_payload["model_id"] == "test-model"
    assert meta_payload["rate_limit_remaining"] >= 0
    assert "hello" in joined
    assert "world" in joined
    assert "event: done" in joined
    assert joined.strip().endswith("[DONE]")


async def test_stream_live_test_surfaces_errors_as_sse_error_event() -> None:
    """M2 invariant: errors during streaming → SSE error event, not silent failure."""
    from uuid import uuid4

    service = make_live_test_service(
        agent=FailingAgent(RuntimeError("model exploded")),
    )
    frames: list[str] = []
    async for frame in service.stream_live_test(
        prompt_id="writing/en/new_chapter",
        request=LiveTestRequest(acknowledge_token_cost=True),
        user_id=str(uuid4()),
        metadata=LiveTestStartedResponse(
            prompt_id="writing/en/new_chapter",
            intent="writing",
            model_id="test-model",
            rate_limit_remaining=4,
        ),
    ):
        frames.append(frame)

    joined = "".join(frames)
    assert "event: error" in joined
    assert "model exploded" in joined
    # The stream must terminate cleanly even after an error.
    assert "[DONE]" in joined


async def test_stream_live_test_raises_configuration_error_without_provider() -> None:
    """No provider → ConfigurationError before SSE starts (so router maps to HTTP status)."""
    from uuid import uuid4

    service = make_live_test_service(resolver_should_fail=True)
    with pytest.raises(ConfigurationError):
        async for _frame in service.stream_live_test(
            prompt_id="writing/en/new_chapter",
            request=LiveTestRequest(acknowledge_token_cost=True),
            user_id=str(uuid4()),
            metadata=LiveTestStartedResponse(
                prompt_id="writing/en/new_chapter",
                intent="writing",
                model_id="test-model",
                rate_limit_remaining=4,
            ),
        ):
            pass
