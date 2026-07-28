"""Import and shape tests for ANAL-009 Phase 2B author-voice-drift backend
contracts (RULE-03).

Mirrors ``test_voice_drift_contracts_schemas.py`` (Phase 1), adapted for the
singular narrator result (one author voice per novel — contrast Phase 1's
per-character lists).
"""

from __future__ import annotations

import inspect
from uuid import UUID, uuid4

import pytest

from narrare.analysis.contracts_author_voice_drift import (
    AuthorVoiceDriftServiceProtocol,
)
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftEvent,
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResponse,
    AuthorVoiceDriftResult,
)
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult


def test_protocol_exposes_novel_scoped_run_and_run_stream() -> None:
    """The protocol carries both RULE-13 run + run_stream signatures."""
    run_sig = inspect.signature(AuthorVoiceDriftServiceProtocol.run)
    stream_sig = inspect.signature(AuthorVoiceDriftServiceProtocol.run_stream)

    assert list(run_sig.parameters) == ["self", "novel_id", "user_id", "request"]
    assert run_sig.parameters["novel_id"].annotation == "UUID"
    assert run_sig.parameters["user_id"].annotation == "UUID"
    assert list(stream_sig.parameters) == ["self", "novel_id", "user_id", "request"]


def test_protocol_is_runtime_checkable() -> None:
    """Protocol remains structurally checkable like sibling analysis contracts."""

    class FakeAuthorVoiceDriftService:
        async def run(
            self,
            novel_id: UUID,
            user_id: UUID,
            request: AuthorVoiceDriftRequest,
        ) -> object:
            return None

        async def run_stream(
            self,
            novel_id: UUID,
            user_id: UUID,
            request: AuthorVoiceDriftRequest,
        ) -> object:
            return None

    assert isinstance(FakeAuthorVoiceDriftService(), AuthorVoiceDriftServiceProtocol)


def test_request_carries_optional_chapter_filter() -> None:
    """Request body carries the optional chapter_ids filter (no character filter)."""
    req = AuthorVoiceDriftRequest()
    assert req.chapter_ids is None

    scoped = AuthorVoiceDriftRequest(chapter_ids=["ch-1", "ch-2"])
    assert scoped.chapter_ids == ["ch-1", "ch-2"]


def test_no_profile_carries_reason() -> None:
    """The graceful no_profile event disambiguates the skip reason (RULE-11)."""
    no_profile = AuthorVoiceDriftNoProfile(reason="no_stored_profile")
    assert no_profile.reason == "no_stored_profile"


def test_result_round_trips_trend_jumps_drift() -> None:
    """Narrator result carries trend + jumps + overall score/band + drift."""
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
    result = AuthorVoiceDriftResult(
        novel_id=str(uuid4()),
        trend=trend,
        jumps=jumps,
        overall_match_score=75.0,
        overall_band="minor",
        drift=drift,
    )
    response = AuthorVoiceDriftResponse(novel_id=str(uuid4()), result=result)

    assert response.result is not None
    assert response.no_profile is None
    assert len(response.result.trend) == 2
    assert response.result.trend[0].band == "stable"
    assert response.result.jumps[0].jumped_metrics == ["avg_sentence_length"]
    assert response.result.overall_match_score == 75.0
    assert response.result.overall_band == "minor"
    assert response.result.drift.drift_type == "inconsistency"


def test_event_discriminates_result_and_no_profile() -> None:
    """The SSE event carries result on 'result', no_profile on skip."""
    result = AuthorVoiceDriftResult(novel_id=str(uuid4()))
    no_profile = AuthorVoiceDriftNoProfile(reason="no_stored_profile")

    result_event = AuthorVoiceDriftEvent(event="result", result=result)
    skip_event = AuthorVoiceDriftEvent(event="no_profile", no_profile=no_profile)
    done_event = AuthorVoiceDriftEvent(event="done", is_final=True)

    assert result_event.event == "result"
    assert result_event.result == result
    assert result_event.no_profile is None
    assert skip_event.event == "no_profile"
    assert skip_event.no_profile == no_profile
    assert skip_event.result is None
    assert done_event.event == "done"
    assert done_event.is_final is True


def test_overall_match_score_rejects_out_of_range() -> None:
    """Numeric score fields reject values outside the 0-100 range."""
    with pytest.raises(ValueError):
        AuthorVoiceDriftResult(overall_match_score=101.0)
