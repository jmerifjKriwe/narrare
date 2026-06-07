"""Tests for ProjectWritingProfile dataclass (FIND-007)."""

from __future__ import annotations

import pytest

from narrare_core.project.profile import ProjectWritingProfile


class TestProjectWritingProfile:
    def test_defaults(self) -> None:
        profile = ProjectWritingProfile()
        assert profile.project_title == ""
        assert profile.genre == ""
        assert profile.novel_synopsis == ""
        assert profile.style_profile == ""
        assert profile.language == "en"

    def test_frozen_immutability(self) -> None:
        profile = ProjectWritingProfile(genre="Fantasy")
        with pytest.raises(AttributeError):
            profile.genre = "Sci-Fi"  # type: ignore[misc]

    def test_to_prompt_variables_with_data(self) -> None:
        profile = ProjectWritingProfile(
            project_title="Im stillen Wald",
            genre="Fantasy",
            tone="dark",
            novel_synopsis="A hero enters the forest.",
            style_profile="Short sentences. Vivid imagery.",
        )
        variables = profile.to_prompt_variables()
        assert variables["project_title"] == "Im stillen Wald"
        assert variables["genre"] == "Fantasy"
        assert variables["tone"] == "dark"
        assert variables["novel_synopsis"] == "A hero enters the forest."
        assert variables["style_profile"] == "Short sentences. Vivid imagery."

    def test_to_prompt_variables_omits_empty(self) -> None:
        profile = ProjectWritingProfile(genre="Fantasy")
        variables = profile.to_prompt_variables()
        assert "genre" in variables
        assert "tone" not in variables  # empty string — omitted
        assert "novel_synopsis" not in variables

    def test_to_prompt_variables_all_empty(self) -> None:
        profile = ProjectWritingProfile()
        variables = profile.to_prompt_variables()
        # language has a non-empty default ("en"), so it always appears
        assert variables == {"language": "en"}

    def test_full_construction(self) -> None:
        profile = ProjectWritingProfile(
            project_title="Test Novel",
            author_name="Author",
            genre="Fantasy",
            tone="balanced",
            story_structure="three_act",
            writing_language="en",
            language="en",
            novel_synopsis="A story.",
            style_profile="Descriptive.",
            logline="Hero saves world.",
        )
        assert profile.project_title == "Test Novel"
        assert profile.logline == "Hero saves world."
