"""Type + Deps tests for CharacterVoiceCheckerAgent (WRITE-010 / ADR-057).

Covers the structured output types and the ``CharacterVoiceCheckerDeps``
construction contract. Mirrors the plain-class Deps pattern of
``CharacterVoiceDeps`` / ``CoreferenceDeps`` / ``ReadabilityDeps``.
"""

from __future__ import annotations

from narrare_core.agents.character_voice_checker_types import (
    CharacterVoiceCheckerDeps,
    CharacterVoiceCheckerEntry,
    CharacterVoiceCheckerOutput,
    FlaggedLine,
    MatchJudgment,
)


class TestCharacterVoiceCheckerDeps:
    """CharacterVoiceCheckerDeps construction (plain class, kw-only)."""

    def test_defaults(self) -> None:
        deps = CharacterVoiceCheckerDeps()
        assert deps.attributed_dialogue == ""
        assert deps.descriptive_profile_summary == ""
        assert deps.metric_delta_summary == ""
        assert deps.character_names == []
        assert deps.project_title == ""
        assert deps.genre == ""
        assert deps.writing_language == "en"
        assert deps.chapter_title == ""

    def test_all_fields(self) -> None:
        deps = CharacterVoiceCheckerDeps(
            attributed_dialogue='Elena: "Hello."',
            descriptive_profile_summary="Elena: elevated/formal register.",
            metric_delta_summary="Elena: avg_sent_len d=0.12.",
            character_names=["Elena", "Marc"],
            project_title="The Silent Forest",
            genre="Fantasy",
            writing_language="de",
            chapter_title="Chapter 1",
        )
        assert deps.attributed_dialogue == 'Elena: "Hello."'
        assert deps.descriptive_profile_summary.startswith("Elena")
        assert "avg_sent_len" in deps.metric_delta_summary
        assert deps.character_names == ["Elena", "Marc"]
        assert deps.project_title == "The Silent Forest"
        assert deps.genre == "Fantasy"
        assert deps.writing_language == "de"
        assert deps.chapter_title == "Chapter 1"

    def test_character_names_defensive_copy(self) -> None:
        """character_names is copied (mutating the source list does not leak in)."""
        source = ["Elena", "Marc"]
        deps = CharacterVoiceCheckerDeps(character_names=source)
        source.append("Iris")
        assert deps.character_names == ["Elena", "Marc"]

    def test_character_names_none_yields_empty_list(self) -> None:
        deps = CharacterVoiceCheckerDeps(character_names=None)
        assert deps.character_names == []


class TestFlaggedLine:
    """FlaggedLine (quote + reason)."""

    def test_construction(self) -> None:
        line = FlaggedLine(quote="I dare say.", reason="Informal register drift.")
        assert line.quote == "I dare say."
        assert line.reason == "Informal register drift."

    def test_defaults(self) -> None:
        line = FlaggedLine()
        assert line.quote == ""
        assert line.reason == ""


class TestMatchJudgmentLiteral:
    """match_judgment accepts exactly the four template literals."""

    def test_all_four_judgments_valid(self) -> None:
        for judgment in (
            "consistent",
            "mostly_consistent",
            "notable_drift",
            "off",
        ):
            entry: MatchJudgment = CharacterVoiceCheckerEntry(
                character_name="Elena",
                match_judgment=judgment,  # type: ignore[arg-type]
            ).match_judgment
            assert entry == judgment

    def test_invalid_judgment_rejected(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CharacterVoiceCheckerEntry(
                character_name="Elena",
                match_judgment="perfect",  # type: ignore[arg-type]
            )


class TestOutputWrapper:
    """CharacterVoiceCheckerOutput wrapper shape."""

    def test_default_empty(self) -> None:
        out = CharacterVoiceCheckerOutput()
        assert out.characters == []

    def test_round_trip(self) -> None:
        out = CharacterVoiceCheckerOutput(
            characters=[
                CharacterVoiceCheckerEntry(character_name="Elena"),
                CharacterVoiceCheckerEntry(character_name="Marc"),
            ]
        )
        assert len(out.characters) == 2


class TestNoRewriteFieldDecision5:
    """ADR-057 Decision 5: the output type carries no suggested_rewrite field.

    Rewrite-on-flagged-line is a separate feature (WRITE-004). The checker
    flags + scores only. This invariant is asserted at the type level so a
    future regression (adding a rewrite field) fails loudly here.
    """

    def test_entry_has_no_rewrite_field(self) -> None:
        field_names = set(CharacterVoiceCheckerEntry.model_fields.keys())
        assert "suggested_rewrite" not in field_names
        assert "rewrite" not in field_names
        assert not any("rewrite" in name for name in field_names)

    def test_flagged_line_fields_are_exactly_quote_and_reason(self) -> None:
        field_names = set(FlaggedLine.model_fields.keys())
        assert field_names == {"quote", "reason"}

    def test_output_wrapper_fields_exactly_characters(self) -> None:
        assert set(CharacterVoiceCheckerOutput.model_fields.keys()) == {"characters"}
