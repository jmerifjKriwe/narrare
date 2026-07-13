"""Tests for ConsistencyDeps kb_relationships field — FIND-001 / CR-AUFG-03-01.

Verifies that ConsistencyDeps accepts a pre-formatted KB relationship
description string (same format as Writing's
``fetch_formatted_relationships`` → ``RenderedKBContext.text``) and that
backward compatibility is maintained (empty-string default).

This unblocks relationship-aware consistency checking: the agent can now
cross-reference the KB relationship graph against chapter events to flag
contradictions (e.g. "Aria is enemy of Malachai" in the KB but they fight
as allies in the text).
"""

from __future__ import annotations

from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
)
from narrare_core.agents.fact_extractor_types import ExtractedFact


class TestConsistencyDepsRelationships:
    """kb_relationships field on ConsistencyDeps (FIND-001)."""

    def test_default_is_empty_string(self) -> None:
        """Without kb_relationships, deps defaults to empty string."""
        deps = ConsistencyDeps()
        assert deps.kb_relationships == ""

    def test_accepts_kb_relationships(self) -> None:
        """kb_relationships accepts a pre-formatted relationship description."""
        formatted = "## Character Relationships\n- Aria ↔ Malachai: enemy\n- Aria ↔ Thane: ally\n"
        deps = ConsistencyDeps(kb_relationships=formatted)
        assert deps.kb_relationships == formatted
        assert "Aria ↔ Malachai: enemy" in deps.kb_relationships

    def test_stores_compact_relationship_string(self) -> None:
        """A compact single-line relationship string is stored verbatim."""
        deps = ConsistencyDeps(kb_relationships="A→B: enemy")
        assert deps.kb_relationships == "A→B: enemy"

    def test_backward_compat_with_existing_fields(self) -> None:
        """Adding kb_relationships doesn't break other fields."""
        deps = ConsistencyDeps(
            language="de",
            novel_id="novel-123",
            chapter_texts={"ch1": "Kapitel eins."},
            kb_entity_summaries=[{"entity_type": "character", "name": "Aria", "traits": ["brave"]}],
            kb_relationships="Aria ↔ Malachai: enemy",
            check_types=[ConsistencyCheckType.WORLD],
            existing_issue_count=2,
        )
        assert deps.language == "de"
        assert deps.novel_id == "novel-123"
        assert "ch1" in deps.chapter_texts
        assert len(deps.kb_entity_summaries) == 1
        assert deps.kb_relationships == "Aria ↔ Malachai: enemy"
        assert ConsistencyCheckType.WORLD in deps.check_types
        assert deps.existing_issue_count == 2

    def test_empty_relationships_is_valid(self) -> None:
        """Empty string is a valid value (novel with no relationships)."""
        deps = ConsistencyDeps(kb_relationships="")
        assert deps.kb_relationships == ""


class TestHasStructuredInputWithRelationships:
    """has_structured_input must remain driven by extracted_facts only.

    Adding kb_relationships must not affect the structured-input flag,
    which gates the ADR-044 staged-pipeline behaviour (prefer structured
    Stage-1 facts over raw-text extraction).
    """

    def test_relationships_alone_do_not_enable_structured_input(self) -> None:
        """kb_relationships alone must not make has_structured_input True."""
        deps = ConsistencyDeps(kb_relationships="Aria ↔ Malachai: enemy")
        assert not deps.has_structured_input

    def test_relationships_with_facts_keeps_structured_input_true(self) -> None:
        """has_structured_input stays True when facts are present alongside relationships."""
        fact = ExtractedFact(
            fact_type="character_state",
            subject="Aria",
            predicate="fights alongside",
            object_value="Malachai",
            chapter_id="ch-3",
            evidence_text="Aria and Malachai fought back to back.",
            confidence=0.9,
        )
        deps = ConsistencyDeps(
            kb_relationships="Aria ↔ Malachai: enemy",
            extracted_facts=[fact],
        )
        assert deps.has_structured_input
        assert deps.kb_relationships == "Aria ↔ Malachai: enemy"

    def test_default_deps_structured_input_false(self) -> None:
        """Default deps (no facts, no relationships) → has_structured_input False."""
        deps = ConsistencyDeps()
        assert not deps.has_structured_input
