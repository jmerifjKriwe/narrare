"""Tests for memory/models.py — PreferenceProfile.to_prompt_text()."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from narrare_core.memory.models import PreferenceProfile


def _make_profile(
    *,
    event_count: int = 10,
    style: dict[str, str] | None = None,
    content: dict[str, str] | None = None,
    constraints: list[str] | None = None,
) -> PreferenceProfile:
    """Helper to build a PreferenceProfile with sensible defaults."""
    return PreferenceProfile(
        user_id=uuid4(),
        project_id=uuid4(),
        event_count=event_count,
        confidence=0.75,
        last_updated=datetime.now(UTC),
        style=style or {},
        content=content or {},
        constraints=constraints or [],
    )


class TestPreferenceProfileEmpty:
    """When event_count is zero, to_prompt_text returns empty string."""

    def test_returns_empty_string_when_no_events(self) -> None:
        profile = _make_profile(event_count=0)
        assert profile.to_prompt_text() == ""

    def test_returns_empty_string_with_data_but_zero_events(self) -> None:
        """Even with style/content data, zero events means no output."""
        profile = _make_profile(
            event_count=0,
            style={"tone": "formal"},
        )
        assert profile.to_prompt_text() == ""


class TestPreferenceProfileStyleOnly:
    """Profile with style preferences only."""

    def test_formats_style_preferences(self) -> None:
        profile = _make_profile(
            style={
                "short_sentences": "preferred",
                "descriptive_prose": "avoid",
            },
        )
        result = profile.to_prompt_text()

        assert "## Style preferences" in result
        assert "- Short sentences: preferred" in result
        assert "- Descriptive prose: avoid" in result
        # Should not include empty sections
        assert "## Content preferences" not in result
        assert "## Constraints" not in result


class TestPreferenceProfileAllSections:
    """Profile with style, content, and constraints."""

    def test_formats_all_sections(self) -> None:
        profile = _make_profile(
            style={"tone": "conversational"},
            content={"genre": "literary fiction"},
            constraints=["no graphic violence", "keep chapters under 3000 words"],
        )
        result = profile.to_prompt_text()

        assert "## Style preferences" in result
        assert "- Tone: conversational" in result
        assert "## Content preferences" in result
        assert "- Genre: literary fiction" in result
        assert "## Constraints" in result
        assert "- no graphic violence" in result
        assert "- keep chapters under 3000 words" in result

    def test_sections_separated_by_double_newline(self) -> None:
        profile = _make_profile(
            style={"tone": "formal"},
            content={"genre": "fantasy"},
        )
        result = profile.to_prompt_text()

        # Two sections → one double-newline separator
        assert "\n\n" in result


class TestPreferenceProfileConstraintsOnly:
    """Profile with only constraints (no style or content)."""

    def test_formats_constraints_only(self) -> None:
        profile = _make_profile(
            constraints=["avoid clichés", "use third-person POV"],
        )
        result = profile.to_prompt_text()

        assert "## Constraints" in result
        assert "- avoid clichés" in result
        assert "- use third-person POV" in result
        assert "## Style preferences" not in result
        assert "## Content preferences" not in result


class TestPreferenceProfileKeyFormatting:
    """Key humanisation: snake_case → Capitalised words."""

    def test_single_word_key(self) -> None:
        profile = _make_profile(style={"tone": "formal"})
        result = profile.to_prompt_text()
        assert "- Tone: formal" in result

    def test_multi_word_snake_key(self) -> None:
        profile = _make_profile(style={"short_sentences": "preferred"})
        result = profile.to_prompt_text()
        assert "- Short sentences: preferred" in result

    def test_multiple_underscores(self) -> None:
        profile = _make_profile(style={"first_person_narrator": "yes"})
        result = profile.to_prompt_text()
        assert "- First person narrator: yes" in result
