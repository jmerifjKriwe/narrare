"""Tests for context_assembler.py — ProjectWritingProfile override path.

Covers uncovered lines 211-224 in ``WritingContextAssembler.assemble()``:
the branch where a ``ProjectWritingProfile`` is provided and overrides
default metadata fields (project_title, genre, tone, writing_language,
story_structure, novel_synopsis, style_profile, logline).
"""

from __future__ import annotations

from narrare_core.project.profile import ProjectWritingProfile
from narrare_core.writing.context_assembler import WritingContextAssembler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _profile(
    *,
    project_title: str = "",
    genre: str = "",
    tone: str = "",
    writing_language: str = "",
    story_structure: str = "",
    novel_synopsis: str = "",
    style_profile: str = "",
    logline: str = "",
) -> ProjectWritingProfile:
    """Create a ProjectWritingProfile with the given fields."""
    return ProjectWritingProfile(
        project_title=project_title,
        genre=genre,
        tone=tone,
        writing_language=writing_language,
        story_structure=story_structure,
        novel_synopsis=novel_synopsis,
        style_profile=style_profile,
        logline=logline,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContextAssemblerProfileOverrides:
    """Profile fields override empty assembler arguments."""

    async def test_profile_overrides_empty_project_title(self) -> None:
        """When project_title is empty and profile has one → profile wins."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(project_title="The Dark Forest")
        ctx = await assembler.assemble(
            chapter_content="Hello",
            profile=profile,
        )
        assert ctx.project_title == "The Dark Forest"

    async def test_profile_does_not_override_nonempty_project_title(self) -> None:
        """When project_title is already set → profile doesn't override."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(project_title="Profile Title")
        ctx = await assembler.assemble(
            chapter_content="Hello",
            project_title="Original Title",
            profile=profile,
        )
        assert ctx.project_title == "Original Title"

    async def test_profile_overrides_empty_genre(self) -> None:
        """When genre is empty and profile has one → profile wins."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(genre="Fantasy")
        ctx = await assembler.assemble(
            chapter_content="Hello",
            profile=profile,
        )
        assert ctx.genre == "Fantasy"

    async def test_profile_overrides_default_tone(self) -> None:
        """When tone is 'balanced' (default) and profile has a tone → profile wins."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(tone="dark")
        ctx = await assembler.assemble(
            chapter_content="Hello",
            tone="balanced",
            profile=profile,
        )
        assert ctx.tone == "dark"

    async def test_profile_overrides_empty_writing_language(self) -> None:
        """When writing_language is empty and profile has one → profile wins."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(writing_language="Schweizerdeutsch")
        ctx = await assembler.assemble(
            chapter_content="Hello",
            profile=profile,
        )
        assert ctx.writing_language == "Schweizerdeutsch"

    async def test_profile_overrides_empty_story_structure(self) -> None:
        """When story_structure is empty and profile has one → profile wins."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(story_structure="three_act")
        ctx = await assembler.assemble(
            chapter_content="Hello",
            profile=profile,
        )
        assert ctx.story_structure == "three_act"

    async def test_profile_provides_synopsis_style_logline(self) -> None:
        """Profile provides novel_synopsis, style_profile, and logline."""
        assembler = WritingContextAssembler(total_budget=6000)
        profile = _profile(
            novel_synopsis="A hero rises.",
            style_profile="Lyrical prose with sparse dialogue.",
            logline="A girl discovers she can talk to trees.",
        )
        ctx = await assembler.assemble(
            chapter_content="Hello",
            profile=profile,
        )
        assert ctx.novel_synopsis == "A hero rises."
        assert ctx.style_profile == "Lyrical prose with sparse dialogue."
        assert ctx.logline == "A girl discovers she can talk to trees."

    async def test_no_profile_produces_empty_synopsis_style_logline(self) -> None:
        """When no profile is given → synopsis/style/logline are empty."""
        assembler = WritingContextAssembler(total_budget=6000)
        ctx = await assembler.assemble(chapter_content="Hello")
        assert ctx.novel_synopsis == ""
        assert ctx.style_profile == ""
        assert ctx.logline == ""
