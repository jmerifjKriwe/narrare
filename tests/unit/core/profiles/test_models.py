"""Tests for profile data models.

Covers:
1. CharacterVoiceProfile construction, frozen, defaults
2. ProjectWritingProfile construction, frozen, defaults
3. has_voice_profiles property
4. formatted_voice_profiles property (empty, fresh, stale, mixed)
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from narrare_core.kb.schemas.character import VoiceMetrics
from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile

# ---------------------------------------------------------------------------
# CharacterVoiceProfile
# ---------------------------------------------------------------------------


class TestCharacterVoiceProfile:
    """CharacterVoiceProfile data model tests."""

    def test_construction_with_defaults(self) -> None:
        vp = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
        )
        assert vp.character_id == "char-1"
        assert vp.name == "Alice"
        assert vp.speech_summary == "dialect: Southern"
        assert vp.updated_at is None
        assert vp.is_fresh is True

    def test_construction_with_all_fields(self) -> None:
        vp = CharacterVoiceProfile(
            character_id="char-2",
            name="Bob",
            speech_summary="dialect: Northern",
            updated_at="2025-01-15T10:00:00+00:00",
            is_fresh=False,
        )
        assert vp.updated_at == "2025-01-15T10:00:00+00:00"
        assert vp.is_fresh is False

    def test_frozen_immutability(self) -> None:
        vp = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
        )
        with pytest.raises(AttributeError):
            cast("Any", vp).name = "Bob"

    def test_equality_by_value(self) -> None:
        vp1 = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
        )
        vp2 = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
        )
        assert vp1 == vp2

    # ------------------------------------------------------------------
    # voice_metrics (ADR-057 Decision 1 — checking-path only)
    # ------------------------------------------------------------------

    def test_voice_metrics_defaults_to_none(self) -> None:
        """Constructing without voice_metrics yields None (additive, optional)."""
        vp = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
        )
        assert vp.voice_metrics is None

    def test_voice_metrics_round_trip(self) -> None:
        """A VoiceMetrics supplied at construction is preserved verbatim."""
        metrics = VoiceMetrics(
            avg_sentence_length=18.5,
            type_token_ratio=0.72,
            verbal_tic_frequency={"indeed": 0.12},
        )
        vp = CharacterVoiceProfile(
            character_id="char-1",
            name="Alice",
            speech_summary="dialect: Southern",
            voice_metrics=metrics,
        )
        vm = vp.voice_metrics
        assert vm is metrics
        assert vm is not None
        assert vm.avg_sentence_length == 18.5
        assert vm.verbal_tic_frequency == {"indeed": 0.12}


# ---------------------------------------------------------------------------
# ProjectWritingProfile
# ---------------------------------------------------------------------------


class TestProjectWritingProfile:
    """ProjectWritingProfile data model tests."""

    def test_default_construction(self) -> None:
        pwp = ProjectWritingProfile()
        assert pwp.writing_language == "en"
        assert pwp.genre is None
        assert pwp.tone is None
        assert pwp.style_profile is None
        assert pwp.character_voice_profiles == ()
        assert pwp.freshness_warnings == ()

    def test_construction_with_all_fields(self) -> None:
        voices = (
            CharacterVoiceProfile("c1", "Alice", "dialect: Southern"),
            CharacterVoiceProfile("c2", "Bob", "dialect: Northern"),
        )
        warnings = ("Voice profile for 'Alice' last updated old (>{30} days ago)",)
        pwp = ProjectWritingProfile(
            writing_language="de",
            genre="fantasy",
            tone="dark",
            style_profile="literary",
            character_voice_profiles=voices,
            freshness_warnings=warnings,
        )
        assert pwp.writing_language == "de"
        assert pwp.genre == "fantasy"
        assert pwp.tone == "dark"
        assert pwp.style_profile == "literary"
        assert len(pwp.character_voice_profiles) == 2
        assert len(pwp.freshness_warnings) == 1

    def test_frozen_immutability(self) -> None:
        pwp = ProjectWritingProfile()
        with pytest.raises(AttributeError):
            cast("Any", pwp).writing_language = "fr"

    # ------------------------------------------------------------------
    # has_voice_profiles
    # ------------------------------------------------------------------

    def test_has_voice_profiles_false_when_empty(self) -> None:
        pwp = ProjectWritingProfile()
        assert pwp.has_voice_profiles is False

    def test_has_voice_profiles_true_with_profiles(self) -> None:
        voices = (CharacterVoiceProfile("c1", "Alice", "dialect: Southern"),)
        pwp = ProjectWritingProfile(character_voice_profiles=voices)
        assert pwp.has_voice_profiles is True

    # ------------------------------------------------------------------
    # formatted_voice_profiles
    # ------------------------------------------------------------------

    def test_formatted_voice_profiles_empty_when_no_profiles(self) -> None:
        pwp = ProjectWritingProfile()
        assert pwp.formatted_voice_profiles == ""

    def test_formatted_voice_profiles_with_fresh_profile(self) -> None:
        voices = (CharacterVoiceProfile("c1", "Alice", "dialect: Southern; vocabulary: archaic"),)
        pwp = ProjectWritingProfile(character_voice_profiles=voices)
        formatted = pwp.formatted_voice_profiles
        assert "**Alice**" in formatted
        assert "dialect: Southern" in formatted
        assert "\u26a0\ufe0f" not in formatted

    def test_formatted_voice_profiles_with_stale_profile(self) -> None:
        voices = (
            CharacterVoiceProfile(
                "c1",
                "Alice",
                "dialect: Southern",
                updated_at="2025-01-01T00:00:00+00:00",
                is_fresh=False,
            ),
        )
        pwp = ProjectWritingProfile(character_voice_profiles=voices)
        formatted = pwp.formatted_voice_profiles
        assert "**Alice**" in formatted
        assert "\u26a0\ufe0f last updated: 2025-01-01T00:00:00+00:00" in formatted

    def test_formatted_voice_profiles_mixed_freshness(self) -> None:
        voices = (
            CharacterVoiceProfile("c1", "Alice", "dialect: Southern"),
            CharacterVoiceProfile(
                "c2",
                "Bob",
                "dialect: Northern",
                updated_at="2025-01-01T00:00:00+00:00",
                is_fresh=False,
            ),
        )
        pwp = ProjectWritingProfile(character_voice_profiles=voices)
        formatted = pwp.formatted_voice_profiles
        lines = formatted.split("\n")
        assert len(lines) == 2
        assert "\u26a0\ufe0f" not in lines[0]
        assert "\u26a0\ufe0f" in lines[1]

    def test_formatted_voice_profiles_identical_with_or_without_voice_metrics(self) -> None:
        """CR-04 guard (ADR-057): generation NEVER reads voice_metrics.

        Two profiles identical except one carries voice_metrics; the generation
        projection (formatted_voice_profiles) must be byte-identical, and no
        metric number may leak into the rendered string. This is the regression
        guard proving ADR-055's "metrics never reach generation" constraint.
        """
        metrics = VoiceMetrics(avg_sentence_length=18.5, type_token_ratio=0.72)
        without = CharacterVoiceProfile("c1", "Alice", "dialect: Southern")
        with_metrics = CharacterVoiceProfile(
            "c1", "Alice", "dialect: Southern", voice_metrics=metrics
        )
        assert without.voice_metrics is None
        assert with_metrics.voice_metrics is metrics

        formatted_without = ProjectWritingProfile(
            character_voice_profiles=(without,)
        ).formatted_voice_profiles
        formatted_with = ProjectWritingProfile(
            character_voice_profiles=(with_metrics,)
        ).formatted_voice_profiles

        # Byte-identical generation output regardless of metrics presence.
        assert formatted_without == formatted_with
        # Sanity: metric numbers never leak into the generation string.
        assert "18.5" not in formatted_with
        assert "0.72" not in formatted_with
        assert "voice_metrics" not in formatted_with
