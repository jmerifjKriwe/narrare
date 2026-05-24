"""Tests for KBAssistOutput model — validation, modes, defaults.

See kb_assist_types.py D2 — single model with mode discriminator.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.kb_assist_types import KBAssistOutput


class TestQuestionMode:
    """KBAssistOutput in question mode."""

    def test_question_mode(self) -> None:
        output = KBAssistOutput(
            mode="question",
            question="What is the character's primary motivation?",
            field_key="motivations",
        )
        assert output.mode == "question"
        assert output.question == "What is the character's primary motivation?"
        assert output.field_key == "motivations"

    def test_question_mode_with_reasoning(self) -> None:
        output = KBAssistOutput(
            mode="question",
            question="Where does the character live?",
            field_key="residence",
            reasoning="Residence affects story setting and available plot hooks.",
        )
        assert output.reasoning is not None
        assert "setting" in output.reasoning


class TestSuggestionMode:
    """KBAssistOutput in suggestion mode."""

    def test_suggestion_mode(self) -> None:
        output = KBAssistOutput(
            mode="suggestion",
            suggestion="A tower of pale marble veined with gold",
            field_key="appearance",
        )
        assert output.mode == "suggestion"
        assert output.suggestion == "A tower of pale marble veined with gold"
        assert output.field_key == "appearance"


class TestDraftMode:
    """KBAssistOutput in draft mode."""

    def test_draft_mode(self) -> None:
        output = KBAssistOutput(
            mode="draft",
            draft_entry={"name": "Anna", "role": "protagonist", "age": 28},
            progress=0.4,
        )
        assert output.mode == "draft"
        assert output.draft_entry is not None
        assert output.draft_entry["name"] == "Anna"
        assert output.progress == 0.4


class TestCompleteMode:
    """KBAssistOutput in complete mode."""

    def test_complete_mode(self) -> None:
        output = KBAssistOutput(
            mode="complete",
            final_entry={"name": "Anna", "role": "protagonist", "age": 28, "motivation": "Justice"},
            progress=1.0,
        )
        assert output.mode == "complete"
        assert output.final_entry is not None
        assert output.final_entry["name"] == "Anna"
        assert output.progress == 1.0


class TestProgressValidation:
    """Progress field must be between 0.0 and 1.0."""

    def test_progress_validation_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            KBAssistOutput(mode="draft", progress=-0.1)

    def test_progress_validation_rejects_over_one(self) -> None:
        with pytest.raises(ValidationError):
            KBAssistOutput(mode="draft", progress=1.5)

    def test_progress_boundary_zero(self) -> None:
        output = KBAssistOutput(mode="draft", progress=0.0)
        assert output.progress == 0.0

    def test_progress_boundary_one(self) -> None:
        output = KBAssistOutput(mode="complete", progress=1.0)
        assert output.progress == 1.0


class TestDefaultFields:
    """Optional fields default to None."""

    def test_default_none_fields(self) -> None:
        output = KBAssistOutput(mode="question")
        assert output.question is None
        assert output.field_key is None
        assert output.suggestion is None
        assert output.reasoning is None
        assert output.context_used is None
        assert output.draft_entry is None
        assert output.final_entry is None
        assert output.progress is None


class TestContextUsed:
    """context_used accepts list of strings."""

    def test_context_used_list(self) -> None:
        output = KBAssistOutput(
            mode="suggestion",
            suggestion="A dark forest",
            field_key="location_type",
            context_used=["The Dark Woods", "Shadow Realm"],
        )
        assert output.context_used == ["The Dark Woods", "Shadow Realm"]


class TestReasoningOptional:
    """reasoning is optional in all modes."""

    @pytest.mark.parametrize("mode", ["question", "suggestion", "draft", "complete"])
    def test_reasoning_optional(self, mode: str) -> None:
        output = KBAssistOutput(mode=mode)  # type: ignore[arg-type]
        assert output.reasoning is None


class TestSerialization:
    """Round-trip serialization via model_dump / model_validate."""

    def test_roundtrip_question(self) -> None:
        original = KBAssistOutput(
            mode="question",
            question="What is the character's name?",
            field_key="name",
            reasoning="Name is the first required field.",
        )
        data = original.model_dump()
        restored = KBAssistOutput.model_validate(data)
        assert restored.mode == original.mode
        assert restored.question == original.question
        assert restored.field_key == original.field_key

    def test_roundtrip_draft(self) -> None:
        original = KBAssistOutput(
            mode="draft",
            draft_entry={"name": "Tower", "type": "location"},
            progress=0.5,
            context_used=["Anna"],
        )
        data = original.model_dump()
        restored = KBAssistOutput.model_validate(data)
        assert restored.draft_entry == original.draft_entry
        assert restored.progress == original.progress
        assert restored.context_used == original.context_used
