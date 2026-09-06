"""Unit tests for the canonical predicate vocabulary (Task 2, scoring fixes).

Tests cover:
- ``CANONICAL_PREDICATES`` is a frozenset of snake_case strings
- The registry slices carry the reference counts (23 fact + 20 relation)
- Every reference predicate is a member of the canonical set
- Common extraction patterns do not morphologically collide with the
  reference registry (no bare-form/``_of``-form ambiguity)
- The bundled extraction prompt lists every canonical predicate and the
  snake_case fallback rule (prompt/vocabulary alignment guard)
"""

from __future__ import annotations

import re
from pathlib import Path

import narrare_core
from narrare_core.kb.predicates import (
    CANONICAL_PREDICATES,
    COMMON_EXTRACTION_PREDICATES,
    REFERENCE_FACT_PREDICATES,
    REFERENCE_RELATION_PREDICATES,
)

PROMPT_PATH = (
    Path(narrare_core.__file__).resolve().parent
    / "prompts"
    / "_bundled"
    / "kb"
    / "en"
    / "extract"
    / "system.md"
)

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

REFERENCE_FACT_PREDICATES_EXPECTED = frozenset(
    {
        "age_at_death",
        "age_stated",
        "allotment_of",
        "birth_date",
        "birth_year",
        "covers_period",
        "discovered_in_drawer_of",
        "district",
        "exists_from",
        "given_up_for_adoption",
        "in_daily_use",
        "located_at",
        "owner",
        "owner_of",
        "profession",
        "promised_to",
        "relation_to_ilse",
        "residence",
        "residence_of",
        "second_bundle_revealed",
        "student_at",
        "widowed_since",
        "workplace_of",
    }
)

REFERENCE_RELATION_PREDICATES_EXPECTED = frozenset(
    {
        "babysitter_of",
        "business_partner_of",
        "colleague_of",
        "confused_in_mail_with",
        "engaged_to",
        "father_of",
        "first_grandchild_of",
        "grandmother_of",
        "half_sibling_of",
        "keeper_of",
        "met_on_jury_with",
        "mother_of",
        "neighbor_of",
        "not_related_to",
        "property_manager_of",
        "sibling_of",
        "sits_within_earshot_of",
        "son_of",
        "spouse_of",
        "unrelated_to_family_of",
    }
)


class TestCanonicalPredicatesRegistry:
    """Structural invariants of the canonical predicate registry."""

    def test_canonical_predicates_is_frozenset_of_snake_case_strings(self) -> None:
        assert isinstance(CANONICAL_PREDICATES, frozenset)
        assert all(isinstance(p, str) for p in CANONICAL_PREDICATES)
        assert all(SNAKE_CASE.match(p) for p in CANONICAL_PREDICATES)

    def test_registry_slices_carry_reference_counts(self) -> None:
        """Pin the reference corpus slices: 23 fact + 20 relation predicates."""
        assert len(REFERENCE_FACT_PREDICATES) == 23
        assert len(REFERENCE_RELATION_PREDICATES) == 20

    def test_canonical_predicates_cover_reference_registry(self) -> None:
        assert REFERENCE_FACT_PREDICATES == REFERENCE_FACT_PREDICATES_EXPECTED
        assert REFERENCE_RELATION_PREDICATES == REFERENCE_RELATION_PREDICATES_EXPECTED
        assert CANONICAL_PREDICATES == (
            REFERENCE_FACT_PREDICATES | REFERENCE_RELATION_PREDICATES | COMMON_EXTRACTION_PREDICATES
        )

    def test_common_patterns_do_not_collide_with_reference_morphology(self) -> None:
        """A common pattern must never differ from a reference predicate
        only by the ``_of`` suffix — that would make the offered
        vocabulary ambiguous."""
        reference = REFERENCE_FACT_PREDICATES | REFERENCE_RELATION_PREDICATES
        for pattern in COMMON_EXTRACTION_PREDICATES:
            assert f"{pattern}_of" not in reference
            if pattern.endswith("_of"):
                assert pattern.removesuffix("_of") not in reference


class TestExtractionPromptAlignment:
    """The extraction prompt must offer exactly the canonical vocabulary."""

    def test_extract_prompt_lists_every_canonical_predicate(self) -> None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        missing = sorted(p for p in CANONICAL_PREDICATES if p not in prompt)
        assert missing == []

    def test_extract_prompt_states_snake_case_fallback_rule(self) -> None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        assert "For facts not covered, use snake_case English keys." in prompt
