"""Tests for ADR-045 typed mem0 learning-event privacy contracts."""

from __future__ import annotations

from uuid import uuid4

from narrare_core.memory.models import LearningEvent, LearningEventKind, MemoryPrecedenceLevel


class TestLearningEvent:
    """Learning events must be typed, precedence-safe, and privacy-safe by default."""

    def test_suggestion_modified_summary_excludes_raw_prose(self) -> None:
        event = LearningEvent(
            user_id=uuid4(),
            project_id=uuid4(),
            kind=LearningEventKind.SUGGESTION_MODIFIED,
            intent="co_author",
            mode="inline",
            preference_summary="Prefers sharper verbs and shorter paragraphs.",
            source_event_id=uuid4(),
            raw_excerpt="Raw manuscript sentence that must not be forwarded.",
        )

        memory_text = event.to_memory_text()

        assert event.precedence_level == MemoryPrecedenceLevel.LEARNED_MEMORY
        assert "Prefers sharper verbs" in memory_text
        assert "Raw manuscript sentence" not in memory_text
        assert "learned preference" in memory_text.lower()

    def test_learning_event_metadata_is_structured(self) -> None:
        event = LearningEvent(
            user_id=uuid4(),
            project_id=uuid4(),
            kind=LearningEventKind.REPEATED_STEERING,
            intent="chat",
            mode="session",
            preference_summary="Ask before adding new lore.",
            confidence=0.9,
        )

        metadata = event.to_mem0_metadata()

        assert metadata["kind"] == "repeated_steering"
        assert metadata["precedence_level"] == "learned_memory"
        assert metadata["confidence"] == 0.9
