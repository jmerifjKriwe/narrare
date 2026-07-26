"""Type + Deps tests for CharacterVoiceDriftAgent (ANAL-009 / ADR-073).

Covers the structured output types and the ``CharacterVoiceDriftDeps``
construction contract. Mirrors the plain-class Deps pattern of
``CharacterVoiceCheckerDeps`` / ``CharacterVoiceDeps`` / ``ReadabilityDeps``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.character_voice_drift_types import (
    ChapterMeta,
    ChapterNote,
    CharacterVoiceDriftDeps,
    DriftType,
    VoiceDriftResult,
)
from narrare_core.analysis.voice_drift_scoring import (
    JumpPoint,
    PerChapterMetrics,
    TrendPoint,
)
from narrare_core.kb.schemas.character import VoiceMetrics


class TestChapterMeta:
    """ChapterMeta (id + title + optional summary)."""

    def test_construction(self) -> None:
        meta = ChapterMeta(chapter_id="ch-1", title="The Arrival")
        assert meta.chapter_id == "ch-1"
        assert meta.title == "The Arrival"
        assert meta.summary is None

    def test_defaults(self) -> None:
        meta = ChapterMeta(chapter_id="ch-2")
        assert meta.chapter_id == "ch-2"
        assert meta.title == ""
        assert meta.summary is None

    def test_with_summary(self) -> None:
        meta = ChapterMeta(chapter_id="ch-3", title="Ch 3", summary="A fight.")
        assert meta.summary == "A fight."

    def test_frozen(self) -> None:
        meta = ChapterMeta(chapter_id="ch-1")
        with pytest.raises(ValidationError):
            meta.chapter_id = "ch-9"  # type: ignore[misc]


class TestChapterNote:
    """ChapterNote (chapter_id + note)."""

    def test_construction(self) -> None:
        note = ChapterNote(chapter_id="ch-7", note="Jump in formality.")
        assert note.chapter_id == "ch-7"
        assert note.note == "Jump in formality."

    def test_defaults(self) -> None:
        note = ChapterNote()
        assert note.chapter_id == ""
        assert note.note == ""


class TestDriftTypeLiteral:
    """drift_type accepts exactly the three template literals."""

    def test_all_three_types_valid(self) -> None:
        for dt in ("evolution", "context", "inconsistency"):
            result: DriftType = VoiceDriftResult(
                drift_type=dt,  # type: ignore[arg-type]
            ).drift_type
            assert result == dt

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VoiceDriftResult(
                drift_type="stable",  # type: ignore[arg-type]
            )


class TestConfidenceBounds:
    """confidence is bounded to [0.0, 1.0] by the Pydantic Field."""

    def test_zero_is_valid(self) -> None:
        assert VoiceDriftResult(confidence=0.0).confidence == 0.0

    def test_one_is_valid(self) -> None:
        assert VoiceDriftResult(confidence=1.0).confidence == 1.0

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VoiceDriftResult(confidence=1.01)

    def test_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VoiceDriftResult(confidence=-0.01)

    def test_default_is_zero(self) -> None:
        assert VoiceDriftResult().confidence == 0.0


class TestVoiceDriftResultShape:
    """VoiceDriftResult is a flat object (NOT a wrapper with a list)."""

    def test_default_empty(self) -> None:
        out = VoiceDriftResult()
        assert out.drift_type == "evolution"
        assert out.confidence == 0.0
        assert out.longitudinal_reasons == []
        assert out.per_chapter_notes == []
        assert out.suggested_attention == []

    def test_round_trip(self) -> None:
        out = VoiceDriftResult(
            drift_type="inconsistency",
            confidence=0.82,
            longitudinal_reasons=[
                "formality declines consistently from ch-3 through ch-12",
                "type-token ratio jumps sharply at ch-7",
            ],
            per_chapter_notes=[
                ChapterNote(chapter_id="ch-7", note="Sharp TTR jump."),
                ChapterNote(chapter_id="ch-11", note="Lowest match score."),
            ],
            suggested_attention=["ch-7", "ch-11"],
        )
        assert out.drift_type == "inconsistency"
        assert out.confidence == 0.82
        assert len(out.longitudinal_reasons) == 2
        assert len(out.per_chapter_notes) == 2
        assert out.per_chapter_notes[0].chapter_id == "ch-7"
        assert out.suggested_attention == ["ch-7", "ch-11"]


class TestNoRewriteOrProfileFieldDecision5:
    """ADR-073 Decision 5: the output type carries no rewrite / profile field.

    Drift classification is read-only analysis — not rewriting (WRITE-004) and
    not profiling (ANAL-008). This invariant is asserted at the type level so a
    future regression (adding such a field) fails loudly here.
    """

    def test_result_has_no_rewrite_field(self) -> None:
        field_names = set(VoiceDriftResult.model_fields.keys())
        assert "suggested_rewrite" not in field_names
        assert "rewrite" not in field_names
        assert not any("rewrite" in name for name in field_names)

    def test_result_has_no_profile_field(self) -> None:
        field_names = set(VoiceDriftResult.model_fields.keys())
        assert "new_profile" not in field_names
        assert "profile" not in field_names
        assert "voice_profile" not in field_names

    def test_result_fields_exactly_locked_shape(self) -> None:
        """The output shape is exactly the locked ADR-073 D3 contract."""
        assert set(VoiceDriftResult.model_fields.keys()) == {
            "drift_type",
            "confidence",
            "longitudinal_reasons",
            "per_chapter_notes",
            "suggested_attention",
        }

    def test_chapter_note_fields_exactly_chapter_id_and_note(self) -> None:
        assert set(ChapterNote.model_fields.keys()) == {"chapter_id", "note"}


class TestCharacterVoiceDriftDeps:
    """CharacterVoiceDriftDeps construction (plain class, kw-only)."""

    def test_defaults(self) -> None:
        deps = CharacterVoiceDriftDeps()
        assert deps.character_name == ""
        assert deps.descriptive_profile == ""
        assert deps.trend == []
        assert deps.jumps == []
        assert deps.chapter_meta == []
        assert deps.project_title == ""
        assert deps.genre == ""
        assert deps.writing_language == "en"

    def test_all_fields(self) -> None:
        trend = [TrendPoint(chapter_id="ch-1", match_subscore=92.0, band="stable")]
        jumps = [
            JumpPoint(
                from_chapter_id="ch-1",
                to_chapter_id="ch-2",
                jumped_metrics=["avg_sentence_length"],
                magnitude=0.4,
            )
        ]
        meta = [ChapterMeta(chapter_id="ch-1", title="The Arrival")]
        deps = CharacterVoiceDriftDeps(
            character_name="Elena",
            descriptive_profile="Elena: elevated/formal register.",
            trend=trend,
            jumps=jumps,
            chapter_meta=meta,
            project_title="The Silent Forest",
            genre="Fantasy",
            writing_language="de",
        )
        assert deps.character_name == "Elena"
        assert deps.descriptive_profile.startswith("Elena")
        assert deps.trend == trend
        assert deps.jumps == jumps
        assert deps.chapter_meta == meta
        assert deps.project_title == "The Silent Forest"
        assert deps.genre == "Fantasy"
        assert deps.writing_language == "de"

    def test_trend_defensive_copy(self) -> None:
        """trend is copied (mutating the source list does not leak in)."""
        source = [TrendPoint(chapter_id="ch-1", match_subscore=90.0, band="stable")]
        deps = CharacterVoiceDriftDeps(trend=source)
        source.append(TrendPoint(chapter_id="ch-2", match_subscore=80.0, band="minor"))
        assert len(deps.trend) == 1

    def test_jumps_defensive_copy(self) -> None:
        source = [
            JumpPoint(
                from_chapter_id="ch-1",
                to_chapter_id="ch-2",
                jumped_metrics=["type_token_ratio"],
                magnitude=0.5,
            )
        ]
        deps = CharacterVoiceDriftDeps(jumps=source)
        source.clear()
        assert len(deps.jumps) == 1

    def test_chapter_meta_defensive_copy(self) -> None:
        source = [ChapterMeta(chapter_id="ch-1")]
        deps = CharacterVoiceDriftDeps(chapter_meta=source)
        source.append(ChapterMeta(chapter_id="ch-2"))
        assert len(deps.chapter_meta) == 1

    def test_none_yields_empty_lists(self) -> None:
        deps = CharacterVoiceDriftDeps(trend=None, jumps=None, chapter_meta=None)
        assert deps.trend == []
        assert deps.jumps == []
        assert deps.chapter_meta == []

    def test_accepts_scoring_value_objects(self) -> None:
        """Deps carry the real scoring value objects (TrendPoint/JumpPoint)."""
        pcm = PerChapterMetrics(
            chapter_id="ch-1",
            character_id="Elena",
            metrics=VoiceMetrics(avg_sentence_length=12.0),
            utterance_count=4,
        )
        trend = trend_against_profile_helper(pcm)
        deps = CharacterVoiceDriftDeps(trend=trend)
        assert deps.trend is not None
        assert deps.trend[0].chapter_id == "ch-1"


def trend_against_profile_helper(pcm: PerChapterMetrics) -> list[TrendPoint]:
    """Build a real TrendPoint via the scoring layer (proves deps interop)."""
    from narrare_core.analysis.voice_drift_scoring import trend_against_profile

    profile = VoiceMetrics(avg_sentence_length=12.0)
    return trend_against_profile([pcm], profile)
