"""Unit tests for writing helpers — validation and feedback utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.writing._helpers import record_feedback, validate_generation_input

if TYPE_CHECKING:
    from narrare.writing.models import GenerationRequest
    from narrare.writing.schemas import GenerateRequest
    from narrare_core.memory.protocols import FeedbackCollector

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeGenerateRequest:
    def __init__(
        self, *, prompt: str | None = None, outline: str | None = None, auto_continue: bool = False
    ) -> None:
        self.prompt = prompt
        self.outline = outline
        self.auto_continue = auto_continue


class _FakeGenerationRequest:
    def __init__(self) -> None:
        self.id = uuid4()
        self.user_id = uuid4()
        self.novel_id = uuid4()


class _FakeFeedbackCollector:
    def __init__(self) -> None:
        self.recorded: list[object] = []

    async def record(self, event: object) -> None:
        self.recorded.append(event)


# ---------------------------------------------------------------------------
# Tests: validate_generation_input
# ---------------------------------------------------------------------------


class TestValidateGenerationInput:
    def test_valid_prompt_passes(self) -> None:
        req = _FakeGenerateRequest(prompt="Write a scene")
        validate_generation_input(cast("GenerateRequest", req))

    def test_valid_outline_passes(self) -> None:
        req = _FakeGenerateRequest(outline="Chapter outline")
        validate_generation_input(cast("GenerateRequest", req))

    def test_valid_auto_continue_passes(self) -> None:
        req = _FakeGenerateRequest(auto_continue=True)
        validate_generation_input(cast("GenerateRequest", req))

    def test_all_none_raises(self) -> None:
        req = _FakeGenerateRequest()
        with pytest.raises(Exception, match="At least one"):
            validate_generation_input(cast("GenerateRequest", req))

    def test_empty_prompt_without_others_raises(self) -> None:
        req = _FakeGenerateRequest(prompt="")
        with pytest.raises(Exception, match="At least one"):
            validate_generation_input(cast("GenerateRequest", req))


# ---------------------------------------------------------------------------
# Tests: record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    @pytest.mark.asyncio
    async def test_records_event_when_service_available(self) -> None:
        feedback = _FakeFeedbackCollector()
        request_model = _FakeGenerationRequest()
        await record_feedback(
            cast("FeedbackCollector", feedback), cast("GenerationRequest", request_model), "accept"
        )
        assert len(feedback.recorded) == 1

    @pytest.mark.asyncio
    async def test_noop_when_service_none(self) -> None:
        request_model = _FakeGenerationRequest()
        await record_feedback(None, cast("GenerationRequest", request_model), "reject")

    @pytest.mark.asyncio
    async def test_passes_modified_text(self) -> None:
        feedback = _FakeFeedbackCollector()
        request_model = _FakeGenerationRequest()
        await record_feedback(
            cast("FeedbackCollector", feedback),
            cast("GenerationRequest", request_model),
            "modify",
            modified_text="edited version",
        )
        assert len(feedback.recorded) == 1
