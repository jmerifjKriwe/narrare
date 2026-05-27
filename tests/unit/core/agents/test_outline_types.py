"""Tests for agents/outline_types.py — OutlineOutput model validation.

Covers:
1. Default values
2. Custom values
3. Serialization roundtrip
4. Edge cases: empty scenes, metadata
"""

from __future__ import annotations

from narrare_core.agents.outline_types import OutlineOutput


class TestOutlineOutputDefaults:
    """OutlineOutput has correct defaults."""

    def test_default_chapter_title(self) -> None:
        output = OutlineOutput()
        assert output.chapter_title == ""

    def test_default_scenes(self) -> None:
        output = OutlineOutput()
        assert output.scenes == []

    def test_default_outline_text(self) -> None:
        output = OutlineOutput()
        assert output.outline_text == ""

    def test_default_metadata(self) -> None:
        output = OutlineOutput()
        assert output.metadata == {}


class TestOutlineOutputWithValues:
    """OutlineOutput with all fields populated."""

    def test_with_scenes_and_title(self) -> None:
        output = OutlineOutput(
            chapter_title="The Dark Forest",
            scenes=["Hero enters forest", "Discovers secret path"],
            outline_text="Hero enters forest\n\nDiscovers secret path",
        )
        assert output.chapter_title == "The Dark Forest"
        assert len(output.scenes) == 2
        assert "Hero" in output.outline_text

    def test_with_metadata(self) -> None:
        output = OutlineOutput(
            chapter_title="Chapter 5",
            metadata={"model": "test", "tokens": 150},
        )
        assert output.metadata["model"] == "test"
        assert output.metadata["tokens"] == 150

    def test_empty_scenes_list(self) -> None:
        output = OutlineOutput(chapter_title="Empty", scenes=[])
        assert output.scenes == []
        assert output.outline_text == ""


class TestOutlineOutputSerialization:
    """OutlineOutput serializes correctly."""

    def test_model_dump(self) -> None:
        output = OutlineOutput(
            chapter_title="Test",
            scenes=["Scene 1"],
        )
        data = output.model_dump()
        assert data["chapter_title"] == "Test"
        assert data["scenes"] == ["Scene 1"]

    def test_roundtrip(self) -> None:
        original = OutlineOutput(
            chapter_title="The Quest",
            scenes=["Departure", "Challenge", "Return"],
            outline_text="Full text",
            metadata={"word_count": 2000},
        )
        data = original.model_dump()
        restored = OutlineOutput.model_validate(data)
        assert restored.chapter_title == original.chapter_title
        assert restored.scenes == original.scenes
        assert restored.metadata == original.metadata
