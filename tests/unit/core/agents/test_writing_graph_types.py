"""Tests für WritingGraph Types — Enums, State, Deps, Decision-Signals.

Test-Strategie:
- Pure data instantiation / mutation — kein I/O, kein LLM.
- Coverage-Ziel: writing_graph_types.py > 95%.
"""

from __future__ import annotations

from narrare_core.agents.writing_graph_types import (
    Approved,
    NeedsRevision,
    WritingDeps,
    WritingState,
    WritingStatus,
)


class TestWritingStatus:
    """A. Enum-Werte (1 Test)."""

    def test_writing_status_enum_values(self) -> None:
        expected = [
            "planned",
            "outlined",
            "drafted",
            "reviewed",
            "needs_revision",
            "revised",
            "summarized",
            "completed",
            "failed",
        ]
        actual = [s.value for s in WritingStatus]
        assert actual == expected

    def test_writing_status_is_str_enum(self) -> None:
        assert isinstance(WritingStatus.PLANNED, str)
        assert WritingStatus.PLANNED == "planned"


class TestWritingState:
    """B. State-Defaults + Mutation (2 Tests)."""

    def test_writing_state_defaults(self) -> None:
        state = WritingState()
        assert state.chapter_id == ""
        assert state.novel_id == ""
        assert state.outline == ""
        assert state.draft == ""
        assert state.revision == ""
        assert state.final == ""
        assert state.summary == ""
        assert state.status == WritingStatus.PLANNED
        assert state.attempts == 0
        assert state.feedback == ""
        assert state.error == ""

    def test_writing_state_mutation(self) -> None:
        state = WritingState()
        state.chapter_id = "ch-42"
        state.draft = "Once upon a time..."
        state.status = WritingStatus.DRAFTED
        state.attempts = 2
        state.feedback = "Too short"
        state.final = "Once upon a time... revised."

        assert state.chapter_id == "ch-42"
        assert state.draft == "Once upon a time..."
        assert state.status == WritingStatus.DRAFTED
        assert state.attempts == 2
        assert state.feedback == "Too short"
        assert state.final == "Once upon a time... revised."


class TestWritingDeps:
    """C. Deps-Instantiation (1 Test)."""

    def test_writing_deps_minimal(self) -> None:
        """WritingDeps requires registry + composer (CR-AUFG-02-07)."""
        deps = WritingDeps(
            registry="mock_registry",
            composer="mock_composer",  # type: ignore[arg-type]
        )
        assert deps.registry == "mock_registry"
        assert deps.composer == "mock_composer"
        assert deps.context_assembler is None
        assert deps.model_config is None
        assert deps.api_key is None
        assert deps.base_url is None
        assert deps.chapter_content == ""
        assert deps.chapter_outline == ""
        assert deps.genre == ""
        assert deps.word_target is None
        assert deps.tone == "balanced"
        assert deps.language == "en"


class TestDecisionSignals:
    """D. Approved + NeedsRevision (2 Tests)."""

    def test_approved_creation(self) -> None:
        sig = Approved()
        assert isinstance(sig, Approved)
        assert hasattr(sig, "__dataclass_fields__")

    def test_needs_revision_creation(self) -> None:
        sig = NeedsRevision(feedback="Expand the dialogue scene.")
        assert isinstance(sig, NeedsRevision)
        assert sig.feedback == "Expand the dialogue scene."

    def test_needs_revision_default_feedback(self) -> None:
        sig = NeedsRevision()
        assert sig.feedback == ""
