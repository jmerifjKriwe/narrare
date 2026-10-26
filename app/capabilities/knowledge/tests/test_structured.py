"""Structured answers: demand JSON, repair it, retry once, then fail with the reason.

Driven end to end through a stub provider — the one boundary a test may fake.
"""

from json import loads
from typing import TYPE_CHECKING, cast

import pytest

from app.capabilities.knowledge.structured import (
    AuditedCall,
    MalformedAnswerError,
    ask_structured,
)
from app.kernel.llm.contract import Delta, Usage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.kernel.llm.contract import CompletionEvent, CompletionRequest

SCHEMA: dict[str, object] = {"type": "array", "items": {"type": "string"}}


def parse_items(answer: str) -> list[str]:
    """The test's contract: a JSON array of strings, nothing else.

    A decode failure becomes the same actionable message a real parse function
    gives — the reason the user ends up reading in ``Job.error``.
    """
    try:
        data = cast("object", loads(answer))
    except ValueError as error:
        raise ValueError("not a JSON array of strings") from error
    if not isinstance(data, list):
        raise ValueError("not a JSON array of strings")
    items: list[str] = []
    for item in cast("list[object]", data):
        if not isinstance(item, str):
            raise ValueError("not a JSON array of strings")
        items.append(item)
    return items


class StubProvider:
    """A TextProvider that answers from a script and records what it was asked."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """One line, as the protocol asks."""
        return "stub"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Record the request and answer with the next scripted line."""
        self.requests.append(request)
        yield Delta(self.answers.pop(0))
        yield Usage(input_tokens=1, output_tokens=1)


def _audit_into(calls: list[AuditedCall]):
    async def audit(call: AuditedCall) -> None:
        calls.append(call)

    return audit


async def test_a_valid_answer_parses_with_one_call_and_one_audit() -> None:
    provider = StubProvider(['["a", "b"]'])
    calls: list[AuditedCall] = []

    assert await ask_structured(
        provider,
        "prompt",
        schema=SCHEMA,
        parse=parse_items,
        audit=_audit_into(calls),
    ) == ["a", "b"]

    assert len(provider.requests) == 1
    assert provider.requests[0].response_schema == SCHEMA
    assert len(calls) == 1
    assert calls[0].answer == '["a", "b"]'


async def test_a_repairable_answer_needs_no_retry() -> None:
    # Python's parser rejects the trailing comma; json_repair fixes it, and a
    # second provider call would be money for nothing.
    provider = StubProvider(['["a", "b",]'])
    calls: list[AuditedCall] = []

    assert await ask_structured(
        provider,
        "prompt",
        schema=SCHEMA,
        parse=parse_items,
        audit=_audit_into(calls),
    ) == ["a", "b"]

    assert len(provider.requests) == 1
    assert len(calls) == 1


async def test_an_unrepairable_answer_is_retried_once_with_the_error() -> None:
    provider = StubProvider(["this is prose, not JSON {{", '["a"]'])
    calls: list[AuditedCall] = []

    assert await ask_structured(
        provider,
        "prompt",
        schema=SCHEMA,
        parse=parse_items,
        audit=_audit_into(calls),
    ) == ["a"]

    assert len(provider.requests) == 2
    retry = provider.requests[1]
    assert retry.response_schema == SCHEMA
    assert len(retry.messages) == 2
    assert retry.messages[0].content == "prompt"
    assert "invalid" in retry.messages[1].content
    assert "not a JSON array of strings" in retry.messages[1].content
    assert len(calls) == 2


async def test_a_second_failure_raises_with_the_parse_reason() -> None:
    provider = StubProvider(["this is prose, not JSON {{", "and again, prose"])
    calls: list[AuditedCall] = []

    with pytest.raises(MalformedAnswerError) as raised:
        await ask_structured(
            provider,
            "prompt",
            schema=SCHEMA,
            parse=parse_items,
            audit=_audit_into(calls),
        )

    assert "not a JSON array of strings" in str(raised.value)
    assert len(provider.requests) == 2
    assert len(calls) == 2
