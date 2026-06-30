"""Import and shape tests for WRITE-010 voice-check backend contracts."""

from __future__ import annotations

import inspect
from uuid import UUID, uuid4

import pytest

from narrare.analysis.contracts_voice_check import CharacterVoiceCheckerServiceProtocol
from narrare.analysis.schemas_voice_check import (
    FlaggedLineResponse,
    VoiceCheckRequest,
    VoiceCheckResponse,
    VoiceCheckResult,
    VoiceCheckStreamEvent,
)


def test_voice_check_protocol_exposes_chapter_scoped_check_signature() -> None:
    """Future router/service integration uses a narrow chapter-scoped method."""
    signature = inspect.signature(CharacterVoiceCheckerServiceProtocol.check)

    assert list(signature.parameters) == ["self", "chapter_id", "user_id"]
    assert signature.parameters["chapter_id"].annotation == "UUID"
    assert signature.parameters["user_id"].annotation == "UUID"


def test_voice_check_schemas_capture_required_per_character_fields() -> None:
    """Per-character schema exposes the ADR-057 / WRITE-010 result contract."""
    flagged_line = FlaggedLineResponse(
        quote="I ain't convinced, professor.",
        reason="Register is too casual for Elena's established profile.",
    )
    result = VoiceCheckResult(
        character_name="Elena",
        has_profile=True,
        match_score=82.5,
        band="good",
        match_judgment="Minor drift in register.",
        qualitative_sub_score=78.0,
        flagged_lines=[flagged_line],
    )
    response = VoiceCheckResponse(chapter_id=str(uuid4()), results=[result])
    event = VoiceCheckStreamEvent(event="result", result=result)

    assert VoiceCheckRequest().model_dump() == {}
    assert response.results[0].character_name == "Elena"
    assert response.results[0].has_profile is True
    assert response.results[0].match_score == 82.5
    assert response.results[0].band == "good"
    assert response.results[0].match_judgment == "Minor drift in register."
    assert response.results[0].qualitative_sub_score == 78.0
    assert response.results[0].flagged_lines[0].quote == "I ain't convinced, professor."
    assert event.result == result


def test_voice_check_protocol_is_runtime_checkable() -> None:
    """Protocol remains structurally checkable like sibling analysis contracts."""

    class FakeVoiceCheckerService:
        async def check(
            self,
            chapter_id: UUID,
            user_id: UUID,
        ) -> object:
            return None

    assert isinstance(FakeVoiceCheckerService(), CharacterVoiceCheckerServiceProtocol)


def test_voice_check_score_fields_are_percentages() -> None:
    """Numeric score fields reject values outside the 0-100 range."""
    with pytest.raises(ValueError, match="less than or equal to 100"):
        VoiceCheckResult(
            character_name="Elena",
            has_profile=True,
            match_score=101.0,
            band="excellent",
            match_judgment="Impossible score.",
            qualitative_sub_score=50.0,
        )
