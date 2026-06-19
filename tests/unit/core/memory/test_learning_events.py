"""Tests for ADR-045 typed mem0 learning-event privacy contracts."""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.memory.models import LearningEvent, LearningEventKind, MemoryPrecedenceLevel

# All ADR-045 Decision 8 kinds present on LearningEventKind (the
# suggestion_accepted/rejected/modified trio flows via FeedbackAction).
ALL_KINDS = list(LearningEventKind)
# The two kinds added to complete the ADR-045 taxonomy.
NEW_KINDS = [LearningEventKind.KB_INTERVIEW_STYLE, LearningEventKind.ANALYSIS_CALIBRATION]


def _make_event(
    kind: LearningEventKind,
    *,
    preference_summary: str = "Prefers concise feedback.",
    raw_excerpt: str | None = None,
    confidence: float = 1.0,
) -> LearningEvent:
    """Build a LearningEvent with the given kind and privacy-safe summary."""
    return LearningEvent(
        user_id=uuid4(),
        project_id=uuid4(),
        kind=kind,
        intent="co_author",
        mode="inline",
        preference_summary=preference_summary,
        source_event_id=uuid4(),
        raw_excerpt=raw_excerpt,
        confidence=confidence,
    )


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


class TestLearningEventKindTaxonomy:
    """ADR-045 Decision 8: all kinds resolve to LEARNED_MEMORY precedence."""

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_every_kind_resolves_to_learned_memory(self, kind: LearningEventKind) -> None:
        event = _make_event(kind)
        assert event.precedence_level == MemoryPrecedenceLevel.LEARNED_MEMORY

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_every_kind_metadata_reports_learned_memory(self, kind: LearningEventKind) -> None:
        metadata = _make_event(kind).to_mem0_metadata()
        assert metadata["kind"] == kind.value
        assert metadata["precedence_level"] == "learned_memory"


class TestNewLearningEventKinds:
    """kb_interview_style and analysis_calibration complete the ADR-045 taxonomy.

    These kinds capture interaction-style / reviewer-lens preferences only —
    they must never store factual world data and never weaken evidence gates.
    The privacy boundary is structural: to_memory_text() emits only the
    preference_summary, never raw_excerpt.
    """

    @pytest.mark.parametrize("kind", NEW_KINDS)
    def test_to_memory_text_carries_preference_summary(self, kind: LearningEventKind) -> None:
        event = _make_event(kind, preference_summary="Prefers concise questions.")

        memory_text = event.to_memory_text()

        assert memory_text == "[learned preference] Prefers concise questions."

    @pytest.mark.parametrize("kind", NEW_KINDS)
    def test_precedence_level_is_learned_memory(self, kind: LearningEventKind) -> None:
        event = _make_event(kind)
        assert event.precedence_level == MemoryPrecedenceLevel.LEARNED_MEMORY

    @pytest.mark.parametrize("kind", NEW_KINDS)
    def test_metadata_includes_correct_kind_value(self, kind: LearningEventKind) -> None:
        event = _make_event(kind, confidence=0.8)

        metadata = event.to_mem0_metadata()

        assert metadata["kind"] == kind.value
        assert metadata["precedence_level"] == "learned_memory"
        assert metadata["confidence"] == 0.8

    @pytest.mark.parametrize("kind", NEW_KINDS)
    def test_raw_excerpt_excluded_from_memory_text(self, kind: LearningEventKind) -> None:
        """Privacy: new kinds must not forward raw prose to mem0.

        Only the preference_summary (a style/calibration marker such as
        'prefers concise questions') may reach memory_text; the raw_excerpt
        must always be stripped.
        """
        event = _make_event(
            kind,
            preference_summary="Prefers pacing-focused analysis feedback.",
            raw_excerpt="The dragon soared over the burning city at dawn.",
        )

        memory_text = event.to_memory_text()

        assert "Prefers pacing-focused analysis feedback." in memory_text
        assert "The dragon soared over the burning city at dawn." not in memory_text
        assert "learned preference" in memory_text.lower()
