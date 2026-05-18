"""Tests for writing/pipeline_scene.py — scene outline parsing.

Covers:
1. Split by *** separators
2. Split by numbered markers
3. No markers returns single scene
4. Empty outline handling
"""

from __future__ import annotations

from narrare_core.writing.pipeline_scene import parse_scenes


class TestSceneParsing:
    """parse_scenes splits outlines correctly."""

    def test_split_by_asterisks(self) -> None:
        outline = "Scene A *** Scene B *** Scene C"
        scenes = parse_scenes(outline)
        assert len(scenes) == 3
        assert "Scene A" in scenes[0]

    def test_split_by_numbered_markers(self) -> None:
        outline = "1. First scene\n2. Second scene\n3. Third scene"
        scenes = parse_scenes(outline)
        assert len(scenes) == 3

    def test_no_markers_returns_single(self) -> None:
        outline = "Just a plain outline without markers"
        scenes = parse_scenes(outline)
        assert len(scenes) == 1
        assert scenes[0] == outline

    def test_empty_outline(self) -> None:
        scenes = parse_scenes("")
        assert len(scenes) == 1
