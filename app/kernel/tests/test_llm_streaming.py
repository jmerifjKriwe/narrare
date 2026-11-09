"""The error frame: the one SSE frame a stream that cannot run ends with.

The bytes are the contract — the routers yield this exact shape and the web
reader parses it back into code, model and detail — so every test here pins
the literal frame, never a parsed approximation of it.
"""

import pytest

from app.kernel.llm.contract import ModelNotFoundError, ProviderAuthError, error_code
from app.kernel.llm.streaming import error_events, error_frame, failure_frame


def test_a_missing_model_gets_its_own_frame() -> None:
    assert error_frame("model-not-found", model="glm-5.3") == (
        'event: error\ndata: {"code": "model-not-found", "model": "glm-5.3"}\n\n'
    )


def test_a_frame_without_parameters_carries_its_code_alone() -> None:
    assert error_frame("prompt-refused") == ('event: error\ndata: {"code": "prompt-refused"}\n\n')


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("key-unavailable", 'event: error\ndata: {"code": "key-unavailable"}\n\n'),
        ("prompt-refused", 'event: error\ndata: {"code": "prompt-refused"}\n\n'),
    ],
)
async def test_the_pre_call_endings_yield_exactly_their_frame(code: str, expected: str) -> None:
    """The two refusals a stream can meet before any provider call are coded."""
    assert [frame async for frame in error_events(code)] == [expected]


async def test_the_default_ending_says_unknown_never_prose() -> None:
    """No code given, no facts to name: the frame says so in one code."""
    assert [frame async for frame in error_events()] == [
        'event: error\ndata: {"code": "unknown"}\n\n'
    ]


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ModelNotFoundError("glm-5.3"), "model-not-found"),
        (
            ProviderAuthError("the endpoint refused the credential (401): no such key"),
            "provider-auth",
        ),
        (RuntimeError("the provider died"), "unknown"),
        (ValueError("a usage frame that breaks its own contract"), "unknown"),
    ],
)
def test_every_failure_maps_to_its_wire_code(failure: Exception, expected: str) -> None:
    """The two typed failures are the whole closed vocabulary; the rest is unknown."""
    assert error_code(failure) == expected


def test_an_unclassified_failure_is_the_unknown_frame_with_its_detail() -> None:
    """What the reader cannot translate still rides along, behind the code."""
    assert failure_frame(RuntimeError("the provider died")) == (
        'event: error\ndata: {"code": "unknown", "detail": "the provider died"}\n\n'
    )


def test_a_missing_model_frame_names_the_model_and_the_detail() -> None:
    """The typed failure carries what the sentence needs and what it answered from."""
    frame = failure_frame(ModelNotFoundError("glm-5.3"))
    assert frame == (
        'event: error\ndata: {"code": "model-not-found", "model": "glm-5.3",'
        ' "detail": "the endpoint does not serve the model \'glm-5.3\'"}\n\n'
    )


def test_a_refused_credential_frame_carries_the_refusal_detail() -> None:
    message = "the endpoint refused the credential (401): Incorrect API key provided"
    frame = failure_frame(ProviderAuthError(message))
    assert frame == (f'event: error\ndata: {{"code": "provider-auth", "detail": "{message}"}}\n\n')


def test_a_silent_failure_yields_the_bare_unknown_frame() -> None:
    """An exception with nothing to say sends the code, never an empty detail."""
    assert failure_frame(Exception()) == 'event: error\ndata: {"code": "unknown"}\n\n'
