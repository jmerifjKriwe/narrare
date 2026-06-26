"""Tests for CoreferenceAgent output types and deps.

Covers:
1. PronounResolution construction and Field constraints
2. CharacterMention construction
3. CoreferenceOutput construction and clarity_score bounds
4. CoreferenceDeps defaults and custom values

No real LLM calls (RULE-01b).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.coreference_types import (
    CharacterMention,
    CoreferenceDeps,
    CoreferenceOutput,
    PronounResolution,
)

# ---------------------------------------------------------------------------
# A. PronounResolution
# ---------------------------------------------------------------------------


class TestPronounResolution:
    """PronounResolution constructs and validates correctly."""

    def test_defaults(self) -> None:
        r = PronounResolution()
        assert r.pronoun == ""
        assert r.position == 0
        assert r.referent == ""
        assert r.confidence == 0.0
        assert r.is_ambiguous is False

    def test_custom_values(self) -> None:
        r = PronounResolution(
            pronoun="She",
            position=24,
            referent="Alice",
            confidence=0.9,
            is_ambiguous=False,
        )
        assert r.pronoun == "She"
        assert r.position == 24
        assert r.referent == "Alice"
        assert r.confidence == 0.9
        assert r.is_ambiguous is False

    def test_confidence_lower_bound_enforced(self) -> None:
        with pytest.raises(ValidationError):
            PronounResolution(confidence=-0.1)

    def test_confidence_upper_bound_enforced(self) -> None:
        with pytest.raises(ValidationError):
            PronounResolution(confidence=1.5)


# ---------------------------------------------------------------------------
# B. CharacterMention
# ---------------------------------------------------------------------------


class TestCharacterMention:
    """CharacterMention constructs correctly."""

    def test_defaults(self) -> None:
        m = CharacterMention()
        assert m.character_name == ""
        assert m.mentions == []
        assert m.is_pov is False

    def test_custom_values(self) -> None:
        m = CharacterMention(
            character_name="Alice",
            mentions=[0, 24, 58],
            is_pov=True,
        )
        assert m.character_name == "Alice"
        assert m.mentions == [0, 24, 58]
        assert m.is_pov is True


# ---------------------------------------------------------------------------
# C. CoreferenceOutput
# ---------------------------------------------------------------------------


class TestCoreferenceOutput:
    """CoreferenceOutput constructs and validates correctly."""

    def test_defaults(self) -> None:
        out = CoreferenceOutput()
        assert out.resolutions == []
        assert out.character_mentions == []
        assert out.clarity_score == 0.0
        assert out.summary == ""

    def test_clarity_score_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            CoreferenceOutput(summary="x", clarity_score=-1.0)

    def test_clarity_score_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            CoreferenceOutput(summary="x", clarity_score=101.0)

    def test_full_construction(self) -> None:
        out = CoreferenceOutput(
            resolutions=[
                PronounResolution(pronoun="She", referent="Alice", confidence=0.9),
            ],
            character_mentions=[
                CharacterMention(character_name="Alice", mentions=[0, 24]),
            ],
            clarity_score=82.5,
            summary="Most pronouns resolve clearly.",
        )
        assert len(out.resolutions) == 1
        assert out.resolutions[0].referent == "Alice"
        assert out.clarity_score == 82.5


# ---------------------------------------------------------------------------
# D. CoreferenceDeps
# ---------------------------------------------------------------------------


class TestCoreferenceDeps:
    """CoreferenceDeps creates and configures correctly."""

    def test_defaults(self) -> None:
        deps = CoreferenceDeps()
        assert deps.text == ""
        assert deps.project_title == ""
        assert deps.genre == ""
        assert deps.writing_language == "en"
        assert deps.chapter_title == ""

    def test_custom_values(self) -> None:
        deps = CoreferenceDeps(
            text="Alice looked at Bob. She smiled.",
            project_title="The Hollow Crown",
            genre="Fantasy",
            writing_language="de",
            chapter_title="Chapter 1: The Arrival",
        )
        assert deps.text == "Alice looked at Bob. She smiled."
        assert deps.project_title == "The Hollow Crown"
        assert deps.genre == "Fantasy"
        assert deps.writing_language == "de"
        assert deps.chapter_title == "Chapter 1: The Arrival"
