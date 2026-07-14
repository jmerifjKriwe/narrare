"""CR-04: Tests for WritingContext prompt variables and metadata with new fields.

Covers:
1. to_prompt_variables() includes kb_systems, kb_timelines, story_structure,
   timeline_position
2. All new fields default to empty
3. to_metadata() includes story_structure and timeline_position
4. voice_profile_warnings and orphan_reference_warnings default
"""

from __future__ import annotations

from narrare_core.writing.models import WritingContext

# ---------------------------------------------------------------------------
# Prompt Variables
# ---------------------------------------------------------------------------


class TestWritingContextPromptVariables:
    """to_prompt_variables() includes CR-04 fields."""

    def test_kb_systems_in_prompt_variables(self) -> None:
        ctx = WritingContext(kb_systems="System rules here.")
        vars = ctx.to_prompt_variables()
        assert vars["kb_systems"] == "System rules here."

    def test_kb_timelines_in_prompt_variables(self) -> None:
        ctx = WritingContext(kb_timelines="Timeline entries here.")
        vars = ctx.to_prompt_variables()
        assert vars["kb_timelines"] == "Timeline entries here."

    def test_story_structure_in_prompt_variables(self) -> None:
        ctx = WritingContext(story_structure="3-Act Structure")
        vars = ctx.to_prompt_variables()
        assert vars["story_structure"] == "3-Act Structure"

    def test_timeline_position_in_prompt_variables(self) -> None:
        ctx = WritingContext(timeline_position="Day 5")
        vars = ctx.to_prompt_variables()
        assert vars["timeline_position"] == "Day 5"

    def test_all_new_fields_empty_by_default(self) -> None:
        ctx = WritingContext()
        vars = ctx.to_prompt_variables()
        assert vars["kb_systems"] == ""
        assert vars["kb_timelines"] == ""
        assert vars["story_structure"] == ""
        assert vars["timeline_position"] == ""

    def test_prompt_variables_contains_all_expected_keys(self) -> None:
        """All expected prompt variable keys are present."""
        ctx = WritingContext()
        vars = ctx.to_prompt_variables()
        expected = {
            "chapter_content",
            "chapter_frontmatter",
            "chapter_outline",
            "recent_chapters",
            "recent_chapter_count",
            "kb_characters",
            "kb_locations",
            "kb_factions",
            "kb_systems",
            "kb_timelines",
            "kb_other",
            "kb_relationships",
            "kb_suggested",
            "kb_pinned",
            "kb_context_warnings",
            "character_voice_profiles",
            "project_title",
            "genre",
            "tone",
            "writing_language",
            "word_target",
            "user_preferences",
            "avoidance_patterns",
            "cross_session_context",
            "is_first_chapter",
            "is_sparse_kb",
            "story_structure",
            "timeline_position",
            "novel_synopsis",
            "style_profile",
            "logline",
        }
        assert set(vars.keys()) == expected


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestWritingContextMetadataCr04:
    """to_metadata() includes CR-04 fields."""

    def test_story_structure_in_metadata(self) -> None:
        ctx = WritingContext(story_structure="Hero's Journey")
        meta = ctx.to_metadata()
        assert meta.story_structure == "Hero's Journey"

    def test_timeline_position_in_metadata(self) -> None:
        ctx = WritingContext(timeline_position="Night 3")
        meta = ctx.to_metadata()
        assert meta.timeline_position == "Night 3"

    def test_voice_profile_warnings_default_empty(self) -> None:
        ctx = WritingContext()
        assert ctx.voice_profile_warnings == []

    def test_orphan_reference_warnings_default_empty(self) -> None:
        ctx = WritingContext()
        assert ctx.orphan_reference_warnings == []

    def test_voice_profile_warnings_forwarded(self) -> None:
        ctx = WritingContext(
            voice_profile_warnings=["Alice profile is stale"],
        )
        # The warnings aren't in ContextMetadata currently, just verify
        # they're on the context
        assert len(ctx.voice_profile_warnings) == 1
        assert ctx.voice_profile_warnings[0] == "Alice profile is stale"
