"""Tests für DraftOutput und DraftConfig Modelle.

Siehe ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from narrare_core.agents.draft_types import DraftConfig, DraftOutput


class TestDraftOutput:
    """F. Pydantic Model Validation — DraftOutput."""

    def test_default_values(self) -> None:
        """DraftOutput erfordert nur text, alles andere hat Defaults."""
        output = DraftOutput(text="Test content")
        assert output.text == "Test content"
        assert output.title is None
        assert output.scene_breaks == []
        assert output.word_count == 0
        assert output.metadata == {}

    def test_with_all_fields(self) -> None:
        """DraftOutput mit allen Feldern."""
        output = DraftOutput(
            text="Chapter text here",
            title="Chapter 1",
            scene_breaks=[10, 50],
            word_count=3,
            metadata={"model": "test", "tokens": 100},
        )
        assert output.text == "Chapter text here"
        assert output.title == "Chapter 1"
        assert output.scene_breaks == [10, 50]
        assert output.word_count == 3
        assert output.metadata == {"model": "test", "tokens": 100}

    def test_serialization_roundtrip(self) -> None:
        """DraftOutput → dict → DraftOutput via model_dump / model_validate."""
        original = DraftOutput(
            text="Test",
            title="Chapter",
            scene_breaks=[5],
            word_count=1,
            metadata={"key": "val"},
        )
        data = original.model_dump()
        restored = DraftOutput.model_validate(data)
        assert restored.text == original.text
        assert restored.title == original.title
        assert restored.scene_breaks == original.scene_breaks
        assert restored.word_count == original.word_count
        assert restored.metadata == original.metadata


class TestDraftConfig:
    """F. Pydantic Model Validation — DraftConfig."""

    def test_default_values(self) -> None:
        """DraftConfig mit Standardwerten."""
        config = DraftConfig()
        assert config.mode == "full_draft"
        assert config.tone is None
        assert config.max_tokens == 8192
        assert config.word_target is None

    def test_with_custom_values(self) -> None:
        """DraftConfig mit benutzerdefinierten Werten in verschiedenen Modi."""
        config = DraftConfig(
            mode="scene_by_scene",
            tone="dark",
            max_tokens=4096,
            word_target=500,
        )
        assert config.mode == "scene_by_scene"
        assert config.tone == "dark"
        assert config.max_tokens == 4096
        assert config.word_target == 500
