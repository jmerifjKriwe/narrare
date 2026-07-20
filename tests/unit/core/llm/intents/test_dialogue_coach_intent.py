"""Tests for the new DIALOGUE_COACH intent and its docs entry.

Phase 1 of ADR-069 adds the enum member + docs entry only.
Route-table registration is Phase 4.

See: ADR-069 Decision 5, CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from narrare_core.llm.intents import INTENT_DOCS, LLMIntent


class TestDialogueCoachEnum:
    """LLMIntent.DIALOGUE_COACH — enum member exists."""

    def test_enum_value(self) -> None:
        assert LLMIntent.DIALOGUE_COACH == "dialogue_coach"

    def test_is_distinct_from_existing_intents(self) -> None:
        """Semantically distinct from ANALYSE, VOICE, WRITE, REWRITE."""
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.ANALYSE
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.VOICE
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.WRITE
        assert LLMIntent.DIALOGUE_COACH is not LLMIntent.REWRITE

    def test_str_representation(self) -> None:
        assert str(LLMIntent.DIALOGUE_COACH) == "dialogue_coach"


class TestDialogueCoachDocsEntry:
    """INTENT_DOCS has a verbose Scope/Input/Output/NOT entry."""

    def test_docs_entry_exists(self) -> None:
        assert LLMIntent.DIALOGUE_COACH in INTENT_DOCS

    def test_docs_entry_has_required_sections(self) -> None:
        docs = INTENT_DOCS[LLMIntent.DIALOGUE_COACH]
        assert "Scope:" in docs
        assert "Input:" in docs
        assert "Output:" in docs
        assert "NOT:" in docs

    def test_docs_entry_mentions_modes(self) -> None:
        """The docs entry references both analyze and improve modes."""
        docs = INTENT_DOCS[LLMIntent.DIALOGUE_COACH]
        assert "analyze" in docs.lower()
        assert "improve" in docs.lower()

    def test_docs_entry_mentions_adaptive_context(self) -> None:
        """The docs entry references adaptive context as a consumer."""
        docs = INTENT_DOCS[LLMIntent.DIALOGUE_COACH]
        assert "adaptive" in docs.lower() or "preference" in docs.lower()
