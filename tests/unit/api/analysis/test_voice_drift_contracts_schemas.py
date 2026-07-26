"""Import and shape tests for ANAL-009 voice-drift backend contracts."""

from __future__ import annotations

import inspect
from uuid import UUID, uuid4

import pytest

from narrare.analysis.contracts_voice_drift import (
    CharacterVoiceDriftServiceProtocol,
)
from narrare.analysis.schemas_voice_drift import (
    VoiceDriftCharacterResult,
    VoiceDriftEvent,
    VoiceDriftNoProfile,
    VoiceDriftRequest,
    VoiceDriftResponse,
)
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult


def test_voice_drift_protocol_exposes_novel_scoped_run_and_run_stream() -> None:
    """The protocol carries both RULE-13 run + run_stream signatures."""
    run_sig = inspect.signature(CharacterVoiceDriftServiceProtocol.run)
    stream_sig = inspect.signature(CharacterVoiceDriftServiceProtocol.run_stream)

    assert list(run_sig.parameters) == ["self", "novel_id", "user_id", "request"]
    assert run_sig.parameters["novel_id"].annotation == "UUID"
    assert run_sig.parameters["user_id"].annotation == "UUID"
    assert list(stream_sig.parameters) == ["self", "novel_id", "user_id", "request"]


def test_voice_drift_protocol_is_runtime_checkable() -> None:
    """Protocol remains structurally checkable like sibling analysis contracts."""

    class FakeVoiceDriftService:
        async def run(
            self,
            novel_id: UUID,
            user_id: UUID,
            request: VoiceDriftRequest,
        ) -> object:
            return None

        async def run_stream(
            self,
            novel_id: UUID,
            user_id: UUID,
            request: VoiceDriftRequest,
        ) -> object:
            return None

    assert isinstance(FakeVoiceDriftService(), CharacterVoiceDriftServiceProtocol)


def test_voice_drift_request_carries_optional_filters() -> None:
    """Request body carries optional character_id + chapter_ids filters."""
    req = VoiceDriftRequest()
    assert req.character_id is None
    assert req.chapter_ids is None

    scoped = VoiceDriftRequest(character_id="abc-123", chapter_ids=["ch-1", "ch-2"])
    assert scoped.character_id == "abc-123"
    assert scoped.chapter_ids == ["ch-1", "ch-2"]


def test_voice_drift_no_profile_carries_reason() -> None:
    """The graceful no_profile event disambiguates the skip reason (RULE-11)."""
    no_profile = VoiceDriftNoProfile(
        character_id="",
        character_name="Marc",
        reason="no_stored_profile",
    )
    assert no_profile.reason == "no_stored_profile"
    assert no_profile.character_name == "Marc"


def test_voice_drift_character_result_round_trips_trend_jumps_drift() -> None:
    """Per-character result carries trend + jumps + overall score/band + drift."""
    from narrare_core.analysis.voice_drift_scoring_types import (
        JumpPoint,
        TrendPoint,
    )

    trend = [
        TrendPoint(chapter_id="ch-1", match_subscore=90.0, per_metric_deltas={}, band="stable"),
        TrendPoint(chapter_id="ch-2", match_subscore=60.0, per_metric_deltas={}, band="moderate"),
    ]
    jumps = [
        JumpPoint(
            from_chapter_id="ch-1",
            to_chapter_id="ch-2",
            jumped_metrics=["avg_sentence_length"],
            magnitude=0.5,
        )
    ]
    drift = VoiceDriftResult(
        drift_type="inconsistency",
        confidence=0.8,
        longitudinal_reasons=["Sharp formality drop ch1->ch2."],
    )
    result = VoiceDriftCharacterResult(
        character_id="char-1",
        character_name="Elena",
        trend=trend,
        jumps=jumps,
        overall_match_score=75.0,
        overall_band="minor",
        drift=drift,
    )
    response = VoiceDriftResponse(novel_id=str(uuid4()), results=[result])

    assert response.results[0].character_name == "Elena"
    assert len(response.results[0].trend) == 2
    assert response.results[0].trend[0].band == "stable"
    assert response.results[0].jumps[0].jumped_metrics == ["avg_sentence_length"]
    assert response.results[0].overall_match_score == 75.0
    assert response.results[0].overall_band == "minor"
    assert response.results[0].drift.drift_type == "inconsistency"


def test_voice_drift_event_discriminates_character_result_and_no_profile() -> None:
    """The SSE event carries result on character_result, no_profile on skip."""
    result = VoiceDriftCharacterResult(character_name="Elena")
    no_profile = VoiceDriftNoProfile(character_name="Marc", reason="no_stored_profile")

    result_event = VoiceDriftEvent(event="character_result", result=result)
    skip_event = VoiceDriftEvent(event="no_profile", no_profile=no_profile)
    done_event = VoiceDriftEvent(event="done", is_final=True)

    assert result_event.event == "character_result"
    assert result_event.result == result
    assert result_event.no_profile is None
    assert skip_event.event == "no_profile"
    assert skip_event.no_profile == no_profile
    assert skip_event.result is None
    assert done_event.event == "done"
    assert done_event.is_final is True


def test_voice_drift_overall_match_score_rejects_out_of_range() -> None:
    """Numeric score fields reject values outside the 0-100 range."""
    with pytest.raises(ValueError):
        VoiceDriftCharacterResult(
            character_name="Elena",
            overall_match_score=101.0,
        )
